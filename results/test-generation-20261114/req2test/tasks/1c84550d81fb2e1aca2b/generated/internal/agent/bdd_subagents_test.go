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
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/EvilFreelancer/coddy-agent/internal/subagents"
	"github.com/cucumber/godog"
)

type deniedSubagentWorld struct {
	t      *testing.T
	cwd    string
	cfg    *config.Config
	state  *session.State
	agent  *Agent
	prompt string
	defs   []*subagents.Definition
}

type deniedSubagentProvider struct{ prompt *string }

func (p deniedSubagentProvider) Complete(context.Context, []llm.Message, []llm.ToolDefinition) (*llm.Response, error) {
	return nil, fmt.Errorf("unexpected Complete")
}
func (p deniedSubagentProvider) Stream(_ context.Context, messages []llm.Message, _ []llm.ToolDefinition, onChunk func(llm.StreamChunk)) (*llm.Response, error) {
	for _, m := range messages {
		if m.Role == llm.RoleSystem {
			*p.prompt = m.Content
			break
		}
	}
	onChunk(llm.StreamChunk{TextDelta: "ready"})
	return &llm.Response{Content: "ready", StopReason: "end_turn"}, nil
}

func TestSubagentsFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			w := &deniedSubagentWorld{t: t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) { return ctx, nil })
			sc.Given(`^a workspace with a subagent definition "([^"]+)" under \.coddy/agents$`, w.definition)
			sc.Given(`^the subagents project trust policy is "([^"]+)"$`, w.trust)
			sc.Given(`^a parent agent session in that workspace$`, w.parent)
			sc.When(`^the parent model receives its first request$`, w.request)
			sc.Then(`^the system prompt does not list the subagent "([^"]+)"$`, w.promptExcludes)
			sc.Then(`^the subagent catalog for that workspace does not name "([^"]+)"$`, w.catalogExcludes)
		},
		Options: &godog.Options{},
	}
	if suite.Run() != 0 {
		t.Fatal("Godog feature failed")
	}
}

func (w *deniedSubagentWorld) definition(name string) error {
	root, err := os.MkdirTemp("", "coddy-subagents-*")
	if err != nil {
		return err
	}
	w.cwd = root
	dir := filepath.Join(root, ".coddy", "agents")
	if err := os.MkdirAll(dir, 0755); err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(dir, name+".md"), []byte("---\nname: "+name+"\ndescription: Review changes carefully.\n---\nDo a bounded review.\n"), 0644)
}
func (w *deniedSubagentWorld) trust(policy string) error {
	w.cfg = &config.Config{}
	w.cfg.Subagents.ProjectTrust = policy
	w.cfg.Subagents.Dirs = config.DefaultSubagentDirs()
	return nil
}
func (w *deniedSubagentWorld) parent() error {
	w.state = &session.State{ID: "bdd-parent", CWD: w.cwd, Mode: session.ModeAgent, SessionDir: filepath.Join(w.cwd, "session")}
	w.agent = NewAgent(w.cfg, w.state, bddNoopSender{}, slog.Default())
	w.agent.SetProviderFactory(func(llm.ProviderInput) (llm.Provider, error) { return deniedSubagentProvider{&w.prompt}, nil })
	return nil
}
func (w *deniedSubagentWorld) request() error {
	_, err := w.agent.Run(context.Background(), []acp.ContentBlock{{Type: "text", Text: "Inspect the workspace."}})
	return err
}
func (w *deniedSubagentWorld) promptExcludes(name string) error {
	if strings.Contains(w.prompt, name) {
		return fmt.Errorf("system prompt unexpectedly names %q", name)
	}
	return nil
}
func (w *deniedSubagentWorld) catalogExcludes(name string) error {
	loader := subagents.NewLoader(w.cfg.Subagents.Dirs, w.cfg.Subagents.ResolvedProjectTrust())
	w.defs = loader.Load(w.cwd, "")
	if subagents.FindByName(w.defs, name) != nil {
		return fmt.Errorf("catalog unexpectedly loaded %q", name)
	}
	return nil
}

type bddNoopSender struct{}

func (bddNoopSender) SendSessionUpdate(string, interface{}) error { return nil }
func (bddNoopSender) RequestPermission(context.Context, acp.PermissionRequestParams) (*acp.PermissionResult, error) {
	return &acp.PermissionResult{Outcome: "allow"}, nil
}
func (bddNoopSender) RequestQuestion(context.Context, acp.QuestionRequestParams) (*acp.QuestionResult, error) {
	return &acp.QuestionResult{}, nil
}
