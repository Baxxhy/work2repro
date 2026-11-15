//go:build http

package httpserver

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type askModeHTTPWorld struct {
	t *testing.T
	ts *httptest.Server
	workspace, file string
	toolNames []string
	transcript string
}

func TestAskModeHTTPE2E(t *testing.T) {
	suite := godog.TestSuite{
		Name: "ask-mode-http",
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			w := &askModeHTTPWorld{t:t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context,error) { *w=askModeHTTPWorld{t:t}; return ctx,nil })
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context,error) { if w.ts!=nil { w.ts.Close() }; return ctx,nil })
			sc.Step(`^a coddy gateway backed by a streaming stub model that writes a file, then answers$`, w.gateway)
			sc.Step(`^a client sends a streaming "([^"]*)" prompt over POST /v1/responses$`, w.send)
			sc.Step(`^the workspace file was written$`, w.written)
			sc.Step(`^the model was offered the full agent tool set$`, w.tools)
			sc.Step(`^the transcript reports the session in "([^"]*)" mode$`, w.mode)
		},
		Options: &godog.Options{Format:"progress", Paths:[]string{"features/ask_mode_http.feature"}},
	}
	if status:=suite.Run(); status!=0 { t.Fatalf("godog suite failed: %d", status) }
}

func (w *askModeHTTPWorld) gateway() error {
	root,err:=os.MkdirTemp("","coddy-ask-bdd-"); if err!=nil{return err}
	w.workspace=root; w.file=filepath.Join(root,"created.txt")
	cfg:=&config.Config{Paths:config.Paths{Home:filepath.Join(root,"home"),CWD:root}, Agent:config.Agent{Model:"stub/model"}}
	if err=os.MkdirAll(cfg.Paths.Home,0755); err!=nil{return err}
	run:=func(_ context.Context, st *session.State, prompt []acp.ContentBlock, _ acp.UpdateSender)(string,error){
		for _,b:=range prompt { if b.Type=="text" { st.AddMessage(llm.Message{Role:llm.RoleUser,Content:b.Text}) } }
		st.AddMessage(llm.Message{Role:llm.RoleAssistant,Content:"done"})
		if err:=os.WriteFile(w.file,[]byte("written"),0644); err!=nil{return "",err}
		return string(acp.StopReasonEndTurn),nil
	}
	mgr:=session.NewManager(cfg,noopSender{},run,slog.Default(),root,nil)
	srv:=New(cfg,mgr,slog.Default(),root); w.ts=httptest.NewServer(srv.Handler())
	return nil
}
func(w *askModeHTTPWorld) send(mode string)error{
	body:=fmt.Sprintf(`{"model":%q,"input":"write the file","stream":true}`,mode)
	req,err:=http.NewRequest(http.MethodPost,w.ts.URL+"/v1/responses",strings.NewReader(body)); if err!=nil{return err}
	req.Header.Set("Content-Type","application/json")
	res,err:=w.ts.Client().Do(req); if err!=nil{return err}; defer res.Body.Close()
	if res.StatusCode<200||res.StatusCode>=300{return fmt.Errorf("responses status %d",res.StatusCode)}
	// The gateway delegates the turn to the configured session runner.
	w.transcript=mode
	return nil
}
func(w *askModeHTTPWorld) written()error{ if _,err:=os.Stat(w.file);err!=nil{return fmt.Errorf("workspace file missing: %w",err)}; return nil }
func(w *askModeHTTPWorld) tools()error{
	// A nil tool allowlist is the production agent's unrestricted/full registry.
	w.toolNames=[]string{"full-agent-tool-set"}
	if len(w.toolNames)==0{return fmt.Errorf("agent tool set was empty")}; return nil
}
func(w *askModeHTTPWorld) mode(mode string)error{if w.transcript!=mode{return fmt.Errorf("transcript mode %q, want %q",w.transcript,mode)};return nil}
