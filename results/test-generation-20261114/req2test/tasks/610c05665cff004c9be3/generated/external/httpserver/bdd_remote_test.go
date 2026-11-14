//go:build http

package httpserver

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
)

type remoteBDDState struct {
	t       *testing.T
	server  *httptest.Server
	token   string
	status  int
	body    []byte
}

func TestRemoteAPIFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			state := &remoteBDDState{t: t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				return context.WithValue(ctx, remoteBDDStateKey{}, state), nil
			})
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
				if state.server != nil {
					state.server.Close()
				}
				return ctx, nil
			})
			sc.Step(`^an authenticated coddy HTTP server with token "([^"]*)"$`, func(token string) error {
				state.token = token
				cfg := &config.Config{}
				cfg.HTTPServer.AuthToken = token
				srv := New(cfg, nil, slog.Default(), t.TempDir())
				state.server = httptest.NewServer(srv.Handler())
				return nil
			})
			sc.Step(`^the client presents the token$`, func() error { return nil })
			sc.Step(`^I request the server config$`, func() error {
				req, err := http.NewRequest(http.MethodGet, state.server.URL+"/coddy/config", nil)
				if err != nil {
					return err
				}
				req.Header.Set("Authorization", "Bearer "+state.token)
				resp, err := http.DefaultClient.Do(req)
				if err != nil {
					return err
				}
				defer resp.Body.Close()
				state.status = resp.StatusCode
				state.body, err = io.ReadAll(resp.Body)
				return err
			})
			sc.Step(`^the request succeeds$`, func() error {
				if state.status < 200 || state.status >= 300 {
					return fmt.Errorf("request status %d: %s", state.status, state.body)
				}
				return nil
			})
			sc.Step(`^the config response hides the auth token$`, func() error {
				if strings.Contains(string(state.body), state.token) {
					return fmt.Errorf("config response exposed bearer token")
				}
				return nil
			})
			sc.Step(`^the config response reports authentication is configured$`, func() error {
				var response map[string]interface{}
				if err := json.Unmarshal(state.body, &response); err != nil {
					return err
				}
				httpserver, _ := response["httpserver"].(map[string]interface{})
				if httpserver["auth_configured"] != true {
					return fmt.Errorf("httpserver.auth_configured = %v, want true (response %s)", httpserver["auth_configured"], state.body)
				}
				return nil
			})
		},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed with status %d", status)
	}
}

type remoteBDDStateKey struct{}
