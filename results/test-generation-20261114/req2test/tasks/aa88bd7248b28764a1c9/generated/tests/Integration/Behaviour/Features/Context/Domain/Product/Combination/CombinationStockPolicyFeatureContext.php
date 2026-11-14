<?php

declare(strict_types=1);

namespace Tests\Integration\Behaviour\Features\Context\Domain\Product\Combination;

use Behat\Gherkin\Node\TableNode;
use PHPUnit\Framework\Assert;
use PrestaShop\PrestaShop\Core\Domain\Product\Query\GetProductForEditing;
use PrestaShop\PrestaShop\Core\Domain\Product\Stock\Command\UpdateProductStockAvailableCommand;
use PrestaShop\PrestaShop\Core\Domain\Product\Stock\ValueObject\OutOfStockType;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use StockAvailable;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/**
 * Stock-policy checks for the product-combination multishop scenario.
 */
class CombinationStockPolicyFeatureContext extends AbstractDomainFeatureContext
{
    private const TYPES = [
        'not_available' => OutOfStockType::OUT_OF_STOCK_NOT_AVAILABLE,
        'available' => OutOfStockType::OUT_OF_STOCK_AVAILABLE,
        'default' => OutOfStockType::OUT_OF_STOCK_DEFAULT,
    ];

    /** @When /^I update product "([^"]*)" stock for shop "([^"]*)" with following information:$/ */
    public function updateProductStockForShop(string $productReference, string $shopReference, TableNode $table): void
    {
        $this->updateStock($productReference, $this->referenceToId($shopReference), $table);
    }

    /** @When /^I update product "([^"]*)" stock for all shops with following information:$/ */
    public function updateProductStockForAllShops(string $productReference, TableNode $table): void
    {
        $rows = $table->getRowsHash();
        $type = self::TYPES[$rows['out_of_stock_type']];
        $command = new UpdateProductStockAvailableCommand(
            $this->referenceToId($productReference),
            ShopConstraint::allShops()
        );
        $this->getCommandBus()->handle($command->setOutOfStockType($type));
        \Cache::clean('StockAvailable::getStockAvailableIdByProductId_*');
    }

    /** @Then /^all combinations of product "([^"]*)" for shops "([^"]*)" should have the stock policy to "([^"]*)"$/ */
    public function assertCombinationsStockPolicy(string $productReference, string $shops, string $expected): void
    {
        foreach ($this->referencesToIds($shops) as $shopId) {
            $stockRows = \Db::getInstance()->executeS(
                'SELECT sa.out_of_stock FROM `' . _DB_PREFIX_ . 'stock_available` sa
                 WHERE sa.id_product = ' . (int) $this->referenceToId($productReference) . '
                   AND sa.id_product_attribute != 0 AND sa.id_shop = ' . (int) $shopId
            );
            foreach ($stockRows as $row) {
                Assert::assertSame(self::TYPES[$expected], (int) $row['out_of_stock']);
            }
            Assert::assertNotEmpty($stockRows, 'Expected product combinations to exist for shop ' . $shopId);
        }
    }

    /** @Given /^product "([^"]*)" should have following stock information for shops "([^"]*)":$/ */
    public function assertProductStockInformation(string $productReference, string $shops, TableNode $table): void
    {
        if (!isset($table->getRowsHash()['out_of_stock_type'])) {
            return;
        }
        foreach ($this->referencesToIds($shops) as $shopId) {
            $product = $this->getQueryBus()->handle(new GetProductForEditing(
                $this->referenceToId($productReference),
                ShopConstraint::shop($shopId),
                (int) \Configuration::get('PS_LANG_DEFAULT')
            ));
            Assert::assertSame(
                self::TYPES[$table->getRowsHash()['out_of_stock_type']],
                $product->getStockInformation()->getOutOfStockType()
            );
        }
    }

    private function updateStock(string $productReference, int $shopId, TableNode $table): void
    {
        $rows = $table->getRowsHash();
        $command = new UpdateProductStockAvailableCommand(
            $this->referenceToId($productReference),
            ShopConstraint::shop($shopId)
        );
        $this->getCommandBus()->handle($command->setOutOfStockType(self::TYPES[$rows['out_of_stock_type']]));
        \Cache::clean('StockAvailable::getStockAvailableIdByProductId_*');
    }
}
