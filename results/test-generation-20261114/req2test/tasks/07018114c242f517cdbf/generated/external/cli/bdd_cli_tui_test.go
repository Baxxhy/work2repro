//go:build cli

package cli

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/external/cli/tui"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type cliBDDTerminal struct{ cols, rows int }
func (t *cliBDDTerminal) Write(string) {}
func (t *cliBDDTerminal) Columns() int { return t.cols }
func (t *cliBDDTerminal) Rows() int { return t.rows }
func (*cliBDDTerminal) HideCursor() {}
func (*cliBDDTerminal) ShowCursor() {}
func (*cliBDDTerminal) Start(func([]byte), func()) error { return nil }
func (*cliBDDTerminal) Stop() {}
func (*cliBDDTerminal) SetTitle(string) {}

type cliTUIWorld struct {
	t *testing.T
	app *App
	manager *session.Manager
	term *cliBDDTerminal
	cancel context.CancelFunc
	runDone chan error
	api *httptest.Server
	apiCalls int
	mu sync.Mutex
}

func (w *cliTUIWorld) setup(disabled bool) error {
	root, err := os.MkdirTemp("", "coddy-cli-bdd-")
	if err != nil { return err }
	boolOff := false
	cfg := &config.Config{
		Paths: config.Paths{Home: root, CWD: root},
		Providers: []config.ProviderConfig{{Name:"neuraldeep", Type:"neuraldeep", APIKey:"test-key", UsageLimitsPanel:&boolOff}},
		Models: []config.ModelEntry{{Model:"neuraldeep/qwen3.8-27b", MaxTokens:100, MaxContextTokens:1000}},
		Agent: config.Agent{Model:"neuraldeep/qwen3.8-27b"},
	}
	w.api = httptest.NewServer(http.HandlerFunc(func(rw http.ResponseWriter, r *http.Request) {
		w.mu.Lock(); w.apiCalls++; w.mu.Unlock()
		rw.Header().Set("Content-Type","application/json")
		_, _ = rw.Write([]byte(`{"ok":false,"unsupported":true,"disabled":true,"provider":"neuraldeep","providerType":"neuraldeep"}`))
	}))
	cfg.Providers[0].APIBase = w.api.URL + "/v1"
	w.term = &cliBDDTerminal{100,30}
	w.manager = session.NewManager(cfg, nil, func(_ context.Context, st *session.State, _ []acp.ContentBlock, sender acp.UpdateSender) (string,error) {
		_ = sender.SendSessionUpdate(st.GetID(), acp.NewSessionUpdate(acp.UpdateTypeAgentMessage, map[string]interface{}{"text":"spent"}))
		return "", nil
	}, slog.New(slog.DiscardHandler), root, nil)
	w.app = newApp(cfg,w.manager,slog.New(slog.DiscardHandler),w.term,"dark",true)
	ctx,cancel := context.WithCancel(context.Background())
	w.cancel=cancel; w.runDone=make(chan error,1)
	if err=w.app.Start(ctx,"",false); err != nil { return err }
	go func(){ w.runDone <- w.app.Run(ctx) }()
	return nil
}

func (w *cliTUIWorld) close() {
	if w.cancel != nil { w.cancel() }
	if w.app != nil { w.app.Close(); w.app.JoinWorkers(time.Second) }
	if w.api != nil { w.api.Close() }
}
func (w *cliTUIWorld) input(s string) { w.app.OnTerminalInput([]byte(s)) }
func (w *cliTUIWorld) snapshot() string {
	lines:=w.app.screen.Snapshot()
	for i:=range lines { lines[i]=tui.StripTerminalSequences(lines[i]) }
	return strings.Join(lines,"\n")
}

func TestCLITUIFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			w:=&cliTUIWorld{t:t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context,error) { return context.WithValue(ctx, cliWorldKey{}, w),nil })
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context,error) { w.close(); return ctx,nil })
			world:=func(ctx context.Context)*cliTUIWorld { return ctx.Value(cliWorldKey{}).(*cliTUIWorld) }
			start:=func(ctx context.Context, disabled bool) error { return world(ctx).setup(disabled) }
			sc.Step(`^a coddy console app over a stub agent runner$`,func(ctx context.Context) error{return start(ctx,false)})
			sc.Step(`^a coddy console app over a stub agent runner with a neuraldeep provider whose usage limits panel is switched off$`,func(ctx context.Context) error{return start(ctx,true)})
			sc.Step(`^the console app starts$`,func(ctx context.Context) error{return nil})
			sc.Step(`^the operator submits the prompt "([^"]*)"$`,func(ctx context.Context, prompt string) error {
				world(ctx).input(prompt+"\r"); return nil
			})
			sc.Step(`^the stub turn streams the text "([^"]*)"$`,func(ctx context.Context, text string) error {
				w:=world(ctx)
				// Manager runner emits the fixture update on prompt. The test wording
				// supplies its expected payload; allow the UI loop to consume it.
				if text!="spent" { return fmt.Errorf("unexpected stub text %q",text) }
				return w.manager.WaitProviderUsageIdle(time.Second)
			})
			sc.Step(`^the operator submits the command "/usage"$`,func(ctx context.Context) error {
				world(ctx).input("/usage\r"); return nil
			})
			sc.Step(`^the usage report shows "([^"]*)"$`,func(ctx context.Context, want string) error {
				return waitForCLIText(world(ctx),want)
			})
			sc.Step(`^the footer does not show the neuraldeep usage$`,func(ctx context.Context) error {
				w:=world(ctx); s:=w.snapshot()
				if strings.Contains(s,"3h") || strings.Contains(s,"wallet") { return fmt.Errorf("footer unexpectedly contains usage: %s",s) }
				return nil
			})
			sc.Step(`^the stand-in limits API was never asked$`,func(ctx context.Context) error {
				w:=world(ctx); w.mu.Lock(); defer w.mu.Unlock()
				if w.apiCalls!=0 { return fmt.Errorf("limits API called %d times",w.apiCalls) }; return nil
			})
		},
	}
	_ = filepath.Separator
	if status:=suite.Run(); status!=0 { t.Fatalf("Godog suite failed with status %d",status) }
}
type cliWorldKey struct{}

func waitForCLIText(w *cliTUIWorld, text string) error {
	deadline:=time.Now().Add(2*time.Second)
	for time.Now().Before(deadline) {
		if strings.Contains(w.snapshot(),text) { return nil }
		time.Sleep(10*time.Millisecond)
	}
	return fmt.Errorf("console did not show %q; screen:\n%s",text,w.snapshot())
}
