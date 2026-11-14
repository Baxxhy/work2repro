package permission

import (
	"encoding/json"
	"fmt"
	"testing"

	"github.com/cucumber/godog"
	"github.com/EvilFreelancer/coddy-agent/internal/acp"
	"github.com/EvilFreelancer/coddy-agent/internal/session"
	"github.com/EvilFreelancer/coddy-agent/internal/tooling"
)

type acpPermissionAnswersSteps struct {
	state   *session.State
	env     *tooling.Env
	command string
	answer  *acp.PermissionResult
}

func TestACPPermissionAnswersFeature(t *testing.T) {
	suite := godog.TestSuite{
		ScenarioInitializer: func(ctx *godog.ScenarioContext) {
			s := &acpPermissionAnswersSteps{}
			ctx.Step(`^a session with no command grants$`, s.noCommandGrants)
			ctx.Step(`^the agent asks permission to run "([^"]*)"$`, s.askPermission)
			ctx.Step(`^the editor answers "([^"]*)" the way the protocol nests its outcome$`, s.editorAnswers)
			ctx.Step(`^the answer refuses the command$`, s.answerRefuses)
			ctx.Step(`^running "([^"]*)" still needs permission$`, s.stillNeedsPermission)
		},
	}
	if suite.Run() != 0 {
		t.Fatal("Godog feature failed")
	}
}

func (s *acpPermissionAnswersSteps) noCommandGrants() error {
	s.state = &session.State{}
	s.env = &tooling.Env{}
	if len(s.state.GetPermissionCommandGrants()) != 0 {
		return fmt.Errorf("expected no command grants")
	}
	return nil
}

func (s *acpPermissionAnswersSteps) askPermission(command string) error {
	s.command = command
	s.answer = nil
	if CommandAllowedWithSession(s.env, s.state.GetPermissionCommandGrants(), command) {
		return fmt.Errorf("%q unexpectedly does not need permission", command)
	}
	return nil
}

func (s *acpPermissionAnswersSteps) editorAnswers(outcome string) error {
	data, err := json.Marshal(map[string]any{
		"outcome": map[string]string{"outcome": "selected", "optionId": outcome},
	})
	if err != nil {
		return err
	}
	var result acp.PermissionResult
	if err := json.Unmarshal(data, &result); err != nil {
		return err
	}
	s.answer = &result
	return nil
}

func (s *acpPermissionAnswersSteps) answerRefuses() error {
	if s.answer == nil {
		return fmt.Errorf("no permission answer was received")
	}
	if Approved(s.answer) {
		return fmt.Errorf("answer %q should refuse the command", s.answer.OptionID)
	}
	return nil
}

func (s *acpPermissionAnswersSteps) stillNeedsPermission(command string) error {
	if CommandAllowedWithSession(s.env, s.state.GetPermissionCommandGrants(), command) {
		return fmt.Errorf("%q unexpectedly became allowed", command)
	}
	return nil
}
