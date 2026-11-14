<?php

declare(strict_types=1);

namespace Tests\Integration\Behaviour\Features\Context\Domain\Product;

use Context;
use Language;
use Pack;
use Product;
use StockAvailable;
use Tests\Integration\Behaviour\Features\Context\AbstractPrestaShopFeatureContext;

class PackStockFeatureContext extends AbstractPrestaShopFeatureContext
{
    /**
     * @Given /^there is a product in the catalog named "([^"]+)" with a price of ([0-9.]+) and ([0-9]+) items in stock$/
     */
    public function createProduct(string $reference, string $price, int $quantity): void
    {
        $context = Context::getContext();
        $product = new Product();
        $product->name = [];
        foreach (Language::getLanguages(false) as $language) {
            $product->name[(int) $language['id_lang']] = $reference;
        }
        $product->link_rewrite = [];
        foreach (Language::getLanguages(false) as $language) {
            $product->link_rewrite[(int) $language['id_lang']] = $reference;
        }
        $product->price = (float) $price;
        $product->active = true;
        $product->available_for_order = true;
        $product->id_category_default = (int) $context->shop->id_category;
        $product->id_tax_rules_group = 0;
        if (!$product->add()) {
            throw new \RuntimeException('Unable to create product ' . $reference);
        }

        StockAvailable::setQuantity((int) $product->id, 0, $quantity, (int) $context->shop->id);
        $this->getSharedStorage()->set($reference, (int) $product->id);
    }

    /**
     * @Given /^product "([^"]+)" is a pack containing ([0-9]+) items of product "([^"]+)"$/
     */
    public function addProductToPack(string $packReference, int $quantity, string $productReference): void
    {
        Pack::addItem(
            $this->referenceToId($packReference),
            $this->referenceToId($productReference),
            $quantity
        );
    }

    /**
     * @Then /^the remaining available stock for product "([^"]+)" should be (-?[0-9]+)$/
     */
    public function assertAvailableQuantity(string $reference, int $expected): void
    {
        \PHPUnit\Framework\Assert::assertSame(
            $expected,
            (int) Product::getQuantity($this->referenceToId($reference))
        );
    }
}
