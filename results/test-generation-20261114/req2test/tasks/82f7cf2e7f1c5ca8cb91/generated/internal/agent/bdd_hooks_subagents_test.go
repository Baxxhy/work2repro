package agent

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/hooks"
	"github.com/EvilFreelancer/coddy-agent/internal/hooks/hooktest"
	"github.com/EvilFreelancer/coddy-agent/internal/llm"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
)

type hookSubagentBDD struct {
	t *testing.T
	r *subagentRig
	task string
	result string
	childTask string
}

type hooksBDDProvider struct { calls []llm.ToolCall; answer string; saw string; once bool }
func (p *hooksBDDProvider) Complete(ctx context.Context, m []llm.Message, d []llm.ToolDefinition) (*llm.Response,error) { return p.Stream(ctx,m,d,func(llm.StreamChunk){}) }
func (p *hooksBDDProvider) Stream(_ context.Context, m []llm.Message, _ []llm.ToolDefinition, chunk func(llm.StreamChunk)) (*llm.Response,error) {
	if len(p.calls)>0 { if !p.once { p.once=true; return &llm.Response{ToolCalls:p.calls,StopReason:"tool_use"},nil }; chunk(llm.StreamChunk{TextDelta:p.answer}); return &llm.Response{Content:p.answer,StopReason:"end_turn"},nil }
	for _,x:=range m { if strings.Contains(x.Content,"answer in one line") { p.saw=x.Content } }
	chunk(llm.StreamChunk{TextDelta:p.answer}); return &llm.Response{Content:p.answer,StopReason:"end_turn"},nil
}

func TestHooksSubagentsFeature(t *testing.T) {
	s := godog.TestSuite{
		ScenarioInitializer: func(sc *godog.ScenarioContext) {
			b := &hookSubagentBDD{t:t}
			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context,error) { b.t=t; return ctx,nil })
			sc.Step(`^a workspace with a subagent definition "([^"]*)" under \.coddy/agents$`, b.definition)
			sc.Step(`^the workspace definition "([^"]*)" is approved for that workspace$`, b.approve)
			sc.Step(`^the operator's hooks\.json has a SubagentStart hook for "([^"]*)" that adds the context "([^"]*)"$`, b.hook)
			sc.Step(`^a parent agent session in that workspace$`, b.parent)
			sc.Step(`^the parent model spawns "([^"]*)" in the foreground and the child answers "([^"]*)"$`, b.spawn)
			sc.Step(`^the child model's task carried the context "([^"]*)"$`, b.context)
			sc.Step(`^the spawn_agent tool result contains "([^"]*)"$`, b.report)
		},
		Options: &godog.Options{Format:"pretty", Paths:[]string{"features/hooks_subagents.feature"}, Tags:"@subagent"},
	}
	if status:=s.Run(); status!=0 { t.Fatalf("godog suite failed: %d",status) }
}

func (b *hookSubagentBDD) definition(name string) error { b.r=newSubagentRig(b.t,nil); b.r.writeDefinition(name,""); return nil }
func (b *hookSubagentBDD) approve(name string) error { b.r.approve(name); return nil }
func (b *hookSubagentBDD) hook(name, context string) error {
	dir:=filepath.Join(b.r.home,"hooks.json")
	return hooktest.Write(dir,hooktest.Entry{Event:hooks.EventSubagentStart,Matcher:name,Handlers:[]hooks.Handler{hooktest.Handler("context",context)}})
}
func (b *hookSubagentBDD) parent() error { return nil }
func (b *hookSubagentBDD) spawn(name, answer string) error {
	child:=&hooksBDDProvider{answer:answer}
	b.r.setChildProvider(func(*session.State) llm.Provider{return child})
	call:=llm.ToolCall{ID:"spawn-1",Name:"spawn_agent",InputJSON:`{"agent":"`+name+`","prompt":"Review the change","description":"review task","background":false}`}
	parent:=&hooksBDDProvider{calls:[]llm.ToolCall{call},answer:"done"}
	b.r.parentAgent().SetProviderFactory(func(llm.ProviderInput)(llm.Provider,error){return parent,nil})
	out,err:=b.r.parentAgent().Run(context.Background(),[]acp.ContentBlock{{Type:"text",Text:"delegate"}})
	b.result=out
	b.childTask=child.saw
	return err
}
func (b *hookSubagentBDD) context(s string) error { if !strings.Contains(b.childTask,s){return fmt.Errorf("child task %q lacks %q",b.childTask,s)}; return nil }
func (b *hookSubagentBDD) report(s string) error { if !strings.Contains(b.result,s){return fmt.Errorf("result %q lacks %q",b.result,s)}; return nil }
