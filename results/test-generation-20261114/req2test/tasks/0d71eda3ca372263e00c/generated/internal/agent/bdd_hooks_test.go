package agent

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/hooks"
	"github.com/EvilFreelancer/coddy-agent/internal/hooks/hooktest"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/cucumber/godog"
)

type hookBDDWorld struct {
	t      *testing.T
	dir    string
	agent  *Agent
	state  *session.State
	sender *hookBDDReporter
	result string
	err    error
}

type hookBDDReporter struct{ permissions int }

func (*hookBDDReporter) SendSessionUpdate(string, interface{}) error { return nil }
func (s *hookBDDReporter) RequestPermission(context.Context, acp.PermissionRequestParams) (*acp.PermissionResult, error) {
	s.permissions++
	return &acp.PermissionResult{Outcome: "allow", OptionID: "allow"}, nil
}
func (*hookBDDReporter) RequestQuestion(context.Context, acp.QuestionRequestParams) (*acp.QuestionResult, error) {
	return &acp.QuestionResult{}, nil
}

type hookBDDProvider struct{ turn int }

func (*hookBDDProvider) Complete(context.Context, []llm.Message, []llm.ToolDefinition) (*llm.Response, error) {
	return nil, fmt.Errorf("unexpected Complete")
}
func (p *hookBDDProvider) Stream(_ context.Context, _ []llm.Message, _ []llm.ToolDefinition, onChunk func(llm.StreamChunk)) (*llm.Response, error) {
	p.turn++
	if p.turn == 1 {
		call := llm.ToolCall{ID: "hook-bdd-call", Name: "run_command", InputJSON: `{"command":"echo allowed-by-hook"}`}
		onChunk(llm.StreamChunk{ToolCall: &call})
		return &llm.Response{ToolCalls: []llm.ToolCall{call}, StopReason: "tool_use"}, nil
	}
	onChunk(llm.StreamChunk{TextDelta: "Command completed."})
	return &llm.Response{Content: "Command completed.", StopReason: "end_turn"}, nil
}

func TestHelperHook(t *testing.T) {
	if hooktest.Main(os.Args[1:]) {
		return
	}
	t.Skip("hook helper process only")
}

func TestHooksFeature(t *testing.T) {
	w := &hookBDDWorld{t: t}
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				w.dir = t.TempDir()
				return ctx, nil
			})
			sc.Given(`the operator's hooks\.json has a PreToolUse hook for "run_command" that allows every call`, func() error {
				return hooktest.Write(filepath.Join(w.dir, "hooks.json"), hooktest.Entry{
					Event: hooks.EventPreToolUse, Matcher: "run_command",
					Handlers: []hooks.Handler{hooktest.Handler("allow")},
				})
			})
			sc.Given(`an agent session in permission mode "ask"`, func() error {
				cwd := filepath.Join(w.dir, "workspace")
				if err := os.MkdirAll(cwd, 0o755); err != nil {
					return err
				}
				w.state = &session.State{ID: "hook-bdd-session", CWD: cwd, Mode: session.ModeAgent, SessionDir: filepath.Join(w.dir, "session")}
				w.state.SetPermissionMode("ask")
				w.sender = &hookBDDReporter{}
				cfg := &config.Config{
					Paths:     config.Paths{Home: w.dir, CWD: cwd},
					Providers: []config.ProviderConfig{{Name: "fake", Type: "openai", APIKey: "test"}},
					Models:    []config.ModelEntry{{Model: "fake/model", MaxTokens: 128}},
					Agent:     config.Agent{Model: "fake/model"},
				}
				cfg.Hooks.ApplyDefaults(cfg.Paths)
				w.agent = NewAgent(cfg, w.state, w.sender, slog.New(slog.NewTextHandler(os.Stderr, nil)))
				w.agent.SetProviderFactory(func(llm.ProviderInput) (llm.Provider, error) { return &hookBDDProvider{}, nil })
				return nil
			})
			sc.When(`the model runs the command "echo allowed-by-hook"`, func() error {
				w.result, w.err = w.agent.Run(context.Background(), []acp.ContentBlock{{Type: "text", Text: "run the command"}})
				return w.err
			})
			sc.Then(`the tool result contains "allowed-by-hook"`, func() error {
				if w.err != nil {
					return w.err
				}
				for _, msg := range w.state.GetMessages() {
					if msg.Role == llm.RoleTool && strings.Contains(msg.Content, "allowed-by-hook") {
						return nil
					}
				}
				return fmt.Errorf("tool result did not contain allowed-by-hook; final response: %q", w.result)
			})
			sc.Then(`the client received no permission request`, func() error {
				if w.sender.permissions != 0 {
					return fmt.Errorf("received %d permission requests", w.sender.permissions)
				}
				return nil
			})
		},
		Options: &godog.Options{Format: "pretty"},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed with status %d", status)
	}
}
