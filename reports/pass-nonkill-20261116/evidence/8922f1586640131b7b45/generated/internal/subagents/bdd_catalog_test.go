package subagents

import (
	"bytes"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/cucumber/godog"
)

type catalogFeatureState struct {
	home      string
	workspace string
	entries   []CatalogEntry
	listing   string
}

func TestSubagentsCatalogFeature(t *testing.T) {
	suite := godog.TestSuite{
		Name:                "subagents-catalog",
		ScenarioInitializer: initializeSubagentsCatalogScenario,
		Options:             &godog.Options{Paths: []string{"../../features/subagents_catalog.feature"}},
	}
	if suite.Run() != 0 {
		t.Fatal("subagents catalog feature failed")
	}
}

func initializeSubagentsCatalogScenario(ctx *godog.ScenarioContext) {
	state := &catalogFeatureState{}

	ctx.Step(`^a coddy home with a subagent definition "([^"]*)" described as "([^"]*)"$`, func(name, description string) error {
		if state.home == "" {
			root, err := os.MkdirTemp("", "coddy-subagents-bdd-")
			if err != nil {
				return err
			}
			state.home = filepath.Join(root, "home")
			if err := os.MkdirAll(filepath.Join(state.home, "agents"), 0o755); err != nil {
				return err
			}
		}
		return writeCatalogDefinition(filepath.Join(state.home, "agents"), name, description)
	})

	ctx.Step(`^a workspace with a subagent definition "([^"]*)" under \.coddy/agents described as "([^"]*)"$`, func(name, description string) error {
		if state.workspace == "" {
			root, err := os.MkdirTemp("", "coddy-subagents-workspace-")
			if err != nil {
				return err
			}
			state.workspace = root
		}
		return writeCatalogDefinition(filepath.Join(state.workspace, ".coddy", "agents"), name, description)
	})

	ctx.Step(`^I list the subagent catalog for that workspace$`, func() error {
		if state.home == "" || state.workspace == "" {
			return fmt.Errorf("home and workspace must be set up before listing")
		}
		loader := NewLoader([]string{"${CODDY_HOME}/agents", "${CWD}/.coddy/agents"}, "ask")
		defs := loader.Load(state.workspace, state.home)
		store := NewTrustStore(state.home)
		state.entries = BuildCatalog(defs, "ask", CanonicalWorkspace(state.workspace), store)
		var out bytes.Buffer
		WriteListing(&out, state.entries)
		state.listing = out.String()
		return nil
	})

	ctx.Step(`^the listing describes "([^"]*)" as "([^"]*)"$`, func(name, description string) error {
		for _, entry := range state.entries {
			if entry.Name == name {
				if entry.Description != description {
					return fmt.Errorf("%q description = %q, want %q; listing:\n%s", name, entry.Description, description, state.listing)
				}
				if !strings.Contains(state.listing, description) {
					return fmt.Errorf("listing does not contain description %q:\n%s", description, state.listing)
				}
				return nil
			}
		}
		return fmt.Errorf("listing has no entry named %q:\n%s", name, state.listing)
	})
}

func writeCatalogDefinition(dir, name, description string) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	content := fmt.Sprintf("---\nname: %s\ndescription: %s\n---\nRole for %s.\n", name, description, name)
	return os.WriteFile(filepath.Join(dir, name+".md"), []byte(content), 0o644)
}
