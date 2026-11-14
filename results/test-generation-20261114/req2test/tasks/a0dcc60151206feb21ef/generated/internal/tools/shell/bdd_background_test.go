package shell

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/EvilFreelancer/coddy-agent/internal/bgtask"
	"github.com/EvilFreelancer/coddy-agent/internal/platform"
	"github.com/EvilFreelancer/coddy-agent/internal/tooling"
	"github.com/cucumber/godog"
)

type backgroundBDD struct {
	env    *tooling.Env
	taskID string
}

func TestBackgroundTasksFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			state := &backgroundBDD{}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				cwd, err := os.MkdirTemp("", "coddy-background-bdd-*")
				if err != nil {
					return ctx, err
				}
				state.env = &tooling.Env{
					SessionID:         fmt.Sprintf("bdd-%d", time.Now().UnixNano()),
					CWD:               cwd,
					BackgroundEnabled: true,
					Background:        bgtask.NewWithRunner(bgtask.Config{}, bgtask.NewCommandRunner()),
				}
				state.taskID = ""
				return ctx, nil
			})
			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context, error) {
				if state.env != nil {
					state.env.Background.StopSession(state.env.SessionID)
					_ = os.RemoveAll(state.env.CWD)
				}
				return ctx, nil
			})

			sc.Given(`a session with an empty background task pool`, func() error {
				if state.env == nil {
					return fmt.Errorf("background session was not initialized")
				}
				if got := state.env.Background.List(state.env.SessionID); len(got) != 0 {
					return fmt.Errorf("task pool is not empty: %d tasks", len(got))
				}
				return nil
			})
			sc.When(`I run a command in the background that sleeps for (\d+) seconds`, func(seconds int) error {
				command, err := sleepCommandForBDD(platform.CurrentShell(), seconds)
				if err != nil {
					return err
				}
				args, err := json.Marshal(runCommandArgs{Command: command, Background: true})
				if err != nil {
					return err
				}
				if _, err = RunCommandTool().Execute(context.Background(), string(args), state.env); err != nil {
					return err
				}
				tasks := state.env.Background.List(state.env.SessionID)
				if len(tasks) != 1 {
					return fmt.Errorf("pool has %d tasks, want one", len(tasks))
				}
				state.taskID = tasks[0].ID
				return nil
			})
			sc.When(`I stop that background task`, func() error {
				if state.taskID == "" {
					return fmt.Errorf("no background task was started")
				}
				args, _ := json.Marshal(struct {
					TaskID string `json:"task_id"`
				}{state.taskID})
				_, err := BackgroundStopTool().Execute(context.Background(), string(args), state.env)
				return err
			})
			sc.Then(`the task is stopped`, func() error {
				snap, err := state.env.Background.Get(state.env.SessionID, state.taskID)
				if err != nil {
					return err
				}
				if snap.Status != bgtask.StatusStopped {
					return fmt.Errorf("task status is %q, want stopped", snap.Status)
				}
				return nil
			})
			sc.Then(`the task is no longer running`, func() error {
				snap, err := state.env.Background.Get(state.env.SessionID, state.taskID)
				if err != nil {
					return err
				}
				if !snap.Status.Finished() {
					return fmt.Errorf("task status is %q, still running", snap.Status)
				}
				return nil
			})
		},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed with status %d", status)
	}
}

func sleepCommandForBDD(commandShell platform.Shell, seconds int) (string, error) {
	switch commandShell.Kind {
	case platform.ShellPwsh, platform.ShellPowerShell:
		return fmt.Sprintf("Start-Sleep -Seconds %d", seconds), nil
	case platform.ShellCmd:
		return fmt.Sprintf("ping -n %d 127.0.0.1 >NUL", seconds+1), nil
	default:
		return fmt.Sprintf("sleep %d", seconds), nil
	}
}

// These command forms are shared by the retained shell tests.
func sleepCommand(kind platform.ShellKind, seconds int) (string, error) {
	return sleepCommandForBDD(platform.Shell{Kind: kind}, seconds)
}

func printCommand(kind platform.ShellKind, text string) (string, error) {
	switch kind {
	case platform.ShellPwsh, platform.ShellPowerShell:
		return "Write-Output " + quotePowerShell(text), nil
	case platform.ShellCmd:
		return "echo " + text, nil
	default:
		return "printf '%s' " + quotePOSIX(text), nil
	}
}

func complainCommand(kind platform.ShellKind, text string) (string, error) {
	switch kind {
	case platform.ShellPwsh, platform.ShellPowerShell:
		return "[Console]::Error.WriteLine(" + quotePowerShell(text) + ")", nil
	case platform.ShellCmd:
		return "echo " + text + " 1>&2", nil
	default:
		return "printf '%s\\n' " + quotePOSIX(text) + " >&2", nil
	}
}

func lastingChildCommand(commandShell platform.Shell, seconds int) (string, error) {
	switch commandShell.Kind {
	case platform.ShellPwsh, platform.ShellPowerShell:
		return fmt.Sprintf("Start-Process -NoNewWindow -FilePath powershell -ArgumentList '-NoProfile','-Command','Start-Sleep -Seconds %d'", seconds), nil
	case platform.ShellCmd:
		return fmt.Sprintf("start \"\" /b ping -n %d 127.0.0.1", seconds+1), nil
	default:
		return fmt.Sprintf("(sleep %d) & wait", seconds), nil
	}
}

func quotePOSIX(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "'\\''") + "'"
}

func quotePowerShell(s string) string {
	return "'" + strings.ReplaceAll(s, "'", "''") + "'"
}
