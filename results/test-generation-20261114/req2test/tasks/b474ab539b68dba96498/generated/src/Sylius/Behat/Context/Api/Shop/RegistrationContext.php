<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\User\Repository\UserRepositoryInterface;
use Symfony\Contracts\Translation\TranslatorInterface;
use Webmozart\Assert\Assert;

final class RegistrationContext implements Context
{
    public function __construct(
        private ApiClientInterface $client,
        private SharedStorageInterface $sharedStorage,
        private UserRepositoryInterface $users,
        private \Sylius\Behat\Service\Checker\EmailCheckerInterface $emailChecker,
        private TranslatorInterface $translator,
    ) {
    }

    #[When('I register with email :email and password :password')]
    public function register(string $email, string $password): void
    {
        $channel = $this->sharedStorage->get('channel');
        $this->client->buildCreateRequest('customers')
            ->setRequestData([
                'firstName' => 'Ghastly',
                'lastName' => 'Bespoke',
                'email' => $email,
                'password' => $password,
                'channelCode' => $channel->getCode(),
                'localeCode' => 'en_US',
            ])
            ->create();
    }

    #[When('I verify my account using link sent to :email')]
    public function verify(string $email): void
    {
        $user = $this->users->findOneByEmail($email);
        Assert::notNull($user, sprintf('No user found for "%s".', $email));
        $token = $user->getEmailVerificationToken();
        Assert::notNull($token, 'The user has no email verification token.');

        $this->client->requestPatch('customers/verify/' . $token, []);
    }

    #[\Behat\Step\Then('a welcoming email should have been sent to :recipient')]
    public function welcomingEmailSent(string $recipient): void
    {
        Assert::true($this->emailChecker->hasMessageTo(
            $this->translator->trans('sylius.email.user_registration.welcome_to_our_store', [], null, 'en_US'),
            $recipient,
        ));
    }
}
