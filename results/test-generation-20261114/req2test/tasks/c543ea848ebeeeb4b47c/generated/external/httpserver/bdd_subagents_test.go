//go:build http

package httpserver

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type subagentsBDD struct {
	t *testing.T
	root, home, sessionID string
	server *httptest.Server
	catalog []map[string]interface{}
}

func TestSubagentsHTTPFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			b := &subagentsBDD{t: t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				return ctx, b.start()
			})
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
				if b.server != nil { b.server.Close() }
				return ctx, nil
			})
			sc.Step(`^a running coddy http server with a session$`, b.running)
			sc.Step(`^the server workspace has a subagent definition "([^"]*)" under \.coddy/agents$`, b.definition)
			sc.Step(`^I GET the subagent catalog for the server workspace$`, b.getCatalog)
			sc.Step(`^the catalog names the built-in "([^"]*)"$`, b.builtin)
			sc.Step(`^the catalog names "([^"]*)" with scope "([^"]*)" needing approval$`, b.needsApproval)
			sc.Step(`^I POST trust for the subagent "([^"]*)" in the server workspace$`, b.trust)
			sc.Step(`^the catalog names "([^"]*)" as trusted$`, b.trusted)
		},
		Options: &godog.Options{Format: "progress"},
	}
	if suite.Run() != 0 { t.Fatal("godog suite failed") }
}

func (b *subagentsBDD) start() error {
	b.root = b.t.TempDir()
	b.home = filepath.Join(b.root, "home")
	sessions := filepath.Join(b.root, "sessions")
	for _, p := range []string{b.home, sessions} {
		if err := os.MkdirAll(p, 0755); err != nil { return err }
	}
	cfg := &config.Config{
		Paths: config.Paths{Home: b.home, CWD: b.root},
		Models: []config.ModelEntry{{Model:"openai/gpt-4o", MaxTokens:100, Temperature:.2}},
		Agent: config.Agent{Model:"openai/gpt-4o"},
		Subagents: config.Subagents{Dirs: config.DefaultSubagentDirs(), ProjectTrust: config.SubagentsProjectTrustAsk},
	}
	runner := func(context.Context, *session.State, []acp.ContentBlock, acp.UpdateSender) (string,error) { return "",nil }
	store := &session.FileStore{Root:sessions}
	mgr := session.NewManager(cfg, noopSender{}, runner, slog.Default(), b.root, store)
	srv := New(cfg,mgr,slog.Default(),b.root)
	res, err := mgr.HandleSessionNew(context.Background(), acp.SessionNewParams{CWD:b.root})
	if err != nil { return err }
	b.sessionID = res.SessionID
	b.server = httptest.NewServer(srv.Handler())
	b.t.Cleanup(srv.Drain)
	return nil
}
func (b *subagentsBDD) running() error { if b.server == nil { return fmt.Errorf("server not running") }; return nil }
func (b *subagentsBDD) definition(name string) error {
	dir := filepath.Join(b.root, ".coddy", "agents")
	if err := os.MkdirAll(dir,0755); err != nil { return err }
	return os.WriteFile(filepath.Join(dir,name+".md"), []byte("---\ndescription: Review changes\n---\nReview the changes carefully.\n"),0644)
}
func (b *subagentsBDD) request(method,path string, body interface{}) (map[string]interface{},error) {
	var r *http.Request
	var err error
	if body == nil { r,err=http.NewRequest(method,b.server.URL+path,nil) } else {
		raw,e:=json.Marshal(body); if e!=nil{return nil,e}
		r,err=http.NewRequest(method,b.server.URL+path,bytesReader(raw))
	}
	if err!=nil{return nil,err}
	r.Header.Set("Content-Type","application/json")
	resp,err:=http.DefaultClient.Do(r); if err!=nil{return nil,err}; defer resp.Body.Close()
	var result map[string]interface{}
	if err=json.NewDecoder(resp.Body).Decode(&result); err!=nil{return nil,err}
	if resp.StatusCode<200||resp.StatusCode>=300{return nil,fmt.Errorf("%s %s: %d %v",method,path,resp.StatusCode,result)}
	return result,nil
}
func bytesReader(b []byte) *bytes.Reader { return bytes.NewReader(b) }
func (b *subagentsBDD) getCatalog() error {
	result,err:=b.request(http.MethodGet,"/coddy/subagents?cwd="+url.QueryEscape(b.root),nil); if err!=nil{return err}
	rows,ok:=result["items"].([]interface{}); if !ok { rows,ok=result["data"].([]interface{}) }; if !ok { rows,ok=result["agents"].([]interface{}) }; if !ok { rows,ok=result["subagents"].([]interface{}) }
	if !ok { return fmt.Errorf("catalog response has no entries: %v",result) }
	b.catalog=nil
	for _, row:=range rows { if m,ok:=row.(map[string]interface{});ok { b.catalog=append(b.catalog,m) } }
	return nil
}
func (b *subagentsBDD) entry(name string) (map[string]interface{},error) {
	for _,row:=range b.catalog { if row["name"]==name{return row,nil} }; return nil,fmt.Errorf("catalog has no %q: %v",name,b.catalog)
}
func (b *subagentsBDD) builtin(name string) error { row,e:=b.entry(name); if e!=nil{return e}; if row["builtin"]!=true{return fmt.Errorf("%q is not builtin: %v",name,row)}; return nil }
func (b *subagentsBDD) needsApproval(name,scope string) error {
	row,e:=b.entry(name); if e!=nil{return e}
	if row["scope"]!=scope || row["needs_approval"]!=true { return fmt.Errorf("%q catalog entry = %v",name,row) }; return nil
}
func (b *subagentsBDD) trust(name string) error {
	_,err:=b.request(http.MethodPost,"/coddy/subagents/"+url.PathEscape(name)+"/trust",map[string]string{"cwd":b.root}); return err
}
func (b *subagentsBDD) trusted(name string) error {
	row,e:=b.entry(name); if e!=nil{return e}
	if row["trusted"]!=true { return fmt.Errorf("%q is not trusted: %v",name,row) }; return nil
}
