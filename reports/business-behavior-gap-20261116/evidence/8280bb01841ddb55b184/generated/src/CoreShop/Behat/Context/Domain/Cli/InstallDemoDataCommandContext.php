<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Cli;

use Behat\Behat\Context\Context;
use Symfony\Bundle\FrameworkBundle\Console\Application;
use Symfony\Component\Console\Input\ArrayInput;
use Symfony\Component\Console\Output\BufferedOutput;
use Symfony\Component\HttpKernel\KernelInterface;
use Webmozart\Assert\Assert;

final class InstallDemoDataCommandContext implements Context
{
    private ?int $lastExitCode = null;

    public function __construct(private KernelInterface $kernel)
    {
    }

    /** @When /^I run CoreShop Install Fixtures Data command$/ */
    public function runFixturesDataCommand(): void
    {
        $this->runCommand('coreshop:install:fixtures');
    }

    /** @When /^I confirm loading Fixtures Data command$/ */
    public function confirmFixturesDataCommand(): void
    {
        Assert::same($this->lastExitCode, 0, 'Fixtures data command did not finish successfully.');
    }

    /** @When /^I run CoreShop Install Demo Data command$/ */
    public function runDemoDataCommand(): void
    {
        $this->runCommand('coreshop:install:demo');
    }

    /** @When /^I confirm loading Demo Data command$/ */
    public function confirmDemoDataCommand(): void
    {
        Assert::same($this->lastExitCode, 0, 'Demo data command did not finish successfully.');
    }

    /** @Then /^the command should finish successfully$/ */
    public function commandShouldFinishSuccessfully(): void
    {
        Assert::same($this->lastExitCode, 0, 'The last install command did not finish successfully.');
    }

    private function runCommand(string $name): void
    {
        $application = new Application($this->kernel);
        $application->setAutoExit(false);
        $application->setCatchExceptions(false);

        $input = new ArrayInput([
            'command' => $name,
            '--no-interaction' => true,
        ]);
        $output = new BufferedOutput();
        $this->lastExitCode = $application->run($input, $output);

        Assert::same(
            $this->lastExitCode,
            0,
            sprintf("Command '%s' failed:\n%s", $name, $output->fetch()),
        );
    }
}
