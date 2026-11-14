<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\RequestFactoryInterface;
use Sylius\Behat\Service\Checker\EmailCheckerInterface;
use Webmozart\Assert\Assert;

final class ResettingPasswordContext implements Context
{
    private string $email = '';

    public function __construct(
        private readonly ApiClientInterface $client,
        private readonly RequestFactoryInterface $requestFactory,
        private readonly EmailCheckerInterface $emailChecker,
    ) {
    }

    #[When('I want to reset password')]
    public function wantToResetPassword(): void
    {
        // Establish the shop session and its locale before posting the form.
        $this->client->executeCustomRequest($this->requestFactory->custom('/en_US/forgotten-password', 'GET'));
    }

    #[When('I specify customer email as :email')]
    public function specifyCustomerEmail(string $email): void
    {
        $this->email = $email;
    }

    #[When('I reset it')]
    public function resetPassword(): void
    {
        $request = $this->requestFactory->custom(
            '/en_US/forgotten-password',
            'POST',
            ['CONTENT_TYPE' => 'application/x-www-form-urlencoded'],
        );
        $request->updateParameters(['sylius_user_request_password_reset' => ['email' => $this->email]]);
        $this->client->executeCustomRequest($request);
    }

    #[Then('I should be notified that email with reset instruction has been sent')]
    public function shouldBeNotifiedResetInstructionsWereSent(): void
    {
        Assert::contains(
            $this->client->getLastResponse()->getContent(),
            'If the email you have specified exists in our system, we have sent there an instruction on how to reset your password.',
        );
    }

    #[Then(':email should receive no emails')]
    public function emailShouldReceiveNoEmails(string $email): void
    {
        Assert::same(0, $this->emailChecker->countMessagesTo($email));
    }
}
