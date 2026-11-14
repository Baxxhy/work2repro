package agent

import (
	"context"
	"fmt"
	"strings"
	"testing"

	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/cucumber/godog"
)

type bddSubagentWorld struct {
	rig      *subagentRig
	provider *bddCaptureProvider
}

type bddCaptureProvider struct {
	messages []llm.Message
	defs     []llm.ToolDefinition
}

func (p *bddCaptureProvider) Complete(ctx context.Context, m []llm.Message, d []llm.ToolDefinition) (*llm.Response, error) {
	return p.Stream(ctx, m, d, func(llm.StreamChunk) {})
}
func (p *bddCaptureProvider) Stream(_ context.Context, m []llm.Message, d []llm.ToolDefinition, _ func(llm.StreamChunk)) (*llm.Response, error) {
	p.messages = append([]llm.Message(nil), m...)
	p.defs = append([]llm.ToolDefinition(nil), d...)
	return &llm.Response{Content: "Ready.", StopReason: "end_turn"}, nil
}

func TestSubagentsFeature(t *testing.T) {
	suite := godog.TestSuite{
		Name: "subagents",
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			w := &bddSubagentWorld{}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context, error) {
				w.rig = newSubagentRig(t, nil)
				return ctx, nil
			})
			sc.Given(`a workspace with a subagent definition {string} under .coddy/agents`, func(name string) error {
				w.rig.writeDefinition(name, "")
				return nil
			})
			sc.Given(`the workspace definition {string} is approved for that workspace`, func(name string) error {
				w.rig.approve(name)
				return nil
			})
			sc.Given(`a parent agent session in that workspace`, func() error {
				w.provider = &bddCaptureProvider{}
				w.rig.mu.Lock()
				w.rig.childProvider = func(*session.State) llm.Provider { return w.provider }
				w.rig.mu.Unlock()
				return nil
			})
			sc.When(`the parent model receives its first request`, func() error {
				w.rig.parentAgent().SetProviderFactory(func(llm.ProviderInput) (llm.Provider, error) { return w.provider, nil })
				_, err := w.rig.parentAgent().Run(context.Background(), []acp.ContentBlock{{Type: "text", Text: "Please inspect the project."}})
				return err
			})
			sc.Then(`the system prompt lists the subagent {string} with its description`, func(name string) error {
				if w.provider == nil || len(w.provider.messages) == 0 {
					return fmt.Errorf("model received no messages")
				}
				for _, m := range w.provider.messages {
					if strings.Contains(m.Content, name) && strings.Contains(m.Content, "Unit helper "+name+".") {
						return nil
					}
				}
				return fmt.Errorf("system prompt does not list %q and its description", name)
			})
			sc.Then(`the model is offered the spawn_agent tool`, func() error {
				for _, d := range w.provider.defs {
					if d.Name == "spawn_agent" {
						return nil
					}
				}
				return fmt.Errorf("spawn_agent was not offered")
			})
		},
	}
	if status := suite.Run(); status != 0 {
		t.Fatalf("Godog suite failed with status %d", status)
	}
}
