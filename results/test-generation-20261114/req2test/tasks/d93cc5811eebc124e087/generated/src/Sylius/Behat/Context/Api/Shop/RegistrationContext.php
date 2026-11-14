<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;

final class RegistrationContext implements Context
{
    public function __construct(private ApiClientInterface $shopApiClient)
    {
    }

    #[When('I register with email :email and password :password')]
    public function iRegisterWithEmailAndPassword(string $email, string $password): void
    {
        $this->shopApiClient
            ->buildCreateRequest('customers')
            ->setRequestData([
                'firstName' => 'Ghastly',
                'lastName' => 'Bespoke',
                'email' => $email,
                'password' => $password,
            ])
            ->create();
    }
}
