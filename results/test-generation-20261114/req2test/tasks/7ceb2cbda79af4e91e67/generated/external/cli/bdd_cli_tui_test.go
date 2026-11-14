//go:build cli

package cli

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/EvilFreelancer/coddy-agent/external/cli/tui"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/cucumber/godog"
)

type consoleBDDTerminal struct {
	cols, rows int
}

type bddTerminal = consoleBDDTerminal

func (t *consoleBDDTerminal) Write(string)                     {}
func (t *consoleBDDTerminal) Columns() int                     { return t.cols }
func (t *consoleBDDTerminal) Rows() int                        { return t.rows }
func (t *consoleBDDTerminal) HideCursor()                      {}
func (t *consoleBDDTerminal) ShowCursor()                      {}
func (t *consoleBDDTerminal) Start(func([]byte), func()) error { return nil }
func (t *consoleBDDTerminal) Stop()                            {}
func (t *consoleBDDTerminal) SetTitle(string)                  {}

type consoleBDD struct {
	t     *testing.T
	cfg   *config.Config
	store *session.FileStore
	cwd   string
	app   *App
	mgr   *session.Manager
}

func TestCLITUIFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			b := &consoleBDD{t: t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				root := t.TempDir()
				b.cwd = filepath.Join(root, "work")
				if err := os.MkdirAll(b.cwd, 0755); err != nil {
					return ctx, err
				}
				b.store = &session.FileStore{Root: filepath.Join(root, "sessions")}
				b.cfg = &config.Config{Paths: config.Paths{Home: root, CWD: b.cwd}}
				return ctx, nil
			})
			sc.Step(`^a coddy console app over a stub agent runner$`, func() error {
				runner := func(_ context.Context, st *session.State, prompt []acp.ContentBlock, _ acp.UpdateSender) (string, error) {
					var text string
					for _, p := range prompt {
						text += p.Text
					}
					st.AddMessage(llm.Message{Role: llm.RoleAssistant, Content: "continued"})
					return string(acp.StopReasonEndTurn), nil
				}
				b.mgr = session.NewManager(b.cfg, nil, runner, slog.New(slog.DiscardHandler), b.cwd, b.store)
				b.app = newApp(b.cfg, b.mgr, slog.New(slog.DiscardHandler), &consoleBDDTerminal{80, 24}, "dark", true)
				return nil
			})
			sc.Step(`^a previous console session with the prompt "([^"]*)" and the reply "([^"]*)"$`, func(prompt, reply string) error {
				runner := func(_ context.Context, st *session.State, _ []acp.ContentBlock, _ acp.UpdateSender) (string, error) {
					st.AddMessage(llm.Message{Role: llm.RoleUser, Content: prompt})
					st.AddMessage(llm.Message{Role: llm.RoleAssistant, Content: reply})
					return string(acp.StopReasonEndTurn), nil
				}
				m := session.NewManager(b.cfg, nil, runner, slog.New(slog.DiscardHandler), b.cwd, b.store)
				res, err := m.HandleSessionNew(context.Background(), acp.SessionNewParams{CWD: b.cwd})
				if err != nil {
					return err
				}
				_, err = m.HandleSessionPrompt(context.Background(), acp.SessionPromptParams{SessionID: res.SessionID, Prompt: []acp.ContentBlock{{Type: "text", Text: prompt}}})
				return err
			})
			sc.Step(`^the console app starts continuing the latest session$`, func() error {
				if err := b.app.StartContinue(context.Background()); err != nil {
					return err
				}
				ctx, cancel := context.WithCancel(context.Background())
				done := make(chan struct{})
				go func() { defer close(done); _ = b.app.Run(ctx) }()
				time.Sleep(30 * time.Millisecond)
				cancel()
				<-done
				return nil
			})
			sc.Step(`^the transcript shows a user message block containing "([^"]*)"$`, func(want string) error {
				if !strings.Contains(consoleBDDTranscript(b.app), want) {
					return fmt.Errorf("transcript does not contain user text %q", want)
				}
				return nil
			})
			sc.Step(`^the transcript shows the assistant text "([^"]*)"$`, func(want string) error {
				if !strings.Contains(consoleBDDTranscript(b.app), want) {
					return fmt.Errorf("transcript does not contain assistant text %q", want)
				}
				return nil
			})
		},
		Options: &godog.Options{Format: "pretty"},
	}
	if status := suite.Run(); status != 0 {
		t.Fatal("Godog feature failed")
	}
}

func consoleBDDTranscript(a *App) string {
	lines := a.screen.Snapshot()
	for i := range lines {
		lines[i] = tui.StripTerminalSequences(lines[i])
	}
	return strings.Join(lines, "\n")
}
