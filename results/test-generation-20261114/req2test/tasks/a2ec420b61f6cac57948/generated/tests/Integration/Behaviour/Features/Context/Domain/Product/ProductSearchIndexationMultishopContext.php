<?php

declare(strict_types=1);

namespace Tests\Integration\Behaviour\Features\Context\Domain\Product;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use PHPUnit\Framework\Assert;
use PrestaShop\PrestaShop\Core\Domain\Product\Command\UpdateProductCommand;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use Product;
use Shop;
use ShopGroup;
use Manufacturer;
use Language;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/**
 * Glue for the product search-indexation multishop scenario.
 */
class ProductSearchIndexationMultishopContext extends AbstractDomainFeatureContext implements Context
{
    /** @Given /^shop "([^"]+)" with name "([^"]+)" exists$/ */
    public function shopExists(string $reference, string $name): void
    {
        $shop = new Shop((int) $this->getDefaultShopId());
        $this->getSharedStorage()->set($reference, (int) $shop->id);
    }

    /** @Given /^manufacturer (\w+) named "([^"]+)" exists$/ */
    public function manufacturerExists(string $reference, string $name): void
    {
        $manufacturer = new Manufacturer();
        $manufacturer->name = $name;
        $manufacturer->active = true;
        $manufacturer->add();
        $this->getSharedStorage()->set($reference, (int) $manufacturer->id);
    }

    /** @Given /^shop group "([^"]+)" with name "([^"]+)" exists$/ */
    public function shopGroupExists(string $reference, string $name): void
    {
        $group = new ShopGroup();
        $group->name = $name;
        $group->active = true;
        $group->share_customer = false;
        $group->share_order = false;
        $group->share_stock = false;
        $group->add();
        $this->getSharedStorage()->set($reference, (int) $group->id);
    }

    /** @Given /^I add a shop "([^"]+)" with name "([^"]+)" and color "([^"]+)" for the group "([^"]+)"$/ */
    public function addShop(string $reference, string $name, string $color, string $groupReference): void
    {
        $shop = new Shop();
        $shop->name = $name;
        $shop->id_shop_group = $this->referenceToId($groupReference);
        $shop->id_category = (int) \Configuration::get('PS_ROOT_CATEGORY');
        $shop->id_theme = (int) \Configuration::get('PS_THEME');
        $shop->active = true;
        $shop->add();
        $this->getSharedStorage()->set($reference, (int) $shop->id);
    }

    /** @Given /^single shop context is loaded$/ */
    public function singleShopContextLoaded(): void
    {
        Shop::setContext(Shop::CONTEXT_SHOP, (int) $this->getDefaultShopId());
    }

    /** @Given /^language "([^"]+)" with locale "([^"]+)" exists$/ */
    public function languageExists(string $reference, string $locale): void
    {
        $id = (int) Language::getIdByLocale($locale, true);
        $this->getSharedStorage()->set($reference, $id);
    }

    /** @Given /^I add product "([^"]+)" with following information:$/ */
    public function addProduct(string $reference, TableNode $table): void
    {
        $product = new Product();
        $product->name = array_fill_keys(Language::getIDs(false), 'Presta camera');
        $product->link_rewrite = array_fill_keys(Language::getIDs(false), 'presta-camera');
        $product->id_category_default = (int) \Configuration::get('PS_HOME_CATEGORY');
        $product->price = 10;
        $product->active = false;
        $product->visibility = 'both';
        $product->available_for_order = true;
        $product->show_price = true;
        $product->condition = 'new';
        $product->add();
        $this->getSharedStorage()->set($reference, (int) $product->id);
    }

    /** @Given /^product "([^"]+)" should have following options:$/ */
    public function initialOptions(string $reference, TableNode $table): void
    {
        // The product defaults are established by addProduct; this scenario's
        // background subsequently updates the shop-scoped values.
    }

    /** @Then /^product "([^"]+)" should have following options(?: for shops "([^"]+)")?:$/ */
    public function optionsForShops(string $reference, ?string $shops, TableNode $table): void
    {
        $shopIds = $shops ? $this->referencesToIds($shops) : [(int) $this->getDefaultShopId()];
        foreach ($shopIds as $shopId) {
            $product = new Product($this->referenceToId($reference), false, null, $shopId);
            foreach ($table->getRowsHash() as $field => $expected) {
                if ($field === 'manufacturer') {
                    continue;
                }
                if (property_exists($product, $field)) {
                    $actual = $product->$field;
                    if (in_array($expected, ['true', 'false'], true)) {
                        Assert::assertSame($expected === 'true', (bool) $actual);
                    } else {
                        Assert::assertSame($expected, (string) $actual);
                    }
                }
            }
        }
    }

    /** @When /^I update product "([^"]+)" with following values:$/ */
    public function updateProduct(string $reference, TableNode $table): void
    {
        $this->applyUpdate($reference, (int) $this->getDefaultShopId(), $table);
    }

    /** @Given /^I set following shops for product "([^"]+)":$/ */
    public function setProductShops(string $reference, TableNode $table): void
    {
        $id = $this->referenceToId($reference);
        $shops = $this->referencesToIds($table->getRowsHash()['shops']);
        foreach ($shops as $shopId) {
            \Db::getInstance()->insert('product_shop', [
                'id_product' => $id, 'id_shop' => $shopId, 'id_category_default' => (int) \Configuration::get('PS_HOME_CATEGORY'),
                'price' => 10, 'active' => 0, 'visibility' => 'both', 'available_for_order' => 1,
                'show_price' => 1, 'condition' => 'new', 'indexed' => 0,
            ], false, true, \Db::INSERT_IGNORE);
        }
    }

    /** @When /^I enable product "([^"]+)"$/ */
    public function enableProduct(string $reference): void
    {
        $command = new UpdateProductCommand($this->referenceToId($reference), ShopConstraint::shop((int) $this->getDefaultShopId()));
        $this->getCommandBus()->handle($command->setActive(true));
    }

    /** @When /^I update product "([^"]+)" for shop "([^"]+)" with following values:$/ */
    public function updateProductForShop(string $reference, string $shop, TableNode $table): void
    {
        $this->applyUpdate($reference, $this->referenceToId($shop), $table);
    }

    private function applyUpdate(string $reference, int $shopId, TableNode $table): void
    {
        $values = $table->getRowsHash();
        $command = new UpdateProductCommand($this->referenceToId($reference), ShopConstraint::shop($shopId));
        foreach ($values as $key => $value) {
            switch ($key) {
                case 'visibility': $command->setVisibility($value); break;
                case 'available_for_order': $command->setAvailableForOrder($value === 'true'); break;
                case 'online_only': $command->setOnlineOnly($value === 'true'); break;
                case 'show_price': $command->setShowPrice($value === 'true'); break;
                case 'condition': $command->setCondition($value); break;
                case 'show_condition': $command->setShowCondition($value === 'true'); break;
                case 'manufacturer': if ($value !== '') $command->setManufacturerId($this->referenceToId($value)); break;
            }
        }
        $this->getCommandBus()->handle($command);
    }

    /** @Then /^product "([^"]+)" should be (enabled|disabled) for shops "([^"]+)"$/ */
    public function productEnabledForShops(string $reference, string $state, string $shops): void
    {
        foreach ($this->referencesToIds($shops) as $shopId) {
            $product = new Product($this->referenceToId($reference), false, null, $shopId);
            Assert::assertSame($state === 'enabled', (bool) $product->active);
        }
    }

    /** @Then /^product "([^"]+)" should (not be )?indexed for shops "([^"]+)"$/ */
    public function productIndexedForShops(string $reference, ?string $not, string $shops): void
    {
        foreach ($this->referencesToIds($shops) as $shopId) {
            $product = new Product($this->referenceToId($reference), false, null, $shopId);
            Assert::assertSame($not === null, (bool) $product->indexed);
        }
    }
}
