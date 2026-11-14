//go:build cli

package cli

import (
	"context"
	"fmt"
	"log/slog"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/external/cli/tui"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type cliQuestionTerminal struct{}
func (cliQuestionTerminal) Write(string) {}
func (cliQuestionTerminal) Columns() int { return 100 }
func (cliQuestionTerminal) Rows() int { return 32 }
func (cliQuestionTerminal) HideCursor() {}
func (cliQuestionTerminal) ShowCursor() {}
func (cliQuestionTerminal) Start(func([]byte), func()) error { return nil }
func (cliQuestionTerminal) Stop() {}
func (cliQuestionTerminal) SetTitle(string) {}

type cliBDD struct {
	t *testing.T
	app *App
	ctx context.Context
	cancel context.CancelFunc
	mgr *session.Manager
	answer chan *acp.QuestionResult
	observed chan *acp.QuestionResult
}

func TestCLITUIFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			b := &cliBDD{t:t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context,error) {
				root := t.TempDir()
				cfg := &config.Config{Paths:config.Paths{Home:root,CWD:root}, Models:[]config.ModelEntry{{Model:"stub/model",MaxTokens:100}}, Agent:config.Agent{Model:"stub/model"}, Sessions:config.Sessions{Dir:filepath.Join(root,"sessions")}}
				store := &session.FileStore{Root:cfg.Sessions.Dir}
				b.observed = make(chan *acp.QuestionResult,1)
				late := &lateBoundSender{}
				var mgr *session.Manager
				runner := func(ctx context.Context, st *session.State, _ []acp.ContentBlock, snd acp.UpdateSender)(string,error) {
					res, err := snd.RequestQuestion(ctx, acp.QuestionRequestParams{
						SessionID: st.GetID(), RequestID: "question-1", ToolCallID: "tool-1",
						Questions: []acp.QuestionPrompt{{Header:"Pick or type", Question:"Pick or type", Options:[]acp.QuestionOption{{Label:"Option"}}, Custom:true}},
					})
					if err == nil { b.observed <- res }
					return string(acp.StopReasonEndTurn), err
				}
				mgr = session.NewManager(cfg, late, runner, slog.Default(), root, store)
				b.mgr = mgr
				b.app = newApp(cfg, mgr, slog.Default(), cliQuestionTerminal{}, "dark", true)
				late.inner = b.app.Sender()
				b.ctx, b.cancel = context.WithCancel(ctx)
				b.app.Start(b.ctx, "", false)
				go b.app.Run(b.ctx)
				t.Cleanup(func(){ b.cancel(); b.app.Close(); b.app.JoinWorkers(time.Second) })
				return ctx,nil
			})
			sc.Step(`^a coddy console app over a stub agent runner$`, b.setup)
			sc.Step(`^the console app starts$`, b.start)
			sc.Step(`^the operator submits the prompt "([^"]*)"$`, b.submit)
			sc.Step(`^the stub turn asks a question titled "([^"]*)" that allows a custom answer$`, b.ask)
			sc.Step(`^the operator chooses the custom answer and types "([^"]*)"$`, b.typeAnswer)
			sc.Step(`^the stub turn observes the question answer "([^"]*)"$`, b.observe)
		},
	}
	if status := suite.Run(); status != 0 { t.Fatalf("godog status %d", status) }
}

func (b *cliBDD) setup() error { return nil }
func (b *cliBDD) start() error { return nil }
func (b *cliBDD) submit(s string) error {
	for _, r := range s { b.app.OnTerminalInput([]byte(string(r))) }
	b.app.OnTerminalInput([]byte{'\r'})
	return nil
}
func (b *cliBDD) ask(s string) error {
	// Prompt submission starts the stub runner, which issues RequestQuestion.
	return nil
}
func (b *cliBDD) typeAnswer(s string) error {
	for i:=0; i<300 && b.app.modal==nil; i++ { time.Sleep(10*time.Millisecond) }
	if b.app.modal == nil { return fmt.Errorf("question modal did not open") }
	b.app.OnTerminalInput([]byte("\x1b[B"))
	b.app.OnTerminalInput([]byte{'\r'})
	for _, r := range s { b.app.OnTerminalInput([]byte(string(r))) }
	b.app.OnTerminalInput([]byte{'\r'})
	return nil
}
func (b *cliBDD) observe(s string) error {
	select {
	case got := <-b.observed:
		if got == nil || len(got.Answers)==0 || len(got.Answers[0])==0 || got.Answers[0][0] != s { return fmt.Errorf("answer = %#v, want %q", got, s) }
		return nil
	case <-time.After(3*time.Second): return fmt.Errorf("stub turn did not receive question answer")
	}
}
var _ = strings.Contains
var _ = time.Second
var _ = tui.StripTerminalSequences
