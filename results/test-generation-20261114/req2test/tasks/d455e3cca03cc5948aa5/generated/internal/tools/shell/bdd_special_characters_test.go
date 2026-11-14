package shell

import (
	"fmt"

	"github.com/EvilFreelancer/coddy-agent/internal/platform"
)

func foregroundComplaintCommand(sh platform.Shell, message string) (string, error) {
	switch sh.Kind {
	case platform.ShellPwsh, platform.ShellPowerShell:
		return fmt.Sprintf("Write-Error '%s'; Start-Sleep -Seconds 60", message), nil
	case platform.ShellCmd:
		return fmt.Sprintf("echo %s 1>&2 & timeout /t 60 /nobreak >NUL", message), nil
	default:
		return fmt.Sprintf("printf '%%s\\n' '%s' >&2; sleep 60", message), nil
	}
}
