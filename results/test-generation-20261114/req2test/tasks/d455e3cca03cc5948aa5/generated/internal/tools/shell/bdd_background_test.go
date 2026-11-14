package shell

import (
	"testing"

	"github.com/EvilFreelancer/coddy-agent/internal/bgtask"
	"github.com/EvilFreelancer/coddy-agent/internal/tooling"
)

type foregroundBDDState struct {
	t       *testing.T
	env     *tooling.Env
	answer  string
}

func newForegroundBDDState(t *testing.T) *foregroundBDDState {
	t.Helper()
	cwd := t.TempDir()
	pool := bgtask.NewWithRunner(bgtask.Config{}, bgtask.NewCommandRunner())
	t.Cleanup(func() { pool.StopSession("godog-foreground") })
	return &foregroundBDDState{
		t: t,
		env: &tooling.Env{
			SessionID:         "godog-foreground",
			CWD:               cwd,
			BackgroundEnabled: true,
			Background:        pool,
		},
	}
}
