<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Doctrine\Persistence\ObjectRepository;
use Sylius\Component\Core\Model\ProductVariantInterface;
use Symfony\Component\BrowserKit\AbstractBrowser;
use Webmozart\Assert\Assert;

final class ViewingCatalogPriceHistoryContext implements Context
{
    private ?string $historyHtml = null;

    public function __construct(
        private ObjectRepository $productVariantRepository,
        private AbstractBrowser $client,
    ) {
    }

    #[When('/^I go to the price history of a variant with code "([^"]+)"$/')]
    public function iGoToThePriceHistoryOfAVariantWithCode(string $code): void
    {
        $variant = $this->productVariantRepository->findOneBy(['code' => $code]);
        Assert::isInstanceOf($variant, ProductVariantInterface::class);

        $pricing = $variant->getChannelPricings()->first();
        Assert::notFalse($pricing);
        $product = $variant->getProduct();
        Assert::notNull($product);

        $url = sprintf(
            '/admin/products/%s/variants/%s/channel-pricing/%s/channel-pricing-log-entries',
            $product->getId(),
            $variant->getId(),
            $pricing->getId(),
        );
        $this->client->request('GET', $url);
        $this->historyHtml = $this->client->getResponse()->getContent();
    }

    #[Then('/^I should see ([0-9]+) log entries in the catalog price history$/')]
    public function iShouldSeeLogEntriesInTheCatalogPriceHistory(int $count): void
    {
        Assert::notNull($this->historyHtml);
        $rows = $this->rows();
        Assert::count($rows, $count);
    }

    #[Then('/^there should be a log entry on the ([0-9]+)(?:st|nd|rd|th) position with the "([^"]+)" selling price, "([^"]+)" original price and datetime of the price change$/')]
    public function thereShouldBeLogEntryOnPositionWithPrices(int $position, string $sellingPrice, string $originalPrice): void
    {
        $this->assertHistoryRow($position, $sellingPrice, $originalPrice);
    }

    #[Then('/^there should be a log entry on the ([0-9]+)(?:st|nd|rd|th) position with the "([^"]+)" selling price, no original price and datetime of the price change$/')]
    public function thereShouldBeLogEntryOnPositionWithSellingPriceAndNoOriginalPrice(int $position, string $sellingPrice): void
    {
        $this->assertHistoryRow($position, $sellingPrice, '-');
    }

    private function assertHistoryRow(int $position, string $sellingPrice, string $originalPrice): void
    {
        Assert::notNull($this->historyHtml);
        $rows = $this->rows();
        Assert::keyExists($rows, $position - 1);
        $row = strip_tags($rows[$position - 1]);
        Assert::contains($row, $sellingPrice);
        Assert::contains($row, $originalPrice);
        Assert::regex($rows[$position - 1], '/\d{4}/');
    }

    /** @return list<string> */
    private function rows(): array
    {
        Assert::notNull($this->historyHtml);
        if (preg_match('/<tbody\b[^>]*>(.*?)<\/tbody>/si', $this->historyHtml, $body) !== 1) {
            return [];
        }

        preg_match_all('/<tr\b[^>]*>.*?<\/tr>/si', $body[1], $matches);

        return $matches[0];
    }
}
