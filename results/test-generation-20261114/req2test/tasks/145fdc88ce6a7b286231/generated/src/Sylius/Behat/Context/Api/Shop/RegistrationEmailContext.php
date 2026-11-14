<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\RequestFactoryInterface;
use Sylius\Behat\Service\Checker\EmailCheckerInterface;
use Webmozart\Assert\Assert;

final readonly class RegistrationEmailContext implements Context
{
    public function __construct(
        private ApiClientInterface $client,
        private RequestFactoryInterface $requestFactory,
        private EmailCheckerInterface $emailChecker,
    ) {
    }

    #[When('/^I register with email "([^"]+)" and password "([^"]+)"$/')]
    public function register(string $email, string $password): void
    {
        $request = $this->requestFactory->create('shop', 'customers', 'Authorization');
        $request->setContent([
            'email' => $email,
            'password' => $password,
            'firstName' => 'Ghastly',
            'lastName' => 'Bespoke',
        ]);
        $this->client->request($request);
    }

    #[Then('/^only one email should have been sent to "([^"]+)"$/')]
    public function onlyOneEmail(string $email): void
    {
        Assert::same(1, $this->emailChecker->countMessagesTo($email));
    }

    #[Then('/^a verification email should have been sent to "([^"]+)"$/')]
    public function verificationEmail(string $email): void
    {
        Assert::true($this->emailChecker->hasMessageTo('verify', $email));
    }

    #[Then('/^a welcoming email should not have been sent to "([^"]+)"$/')]
    public function noWelcomeEmail(string $email): void
    {
        Assert::false($this->emailChecker->hasMessageTo('Welcome', $email));
    }
}
