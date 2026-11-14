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
	"reflect"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/config"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type reasoningLevelsBDD struct {
	server *httptest.Server
	resp   int
	levels []string
	detect bool
}

func TestReasoningLevelsFetchFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			state := &reasoningLevelsBDD{}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				*state = reasoningLevelsBDD{}
				return ctx, nil
			})
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
				if state.server != nil {
					state.server.Close()
				}
				return ctx, nil
			})
			sc.Step(`^a coddy gateway with an? "([^"]+)" provider named "([^"]+)"$`, func(providerType, name string) error {
				cfg := &config.Config{
					Agent: config.Agent{Model: name + "/qwen3.8-27b"},
					Providers: []config.ProviderConfig{{Name: name, Type: providerType}},
				}
				runner := func(context.Context, *session.State, []acp.ContentBlock, acp.UpdateSender) (string, error) {
					return "", nil
				}
				mgr := session.NewManager(cfg, noopSender{}, runner, slog.Default(), "/tmp", nil)
				srv := New(cfg, mgr, slog.Default(), "/tmp")
				state.server = httptest.NewServer(srv.Handler())
				return nil
			})
			sc.Step(`^the settings form fetches the reasoning levels for "([^"]+)"$`, func(model string) error {
				if state.server == nil {
					return fmt.Errorf("gateway has not been started")
				}
				res, err := http.Get(state.server.URL + "/coddy/config/reasoning-levels?model=" + model)
				if err != nil {
					return err
				}
				defer res.Body.Close()
				state.resp = res.StatusCode
				data, err := io.ReadAll(res.Body)
				if err != nil {
					return err
				}
				var body struct {
					Levels   []string `json:"levels"`
					Detected bool     `json:"detected"`
				}
				if err := json.Unmarshal(data, &body); err != nil {
					return err
				}
				state.levels, state.detect = body.Levels, body.Detected
				return nil
			})
			sc.Step(`^the gateway answers with the levels "([^"]+)"$`, func(want string) error {
				expected := strings.Split(want, ",")
				if state.resp != http.StatusOK || !reflect.DeepEqual(state.levels, expected) {
					return fmt.Errorf("response status=%d levels=%v; want status=%d levels=%v", state.resp, state.levels, http.StatusOK, expected)
				}
				return nil
			})
			sc.Step(`^the answer reports the levels as detected$`, func() error {
				if !state.detect {
					return fmt.Errorf("reasoning levels were not reported as detected")
				}
				return nil
			})
		},
		Options: &godog.Options{Format: "pretty", Paths: []string{"../../features/reasoning_levels_fetch.feature"}},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("godog suite failed with status %d", status)
	}
}
