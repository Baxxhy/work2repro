//go:build http

package httpserver

import (
	"context"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type compactBDD struct {
	t *testing.T
	mgr *session.Manager
	srv *Server
	ts *httptest.Server
	sid string
	response string
	stream string
}

func (b *compactBDD) runningServer() error {
	// The normal runner is intentionally unused for /compact; the command path
	// constructs an Agent and obtains its summarizer from providerFactory.
	runner := func(context.Context, *session.State, []acp.ContentBlock, acp.UpdateSender) (string, error) {
		return "", fmt.Errorf("unexpected ordinary agent turn")
	}
	b.mgr, b.srv, _ = testHTTPServerPersistWithRunner(b.t, runner)
	cfg := b.srv.activeCfg()
	cfg.Compaction = config.Compaction{Enabled: compactBool(true), KeepRecentTurns: compactInt(1)}
	b.srv.providerFactory = func(*config.Config) (llm.Provider, error) { return compactBDDProvider{}, nil }
	b.srv.agentProviderFactory = func(llm.ProviderInput) (llm.Provider, error) { return compactBDDProvider{}, nil }
	b.ts = httptest.NewServer(b.srv.Handler())
	return nil
}

func compactBool(v bool) *bool { return &v }
func compactInt(v int) *int { return &v }

type compactBDDProvider struct{}
func (compactBDDProvider) Complete(context.Context, []llm.Message, []llm.ToolDefinition) (*llm.Response, error) {
	return &llm.Response{Content: "A concise summary of the earlier exchanges.", StopReason: "end_turn"}, nil
}
func (compactBDDProvider) Stream(context.Context, []llm.Message, []llm.ToolDefinition, func(llm.StreamChunk)) (*llm.Response, error) {
	return &llm.Response{Content: "Compaction complete.", StopReason: "end_turn"}, nil
}

func (b *compactBDD) fourExchanges() error {
	sn, err := b.mgr.HandleSessionNew(context.Background(), acp.SessionNewParams{CWD: "/tmp"})
	if err != nil { return err }
	b.sid = sn.SessionID
	st := b.mgr.SessionByID(b.sid)
	for i := 1; i <= 4; i++ {
		st.AddMessage(llm.Message{Role: llm.RoleUser, Content: fmt.Sprintf("original question %d", i)})
		st.AddMessage(llm.Message{Role: llm.RoleAssistant, Content: fmt.Sprintf("original answer %d", i)})
	}
	return nil
}

func (b *compactBDD) sendCompact() error {
	req, err := http.NewRequest(http.MethodPost, b.ts.URL+"/v1/responses", strings.NewReader(`{"model":"agent","input":"/compact","stream":true}`))
	if err != nil { return err }
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-Coddy-Session-ID", b.sid)
	res, err := b.ts.Client().Do(req)
	if err != nil { return err }
	defer res.Body.Close()
	body, err := io.ReadAll(res.Body)
	if err != nil { return err }
	if res.StatusCode != http.StatusOK { return fmt.Errorf("responses status %d: %s", res.StatusCode, body) }
	b.stream = string(body)
	b.response = string(body)
	return nil
}

func (b *compactBDD) responseConfirms() error {
	if !strings.Contains(strings.ToLower(b.response), "compact") { return fmt.Errorf("response does not confirm compaction: %s", b.response) }
	return nil
}
func (b *compactBDD) summaryRow() error {
	for _, m := range b.mgr.SessionByID(b.sid).GetMessages() { if m.CompactionSummary { return nil } }
	return fmt.Errorf("transcript has no compaction summary row")
}
func (b *compactBDD) exchangesRemain() error {
	text := ""
	for _, m := range b.mgr.SessionByID(b.sid).GetMessages() { text += m.Content + "\n" }
	for i := 1; i <= 4; i++ { if !strings.Contains(text, fmt.Sprintf("original question %d", i)) || !strings.Contains(text, fmt.Sprintf("original answer %d", i)) { return fmt.Errorf("exchange %d missing from transcript", i) } }
	return nil
}
func (b *compactBDD) commandInTranscript() error {
	for _, m := range b.mgr.SessionByID(b.sid).GetMessages() { if strings.Contains(m.Content, "/compact") { return nil } }
	return fmt.Errorf("/compact absent from transcript")
}
func (b *compactBDD) smallerUsage() error {
	if !strings.Contains(b.stream, "usage") { return fmt.Errorf("stream has no usage metadata: %s", b.stream) }
	return nil
}
func (b *compactBDD) statsMatch() error {
	st := b.mgr.SessionByID(b.sid)
	if len(session.MessagesForLLM(st.GetMessages())) >= len(st.GetMessages()) { return fmt.Errorf("LLM context was not compacted") }
	return nil
}

func TestContextCompactionCommandFeature(t *testing.T) {
	b := &compactBDD{t:t}
	suite := godog.TestSuite{
		Name: "context-compaction-command",
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) { return ctx, nil })
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
				if b.ts != nil { b.ts.Close() }
				return ctx, nil
			})
			sc.Given(`^a running coddy HTTP server with a summarizing agent$`, b.runningServer)
			sc.Given(`^an HTTP session with 4 completed exchanges$`, b.fourExchanges)
			sc.When(`^the user sends "([^"]*)" as a prompt$`, func(command string) error {
				if command != "/compact" { return fmt.Errorf("unexpected prompt %q", command) }
				return b.sendCompact()
			})
			sc.Then(`^the prompt response confirms the compaction$`, b.responseConfirms)
			sc.Then(`^the session transcript contains a compaction summary row$`, b.summaryRow)
			sc.Then(`^the session transcript still contains all 4 original exchanges$`, b.exchangesRemain)
			sc.Then(`^the "([^"]*)" command is part of the transcript$`, func(command string) error { return b.commandInTranscript() })
			sc.Then(`^the HTTP stream reports the smaller context usage$`, b.smallerUsage)
			sc.Then(`^HTTP session stats match the compacted LLM context$`, b.statsMatch)
		},
		}
	if status := suite.Run(); status != 0 { t.Fatalf("godog suite failed with status %d", status) }
}
