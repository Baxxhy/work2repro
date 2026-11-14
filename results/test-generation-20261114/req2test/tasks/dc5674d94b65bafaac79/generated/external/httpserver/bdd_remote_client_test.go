//go:build http

package httpserver

import (
	"context"
	"fmt"
	"log/slog"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/remote"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type remoteBDD struct {
	t            *testing.T
	server       *httptest.Server
	client       *remote.Handler
	serverToken  string
	clientToken  string
	answer       string
	permission   string
	text         strings.Builder
	sessionID    string
}

func (b *remoteBDD) reset() {
	b.serverToken, b.clientToken = "secret-token", "secret-token"
	b.answer, b.permission, b.sessionID = "", "", ""
	b.text.Reset()
	if b.server != nil {
		b.server.Close()
		b.server = nil
	}
}

func (b *remoteBDD) startServer(token string) error {
	b.serverToken = token
	cfg := &config.Config{Agent: config.Agent{Model: "openai/gpt-4o"}}
	runner := func(ctx context.Context, st *session.State, _ []acp.ContentBlock, sender acp.UpdateSender) (string, error) {
		if b.permission != "" {
			_, err := sender.RequestPermission(ctx, acp.PermissionRequestParams{
				SessionID: st.ID,
				ToolCall: acp.PermissionToolCall{ToolCallID: "bdd-tool", Title: "Run tool", Kind: "execute", Status: "pending"},
				Options: []acp.PermissionOption{{OptionID: "allow", Name: "Allow", Kind: "allow_once"}, {OptionID: "reject", Name: "Reject", Kind: "reject_once"}},
			})
			if err != nil {
				return "", err
			}
		}
		st.AddMessage(llm.Message{Role: llm.RoleAssistant, Content: b.answer})
		if err := sender.SendSessionUpdate(st.ID, acp.MessageChunkUpdate{
			SessionUpdate: acp.UpdateTypeAgentMessageChunk,
			Content:       acp.ContentBlock{Type: acp.ContentTypeText, Text: b.answer},
		}); err != nil {
			return "", err
		}
		return string(acp.StopReasonEndTurn), nil
	}
	mgr := session.NewManager(cfg, noopSender{}, runner, slog.Default(), b.t.TempDir(), nil)
	srv := New(cfg, mgr, slog.Default(), b.t.TempDir())
	srv.SetExtraAuthTokens([]string{token})
	b.server = httptest.NewServer(srv.Handler())
	return nil
}

func (b *remoteBDD) connectClient(token string) error {
	b.clientToken = token
	h, err := remote.NewHandler(remote.Options{BaseURL: b.server.URL, Token: token})
	if err != nil {
		return err
	}
	sender := &remoteBDDClientSender{b: b}
	h.SetServer(sender)
	b.client = h
	return nil
}

type remoteBDDClientSender struct{ b *remoteBDD }

func (s *remoteBDDClientSender) SendSessionUpdate(_ string, update interface{}) error {
	if chunk, ok := update.(acp.MessageChunkUpdate); ok && chunk.Content.Type == acp.ContentTypeText {
		s.b.text.WriteString(chunk.Content.Text)
	}
	return nil
}
func (s *remoteBDDClientSender) RequestPermission(_ context.Context, _ acp.PermissionRequestParams) (*acp.PermissionResult, error) {
	return &acp.PermissionResult{Outcome: s.b.permission, OptionID: s.b.permission}, nil
}
func (*remoteBDDClientSender) RequestQuestion(context.Context, acp.QuestionRequestParams) (*acp.QuestionResult, error) {
	return &acp.QuestionResult{}, nil
}

func (b *remoteBDD) startSession() error {
	result, err := b.client.HandleSessionNew(context.Background(), acp.SessionNewParams{CWD: b.t.TempDir()})
	if err == nil {
		b.sessionID = result.SessionID
	}
	return err
}

func (b *remoteBDD) sendPrompt(prompt string) error {
	_, err := b.client.HandleSessionPromptWithSender(context.Background(), acp.SessionPromptParams{
		SessionID: b.sessionID,
		Prompt: []acp.ContentBlock{{Type: acp.ContentTypeText, Text: prompt}},
	}, &remoteBDDClientSender{b: b}, nil)
	return err
}

func initializeRemoteClientScenario(sc *godog.ScenarioContext) {
	b := &remoteBDD{}
	sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
		b.reset()
		return ctx, nil
	})
	sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
		if b.server != nil {
			b.server.Close()
		}
		return ctx, nil
	})
	sc.Given(`a remote coddy server protected by the token {string}`, func(token string) error {
		return b.startServer(token)
	})
	sc.Given(`a remote client connected with the token {string}`, func(token string) error {
		return b.connectClient(token)
	})
	sc.Given(`the remote agent asks permission before replying {string}`, func(answer string) error {
		b.permission = "allow"
		b.answer = answer
		return nil
	})
	sc.Given(`the client answers permissions with {string}`, func(answer string) error {
		b.permission = answer
		return nil
	})
	sc.Given(`the client starts a session`, b.startSession)
	sc.When(`the client sends the prompt {string}`, func(prompt string) error {
		if err := b.sendPrompt(prompt); err != nil {
			return fmt.Errorf("send remote prompt: %w", err)
		}
		return nil
	})
	sc.Then(`the client receives the streamed text {string}`, func(want string) error {
		if got := b.text.String(); got != want {
			return fmt.Errorf("streamed text = %q, want %q", got, want)
		}
		return nil
	})
}

func TestRemoteClientFeature(t *testing.T) {
	suite := godog.TestSuite{
		Name:                 "remote-client",
		ScenarioInitializer: initializeRemoteClientScenario,
		Options: &godog.Options{
			Paths: []string{"features/remote_client.feature"},
		},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("godog suite failed with status %d", status)
	}
}
