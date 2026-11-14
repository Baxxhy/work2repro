package agent

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"path/filepath"
	"sync"
	"testing"
	"time"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type limitBDDProvider struct{ mu sync.Mutex; calls int }
func (p *limitBDDProvider) invoke() (*llm.Response,error) {
	p.mu.Lock(); defer p.mu.Unlock(); p.calls++
	if p.calls == 1 { return nil, &llm.QuotaResetError{ResetAt:time.Now().Add(30*time.Second), Delay:30*time.Second, Cause:errors.New("429")} }
	return &llm.Response{Content:"done"},nil
}
func (p *limitBDDProvider) Complete(context.Context, []llm.Message, []llm.ToolDefinition)(*llm.Response,error){ return p.invoke() }
func (p *limitBDDProvider) Stream(_ context.Context, _ []llm.Message, _ []llm.ToolDefinition, _ func(llm.StreamChunk))(*llm.Response,error){ return p.invoke() }

type limitBDDClient struct { cancel context.CancelFunc; once sync.Once }
func (c *limitBDDClient) SendSessionUpdate(_ string, _ interface{}) error { c.once.Do(c.cancel); return nil }
func (*limitBDDClient) RequestPermission(context.Context,acp.PermissionRequestParams)(*acp.PermissionResult,error){return nil,nil}
func (*limitBDDClient) RequestQuestion(context.Context,acp.QuestionRequestParams)(*acp.QuestionResult,error){return nil,nil}

type limitBDDWorld struct { t *testing.T; ag *Agent; state *session.State; provider *limitBDDProvider; client *limitBDDClient; ctx context.Context; cancel context.CancelFunc; started time.Time; result string; err error }
func (w *limitBDDWorld) agent(_ string) error {
	w.t.Helper()
	cfg:=&config.Config{Providers:[]config.ProviderConfig{{Name:"neuraldeep",Type:"neuraldeep",APIKey:"test"}},Models:[]config.ModelEntry{{Model:"neuraldeep/qwen3.8-27b",MaxTokens:100,MaxContextTokens:128000}},Agent:config.Agent{Model:"neuraldeep/qwen3.8-27b"}}
	cfg.Agent.ApplyDefaults()
	w.state=&session.State{ID:"bdd-limit-wait",CWD:w.t.TempDir(),Mode:session.ModeAgent}
	w.provider=&limitBDDProvider{}
	w.client=&limitBDDClient{}
	w.ag=NewAgent(cfg,w.state,w.client,slog.Default())
	w.ag.SetProviderFactory(func(llm.ProviderInput)(llm.Provider,error){return w.provider,nil})
	return nil
}
func (w *limitBDDWorld) enabled() error { w.ag.cfg.Agent.WaitForLimitReset=true; return nil }
func (w *limitBDDWorld) send() error {
	w.ctx,w.cancel=context.WithCancel(context.Background())
	w.client.cancel=w.cancel
	w.started=time.Now()
	go func(){w.result,w.err=w.ag.Run(w.ctx,[]acp.ContentBlock{{Type:acp.ContentTypeText,Text:"hello"}})}()
	return nil
}
func (w *limitBDDWorld) stop() error {
	select { case <-time.After(500*time.Millisecond): return fmt.Errorf("turn did not enter limit wait") ; default: }
	// The provider_usage update is emitted at the start of the wait.
	time.Sleep(20*time.Millisecond)
	w.state.SetUserCancelledTurn()
	w.cancel()
	for time.Since(w.started)<900*time.Millisecond { if w.err!=nil { return nil }; time.Sleep(time.Millisecond) }
	return nil
}
func (w *limitBDDWorld) cancelled(n int) error {
	deadline:=time.Now().Add(time.Second)
	for w.err==nil && time.Now().Before(deadline){time.Sleep(time.Millisecond)}
	if w.provider.calls!=n {return fmt.Errorf("provider calls %d, want %d",w.provider.calls,n)}
	if w.err==nil {return fmt.Errorf("turn did not fail")}
	return nil
}
func (w *limitBDDWorld) fast(ms int) error { if time.Since(w.started)>=time.Duration(ms)*time.Millisecond{return fmt.Errorf("turn took %v",time.Since(w.started))}; return nil }

func TestLLMLimitWaitFeature(t *testing.T) {
	suite:=godog.TestSuite{ScenarioInitializer:func(sc *godog.ScenarioContext){
		w:=&limitBDDWorld{t:t}
		sc.Step(`^an agent whose provider first reports a limit that lifts in 30 s and then answers "done"$`,w.agent)
		sc.Step(`^wait_for_limit_reset is on$`,w.enabled)
		sc.Step(`^the user sends a turn and stops it while it waits$`,func() error {if err:=w.send();err!=nil{return err};return w.stop()})
		sc.Step(`^the turn ends as cancelled after (\d+) provider call$`,w.cancelled)
		sc.Step(`^the turn took less than (\d+) ms$`,w.fast)
	},Options:&godog.Options{Format:"progress",Paths:[]string{filepath.Join("..","..","features","llm_limit_wait.feature")}}}
	if status:=suite.Run();status!=0 { t.Fatal("godog suite failed") }
}
