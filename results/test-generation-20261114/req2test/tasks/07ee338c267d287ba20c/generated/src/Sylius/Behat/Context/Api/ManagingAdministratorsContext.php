<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\ResponseCheckerInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Webmozart\Assert\Assert;

final class ManagingAdministratorsContext implements Context
{
    private const RESOURCE = 'administrators';

    public function __construct(
        private readonly ApiClientInterface $adminApiClient,
        private readonly ResponseCheckerInterface $responseChecker,
        private readonly SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I want to browse administrators')]
    public function browseAdministrators(): void
    {
        $this->sharedStorage->set('administrators_response', $this->adminApiClient->index(self::RESOURCE));
    }

    #[When('I delete administrator with email :email')]
    public function deleteAdministrator(string $email): void
    {
        $response = $this->adminApiClient->index(self::RESOURCE, ['email' => $email]);
        $administrators = $this->responseChecker->getCollection($response);
        Assert::count($administrators, 1, sprintf('Expected exactly one administrator with email "%s".', $email));

        $this->sharedStorage->set(
            'administrator_delete_response',
            $this->adminApiClient->delete(self::RESOURCE, (string) $administrators[0]['id']),
        );
        $this->sharedStorage->set('administrator_email_to_check', $email);
    }

    #[Then('I should be notified that it has been successfully deleted')]
    public function deletionShouldBeSuccessful(): void
    {
        Assert::true($this->responseChecker->isDeletionSuccessful($this->sharedStorage->get('administrator_delete_response')));
    }

    #[Then('there should not be :email administrator anymore')]
    public function administratorShouldNoLongerExist(string $email): void
    {
        $response = $this->adminApiClient->index(self::RESOURCE, ['email' => $email]);
        Assert::same($this->responseChecker->countCollectionItems($response), 0);
    }
}
