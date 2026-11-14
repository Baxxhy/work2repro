<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\ResponseCheckerInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\ProductInterface;
use Webmozart\Assert\Assert;

final class ProductPriceContext implements Context
{
    public function __construct(
        private ApiClientInterface $client,
        private ResponseCheckerInterface $responseChecker,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I check this product\'s details')]
    public function checkProductDetails(ProductInterface $product): void
    {
        $response = $this->client->show('shop/products', $product->getCode());
        Assert::true($this->responseChecker->isShowSuccessful($response));
        $this->sharedStorage->set('product_details', $this->responseChecker->getResponseContent($response));
    }

    #[Then('I should see the product price :price')]
    public function shouldSeeProductPrice(string $price): void
    {
        Assert::same($this->variantPrice('price'), $this->priceToInteger($price));
    }

    #[Then('I should see the product original price :price')]
    public function shouldSeeProductOriginalPrice(string $price): void
    {
        Assert::same($this->variantPrice('originalPrice'), $this->priceToInteger($price));
    }

    private function variantPrice(string $field): int
    {
        $details = $this->sharedStorage->get('product_details');
        Assert::isArray($details);
        Assert::isArray($details['variants'] ?? null);
        Assert::notEmpty($details['variants']);
        Assert::isArray($details['variants'][0]);
        Assert::keyExists($field, $details['variants'][0]);

        return (int) $details['variants'][0][$field];
    }

    private function priceToInteger(string $price): int
    {
        return (int) preg_replace('/\D/', '', $price);
    }
}
