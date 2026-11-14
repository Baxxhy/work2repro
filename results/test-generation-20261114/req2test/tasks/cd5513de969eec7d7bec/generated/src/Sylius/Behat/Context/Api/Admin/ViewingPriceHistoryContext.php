<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Webmozart\Assert\Assert;

final class ViewingPriceHistoryContext implements Context
{
    private array $entries = [];

    public function __construct(
        private ApiClientInterface $adminApiClient,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('/^I go to the price history of a variant with code "([^"]+)"$/')]
    public function iGoToPriceHistoryOfVariant(string $code): void
    {
        $response = $this->adminApiClient->index('admin/products', ['code' => $code]);
        $products = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);
        Assert::notEmpty($products['hydra:member'] ?? []);
        $product = $products['hydra:member'][0];

        $response = $this->adminApiClient->requestGet((string) $product['@id']);
        $product = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);
        $variant = null;
        foreach ($product['variants'] ?? [] as $candidate) {
            if (($candidate['code'] ?? null) === $code) {
                $variant = $candidate;
                break;
            }
        }
        Assert::notNull($variant, sprintf('Variant "%s" was not found.', $code));
        $pricing = $variant['channelPricings'][0] ?? null;
        Assert::notNull($pricing);

        $uri = '/api/v2/admin/channel-pricing-log-entries';
        $response = $this->adminApiClient->requestGet($uri, [
            'channelPricing' => $pricing['@id'],
            'order[id]' => 'desc',
        ]);
        $content = json_decode((string) $response->getContent(), true, flags: JSON_THROW_ON_ERROR);
        $this->entries = $content['hydra:member'] ?? $content['member'] ?? [];
        $this->sharedStorage->set('catalog_price_history', $this->entries);
    }

    #[Then('/^I should see (\d+) log entries in the catalog price history$/')]
    public function iShouldSeeLogEntries(int $count): void
    {
        Assert::count($this->entries, $count);
    }

    #[Then('/^there should be a log entry on the (\d+)(?:st|nd|rd|th) position with the "([^"]+)" selling price, "([^"]+)" original price and datetime of the price change$/')]
    public function thereShouldBeLogEntry(int $position, string $price, string $originalPrice): void
    {
        Assert::keyExists($this->entries, $position - 1);
        $entry = $this->entries[$position - 1];
        Assert::same((int) str_replace('.', '', substr($price, 1)), (int) ($entry['price'] ?? -1));
        Assert::same((int) str_replace('.', '', substr($originalPrice, 1)), (int) ($entry['originalPrice'] ?? -1));
        Assert::notNull($entry['loggedAt'] ?? null, 'The price change datetime should be present.');
    }
}
