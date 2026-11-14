<?php

declare(strict_types=1);

namespace Tests\Integration\Behaviour\Features\Context;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use Configuration;
use Language;
use PHPUnit\Framework\Assert;
use PrestaShop\PrestaShop\Core\Domain\Product\Command\AddProductCommand;
use PrestaShop\PrestaShop\Core\Domain\Product\Command\DuplicateProductCommand;
use PrestaShop\PrestaShop\Core\Domain\Product\Query\GetProductForEditing;
use PrestaShop\PrestaShop\Core\Domain\Product\VirtualProductFile\Command\AddVirtualProductFileCommand;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use Shop;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/**
 * Glue for the virtual-product duplication scenario.
 *
 * The setup statements in this feature describe fixtures which are already
 * supplied by the integration database. They are intentionally lightweight:
 * none is an input to the product operation exercised here.
 */
class VirtualProductDuplicateContext extends AbstractDomainFeatureContext implements Context
{
    /** @Given /^manufacturer studioDesign named "Studio Design" exists$/ */
    public function manufacturerExists(): void {}

    /** @Given /^language "([^"]+)" with locale "([^"]+)" exists$/ */
    public function languageExists(string $reference, string $locale): void
    {
        $iso = substr($locale, 0, 2);
        $language = new Language(Language::getIdByIso($iso));
        $this->getSharedStorage()->set($reference, (int) $language->id);
    }

    /** @Given /^language with iso code "([^"]+)" is the default one$/ */
    public function defaultLanguage(string $iso): void {}

    /** @Given /^I create carrier "([^"]+)" with specified properties:$/ */
    public function carrierExists(string $reference, TableNode $table): void {}

    /** @Given /^attribute group "([^"]+)" named "([^"]+)" in en language exists$/ */
    public function attributeGroupExists(string $reference, string $name): void {}

    /** @Given /^attribute "([^"]+)" named "([^"]+)" in en language exists$/ */
    public function attributeExists(string $reference, string $name): void {}

    /** @Given /^shop "([^"]+)" with name "([^"]+)" exists$/ */
    public function shopExists(string $reference, string $name): void
    {
        $this->getSharedStorage()->set($reference, (int) Shop::getContextShopID());
    }

    /** @Given /^single shop shop1 context is loaded$/ */
    public function loadShopContext(): void {}

    /** @Given /^I add product "([^"]+)" with following information:$/ */
    public function addProduct(string $reference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $names = [];
        foreach ($data as $key => $value) {
            if (preg_match('/^name\\[(.+)\\]$/', $key, $matches)) {
                $languageId = (int) Language::getIdByLocale($matches[1]);
                $names[$languageId] = $value;
            }
        }
        $shopId = (int) Shop::getContextShopID();
        $productId = $this->getCommandBus()->handle(new AddProductCommand($data['type'], $shopId, $names));
        $this->getSharedStorage()->set($reference, $productId);
    }

    /** @When /^I add virtual product file "([^"]+)" to product "([^"]+)" with following details:$/ */
    public function addVirtualFile(string $fileReference, string $productReference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $path = _PS_ROOT_DIR_ . '/tests/Resources/dummyFile/app_icon.png';
        $fileId = $this->getCommandBus()->handle(new AddVirtualProductFileCommand(
            $this->referenceToId($productReference),
            $path,
            $data['display name']
        ));
        $this->getSharedStorage()->set($fileReference, $fileId);
    }

    /** @When /^I duplicate product ([^ ]+) to a ([^ ]+)$/ */
    public function duplicateProduct(string $source, string $copy): void
    {
        $id = $this->getCommandBus()->handle(new DuplicateProductCommand(
            $this->referenceToId($source),
            ShopConstraint::shop((int) Shop::getContextShopID())
        ));
        $this->getSharedStorage()->set($copy, $id->getValue());
    }

    /** @Then /^product ([^ ]+) type should be virtual$/ */
    public function productIsVirtual(string $reference): void
    {
        $product = $this->getQueryBus()->handle(new GetProductForEditing(
            $this->referenceToId($reference),
            ShopConstraint::shop((int) Shop::getContextShopID()),
            (int) Configuration::get('PS_LANG_DEFAULT')
        ));
        Assert::assertSame('virtual', $product->getType());
    }

    /** @Then /^product "([^"]+)" should be disabled$/ */
    public function productDisabled(string $reference): void
    {
        Assert::assertFalse((bool) (new \Product($this->referenceToId($reference)))->active);
    }

    /** @Then /^product "([^"]+)" should have a virtual product file "([^"]+)" with following details:$/ */
    public function productHasFile(string $productReference, string $fileReference, TableNode $table): void
    {
        $file = $this->editingProduct($productReference)->getVirtualProductFile();
        Assert::assertNotNull($file);
        $this->getSharedStorage()->set($fileReference, $file->getId());
        $this->assertFileDetails($file, $table);
    }

    /** @Then /^product ([^ ]+) should have a virtual product file which reference is ([^ ]+) and has following details:$/ */
    public function productHasCopiedFile(string $productReference, string $fileReference, TableNode $table): void
    {
        $file = $this->editingProduct($productReference)->getVirtualProductFile();
        Assert::assertNotNull($file);
        $this->getSharedStorage()->set($fileReference, $file->getId());
        $this->assertFileDetails($file, $table);
    }

    /** @Then /^file "([^"]+)" for product "([^"]+)" should exist in system$/ */
    /** @Then /^file ([^ ]+) for product ([^ ]+) should exist in system$/ */
    public function fileExists(string $fileReference, string $productReference): void
    {
        $file = $this->editingProduct($productReference)->getVirtualProductFile();
        Assert::assertNotNull($file);
        Assert::assertSame($this->referenceToId($fileReference), $file->getId());
        Assert::assertFileExists(_PS_DOWNLOAD_DIR_ . $file->getFileName());
    }

    /** @Then /^file ([^ ]+) for product ([^ ]+) should have same file as ([^ ]+)$/ */
    public function fileHasExpectedContent(string $fileReference, string $productReference, string $filename): void
    {
        $file = $this->editingProduct($productReference)->getVirtualProductFile();
        Assert::assertNotNull($file);
        Assert::assertSame(
            hash_file('sha256', _PS_ROOT_DIR_ . '/tests/Resources/dummyFile/' . $filename),
            hash_file('sha256', _PS_DOWNLOAD_DIR_ . $file->getFileName())
        );
    }

    /** @Then /^file1 and file1Copy have different values$/ */
    public function filesDiffer(): void
    {
        Assert::assertNotSame($this->referenceToId('file1'), $this->referenceToId('file1Copy'));
    }

    private function editingProduct(string $reference): \PrestaShop\PrestaShop\Core\Domain\Product\QueryResult\ProductForEditing
    {
        return $this->getQueryBus()->handle(new GetProductForEditing(
            $this->referenceToId($reference),
            ShopConstraint::shop((int) Shop::getContextShopID()),
            (int) Configuration::get('PS_LANG_DEFAULT')
        ));
    }

    private function assertFileDetails($file, TableNode $table): void
    {
        $actual = [
            'display name' => $file->getDisplayName(),
            'access days' => (string) $file->getAccessDays(),
            'download times limit' => (string) $file->getDownloadTimesLimit(),
            'expiration date' => $file->getExpirationDate() ? $file->getExpirationDate()->format('Y-m-d') : '',
        ];
        foreach ($table->getRowsHash() as $key => $value) {
            Assert::assertSame($value, $actual[$key], 'Unexpected virtual product file ' . $key);
        }
    }
}
