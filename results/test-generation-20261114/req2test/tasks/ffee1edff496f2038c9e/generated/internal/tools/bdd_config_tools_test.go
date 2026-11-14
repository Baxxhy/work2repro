package tools

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/tooling"
)

type configBDDState struct {
	t        *testing.T
	env      *tooling.Env
	registry *tooling.Registry
	changes  string
}

func (s *configBDDState) activeConfig(doc *godog.DocString) error {
	dir := s.t.TempDir()
	path := filepath.Join(dir, "config.yaml")
	if err := os.WriteFile(path, []byte(doc.Content), 0o600); err != nil {
		return err
	}
	s.env = &tooling.Env{SessionID: "bdd-config", SessionDir: dir, ConfigPath: path, ConfigHome: dir, ConfigCWD: dir}
	s.registry = NewRegistry()
	return nil
}

func (s *configBDDState) hotReload() {}

func (s *configBDDState) stage(doc *godog.DocString) error {
	commands := make([]string, 0)
	for _, line := range strings.Split(doc.Content, "\n") {
		if line = strings.TrimSpace(line); line != "" {
			commands = append(commands, line)
		}
	}
	args, err := json.Marshal(map[string]interface{}{"commands": commands})
	if err != nil {
		return err
	}
	_, err = s.registry.Execute(context.Background(), "config_set", string(args), s.env)
	return err
}

func (s *configBDDState) listChanges() error {
	out, err := s.registry.Execute(context.Background(), "config_changes", "{}", s.env)
	s.changes = out
	return err
}

func (s *configBDDState) changesShow(command string) error {
	if !strings.Contains(s.changes, command) {
		return fmt.Errorf("change list %q does not contain %q", s.changes, command)
	}
	return nil
}

func InitializeConfigToolsScenario(sc *godog.ScenarioContext, state *configBDDState) {
	sc.Given(`^an active Coddy config:$`, state.activeConfig)
	sc.Step(`^the session can hot-reload its runtime configuration$`, state.hotReload)
	sc.When(`^the agent stages config commands:$`, state.stage)
	sc.When(`^the agent lists config changes$`, state.listChanges)
	sc.Then(`^the change list shows "([^"]*)"$`, state.changesShow)
}

func TestConfigToolsFeature(t *testing.T) {
	_, file, _, _ := runtime.Caller(0)
	feature := filepath.Join(filepath.Dir(file), "..", "..", "features", "config_tools.feature")
	state := &configBDDState{t: t}
	suite := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			InitializeConfigToolsScenario(sc, state)
		},
		Options: &godog.Options{Format: "pretty", Paths: []string{feature}},
	}
	if suite.Run() != 0 {
		t.Fatal("Godog feature failed")
	}
}
