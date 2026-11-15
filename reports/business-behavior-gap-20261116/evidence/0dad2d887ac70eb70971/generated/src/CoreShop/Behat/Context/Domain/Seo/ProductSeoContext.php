<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Seo;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use CoreShop\Component\SEO\SEOPresentationInterface;
use Pimcore\Model\DataObject\CoreShopProduct;
use Webmozart\Assert\Assert;

final class ProductSeoContext implements Context
{
    public function __construct(
        private SharedStorageInterface $sharedStorage,
        private SEOPresentationInterface $seoPresentation,
    ) {
    }

    /** @Given /^the site has a product "([^"]+)"$/ */
    public function theSiteHasAProduct(string $name): void
    {
        $product = new CoreShopProduct();
        $product->setKey($this->uniqueKey($name));
        $product->setParentId(1);
        $product->setName($name);
        $product->save();

        $this->sharedStorage->set('product', $product);
    }

    /** @Given /^the products meta title is "([^"]+)"$/ */
    public function theProductsMetaTitleIs(string $title): void
    {
        $product = $this->product();
        $product->setPimcoreMetaTitle($title);
        $product->save();
        $this->seoPresentation->updateSeoMetadata($product);
    }

    /** @Then /^the product should have meta title "([^"]+)"$/ */
    public function theProductShouldHaveMetaTitle(string $title): void
    {
        Assert::same($this->product()->getMetaTitle(), $title);
    }

    private function product(): CoreShopProduct
    {
        $product = $this->sharedStorage->get('product');
        Assert::isInstanceOf($product, CoreShopProduct::class);

        return $product;
    }

    private function uniqueKey(string $name): string
    {
        return strtolower(preg_replace('/[^a-z0-9]+/i', '-', trim($name)) ?? 'product')
            . '-'
            . bin2hex(random_bytes(4));
    }
}
