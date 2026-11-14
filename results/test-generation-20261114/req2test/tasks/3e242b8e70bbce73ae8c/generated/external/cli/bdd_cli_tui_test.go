//go:build cli

package cli

import (
	"context"
	"fmt"
	"io"
	"log/slog"
	"strings"
	"testing"

	"github.com/EvilFreelancer/coddy-agent/external/cli/tui"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/cucumber/godog"
)

type cliFeatureState struct {
	t      *testing.T
	app    *App
	term   *cliFeatureTerminal
	ctx    context.Context
	cancel context.CancelFunc
}

type cliFeatureTerminal struct {
	cols, rows int
	writes     strings.Builder
}

func (f *cliFeatureTerminal) Write(s string)                 { f.writes.WriteString(s) }
func (f *cliFeatureTerminal) Columns() int                   { return f.cols }
func (f *cliFeatureTerminal) Rows() int                      { return f.rows }
func (*cliFeatureTerminal) HideCursor()                      {}
func (*cliFeatureTerminal) ShowCursor()                      {}
func (*cliFeatureTerminal) Start(func([]byte), func()) error { return nil }
func (*cliFeatureTerminal) Stop()                            {}
func (*cliFeatureTerminal) SetTitle(string)                  {}

// The UI scenario never starts a turn; this backend only supplies the new
// session required by App.Start.
type cliFeatureBackend struct{}

func (*cliFeatureBackend) SetPreferredSessionID(string)                 {}
func (*cliFeatureBackend) ForgetLiveSession(string)                     {}
func (*cliFeatureBackend) SessionByID(string) *session.State            { return nil }
func (*cliFeatureBackend) FileStore() *session.FileStore                { return nil }
func (*cliFeatureBackend) ToolCallResult(string, string) (string, bool) { return "", false }
func (*cliFeatureBackend) HandleSessionNew(context.Context, acp.SessionNewParams) (*acp.SessionNewResult, error) {
	return &acp.SessionNewResult{SessionID: "bdd-session"}, nil
}
func (*cliFeatureBackend) HandleSessionLoad(context.Context, acp.SessionLoadParams) (*acp.SessionLoadResult, error) {
	return nil, fmt.Errorf("unexpected load")
}
func (*cliFeatureBackend) HandleSessionList(context.Context, acp.SessionListParams) (*acp.SessionListResult, error) {
	return nil, fmt.Errorf("unexpected list")
}
func (*cliFeatureBackend) HandleSessionReady(string)                   {}
func (*cliFeatureBackend) HandleSessionCancel(acp.SessionCancelParams) {}
func (*cliFeatureBackend) HandleSessionSetMode(context.Context, acp.SessionSetModeParams) error {
	return nil
}
func (*cliFeatureBackend) HandleSessionSetConfigOption(context.Context, acp.SessionSetConfigOptionParams) (*acp.SessionSetConfigOptionResult, error) {
	return nil, nil
}
func (*cliFeatureBackend) HandleSessionPromptWithSender(context.Context, acp.SessionPromptParams, acp.UpdateSender, *session.PromptRunOpts) (*acp.SessionPromptResult, error) {
	return nil, fmt.Errorf("unexpected prompt")
}
func (*cliFeatureBackend) ProviderUsageForSession(context.Context, string, string, bool) (*acp.ProviderUsageUpdate, error) {
	return nil, nil
}

func TestCLITUIFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			state := &cliFeatureState{t: t, term: &cliFeatureTerminal{cols: 80, rows: 24}}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				state.ctx, state.cancel = context.WithCancel(ctx)
				cfg := &config.Config{Paths: config.Paths{Home: t.TempDir(), CWD: t.TempDir()}}
				state.app = newApp(cfg, &cliFeatureBackend{}, slog.New(slog.NewTextHandler(io.Discard, nil)), state.term, "dark", true)
				return state.ctx, nil
			})
			sc.After(func(context.Context, *godog.Scenario, error) (context.Context, error) {
				if state.cancel != nil {
					state.cancel()
				}
				return nil, nil
			})
			sc.Given(`^a coddy console app over a stub agent runner$`, func() {})
			sc.When(`^the console app starts$`, func() error {
				if err := state.app.Start(state.ctx, "", false); err != nil {
					return err
				}
				go func() { _ = state.app.Run(state.ctx) }()
				return nil
			})
			sc.When(`^the operator types "([^"]*)" without sending it$`, func(text string) {
				state.app.OnTerminalInput([]byte(text))
				// Run consumes input asynchronously; wait for its render.
				state.app.screen.RenderNow()
			})
			sc.Then(`^the editor borders render in the local shell color$`, func() error {
				want := state.app.theme.Fg(roleBashMode, "│")
				rendered := strings.Join(state.app.editor.Render(80), "\n")
				if !strings.Contains(rendered, want) {
					return fmt.Errorf("editor did not render border in local-shell color; got %q, want %q", rendered, want)
				}
				return nil
			})
		},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed: %d", status)
	}
}

var _ tui.Terminal = (*cliFeatureTerminal)(nil)
