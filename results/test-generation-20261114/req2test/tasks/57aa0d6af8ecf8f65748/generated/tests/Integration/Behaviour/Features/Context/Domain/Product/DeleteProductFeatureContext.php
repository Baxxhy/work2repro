<?php
/**
 * For the full copyright and license information, please view the
 * docs/licenses/LICENSE.txt file.
 */

declare(strict_types=1);

namespace Tests\Integration\Behaviour\Features\Context\Domain\Product;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use PHPUnit\Framework\Assert;
use PrestaShop\PrestaShop\Core\Domain\Product\Command\BulkDeleteProductCommand;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use Product;

/**
 * @todo Product CRUD behavior for the delete-product feature.
 */
class DeleteProductFeatureContext extends AbstractProductFeatureContext implements Context
{
    /**
     * @Given /^I add product "([^"]+)" with following information:$/
     */
    public function addProduct(string $reference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $name = [];
        foreach ($data as $key => $value) {
            if (preg_match('/^name\[([^\]]+)\]$/', $key, $matches)) {
                $langId = (int) \Language::getIdByLocale($matches[1], true);
                $name[$langId] = $value;
            }
        }

        $product = new Product();
        $product->name = $name;
        $product->link_rewrite = array_fill_keys(array_keys($name), 'test-product-' . $reference);
        $product->reference = $reference;
        $product->price = 1;
        $product->active = 1;
        $product->id_category_default = (int) \Configuration::get('PS_HOME_CATEGORY');
        Assert::assertTrue($product->add(), 'Could not create product ' . $reference);
        $product->addToCategories([(int) \Configuration::get('PS_HOME_CATEGORY')]);

        $this->getSharedStorage()->set($reference, (int) $product->id);
    }

    /**
     * @Then /^product "([^"]+)" type should be standard$/
     */
    public function assertProductIsStandard(string $reference): void
    {
        Assert::assertSame('standard', $this->getProductForEditing($reference)->getType());
    }

    /**
     * @When /^I bulk delete following products:$/
     */
    public function bulkDeleteProducts(TableNode $table): void
    {
        $ids = [];
        foreach ($table->getHash() as $row) {
            $ids[] = $this->referenceToId($row['reference']);
        }

        $this->getCommandBus()->handle(new BulkDeleteProductCommand(
            $ids,
            ShopConstraint::shop($this->getDefaultShopId())
        ));
    }

    /**
     * @Then /^product ([^ ]+) should not exist anymore$/
     */
    public function assertProductDoesNotExist(string $reference): void
    {
        $product = new Product($this->referenceToId($reference));
        Assert::assertFalse(\Validate::isLoadedObject($product), 'Product ' . $reference . ' still exists');
    }
}
