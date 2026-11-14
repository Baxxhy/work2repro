package shell

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"testing"
	"time"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/platform"
)

func TestForegroundTimeoutAdoptionFeature(t *testing.T) {
	state := newForegroundBDDState(t)
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				state.answer = ""
				return ctx, nil
			})
			sc.Given(`a session with an empty background task pool`, func() error {
				if got := state.env.Background.List(state.env.SessionID); len(got) != 0 {
					return fmt.Errorf("background pool is not empty: %d tasks", len(got))
				}
				return nil
			})
			sc.When(`I run a command in the foreground that complains {string} on its error stream and keeps running past its 2 second timeout`, func(message string) error {
				command, err := foregroundComplaintCommand(platform.CurrentShell(), message)
				if err != nil {
					return err
				}
				args, err := json.Marshal(runCommandArgs{Command: command, TimeoutSeconds: 2})
				if err != nil {
					return err
				}
				began := time.Now()
				state.answer, err = executeRunCommandWithShell(context.Background(), string(args), state.env, platform.CurrentShell())
				if err != nil {
					return err
				}
				if time.Since(began) > 20*time.Second {
					return fmt.Errorf("run_command took longer than 20 seconds")
				}
				return nil
			})
			sc.Then(`the answer contains {string}`, func(text string) error {
				if !strings.Contains(state.answer, text) {
					return fmt.Errorf("answer %q does not contain %q", state.answer, text)
				}
				return nil
			})
		},
		Options: &godog.Options{},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed with status %d", status)
	}
}
