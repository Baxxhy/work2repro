<?php

namespace Tests\Integration\Behaviour\Features\Context\Domain\Product;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use Cache;
use Configuration;
use Db;
use Language;
use PHPUnit\Framework\Assert;
use PrestaShop\PrestaShop\Core\Domain\Product\Command\UpdateProductCommand;
use PrestaShop\PrestaShop\Core\Domain\Product\Query\GetProductForEditing;
use PrestaShop\PrestaShop\Core\Domain\Shop\ValueObject\ShopConstraint;
use Product;
use Tax;
use TaxRule;
use TaxRulesGroup;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/** Glue for the single state-tax product price scenario. */
class UpdatePricesContext extends AbstractDomainFeatureContext implements Context
{
    /** @Given /^I add product "([^"]+)" with following information:$/ */
    public function addProduct(string $ref, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $product = new Product();
        $product->name = [ (int) Configuration::get('PS_LANG_DEFAULT') => $data['name[en-US]'] ];
        $product->link_rewrite = [ (int) Configuration::get('PS_LANG_DEFAULT') => 'magic-staff' ];
        $product->price = 0;
        $product->id_tax_rules_group = (int) TaxRulesGroup::getIdByName('US-FL Rate (6%)');
        $product->active = 1;
        $product->add();
        $this->getSharedStorage()->set($ref, (int) $product->id);
    }

    /** @Then /^product ([^ ]+) should have following prices information:$/ */
    public function checkPrices(string $ref, TableNode $table): void
    {
        $product = $this->getQueryBus()->handle(new GetProductForEditing(
            $this->referenceToId($ref),
            ShopConstraint::shop((int) Configuration::get('PS_SHOP_DEFAULT')),
            (int) Configuration::get('PS_LANG_DEFAULT')
        ));
        $p = $product->getPricesInformation();
        $actual = [
            'price' => $p->getPrice(), 'price_tax_included' => $p->getPriceTaxIncluded(),
            'ecotax' => $p->getEcotax(), 'tax rules group' => TaxRulesGroup::getNameById($p->getTaxRulesGroupId()),
            'on_sale' => $p->isOnSale(), 'wholesale_price' => $p->getWholesalePrice(),
            'unit_price' => $p->getUnitPrice(), 'unit_price_tax_included' => $p->getUnitPriceTaxIncluded(),
            'unit_price_ratio' => $p->getUnitPriceRatio(), 'unity' => $p->getUnity(),
        ];
        foreach ($table->getRowsHash() as $key => $expected) {
            Assert::assertEquals($expected, $actual[$key], "Mismatch for $key");
        }
    }

    /** @When /^I update product "([^"]+)" with following values:$/ */
    public function updateProduct(string $ref, TableNode $table): void
    {
        $id = $this->referenceToId($ref);
        $cmd = new UpdateProductCommand($id, ShopConstraint::shop((int) Configuration::get('PS_SHOP_DEFAULT')));
        foreach ($table->getRowsHash() as $key => $value) {
            switch ($key) {
                case 'price': $cmd->setPrice($value); break;
                case 'ecotax': $cmd->setEcotax($value); break;
                case 'on_sale': $cmd->setOnSale($value === 'true'); break;
                case 'wholesale_price': $cmd->setWholesalePrice($value); break;
                case 'unit_price': $cmd->setUnitPrice($value); break;
                case 'unity': $cmd->setUnity($value); break;
                case 'tax rules group': $cmd->setTaxRulesGroupId((int) TaxRulesGroup::getIdByName($value)); break;
            }
        }
        $this->getCommandBus()->handle($cmd);
    }

    /** @Given /^I add new tax "([^"]+)" with following properties:$/ */
    public function addTax(string $ref, TableNode $table): void
    {
        $d = $table->getRowsHash();
        $tax = new Tax();
        $tax->name = $d['name']; $tax->rate = (float) $d['rate'];
        $tax->active = $d['is_enabled'] === 'true' ? 1 : 0; $tax->add();
        $this->getSharedStorage()->set($ref, (int) $tax->id);
    }

    /** @Given /^I add the tax rule group "([^"]+)" for the tax "([^"]+)" with the following conditions:$/ */
    public function addTaxGroup(string $ref, string $taxRef, TableNode $table): void
    {
        $d = $table->getRowsHash();
        $group = new TaxRulesGroup();
        $group->name = $d['name']; $group->active = 1; $group->add();
        $this->getSharedStorage()->set($ref, (int) $group->id);
        $this->insertRule($group->id, $this->referenceToId($taxRef), $d);
    }

    /** @Given /^I add the tax rule "([^"]+)" for tax rule group "([^"]+)":$/ */
    public function addTaxRule(string $taxRef, string $groupRef, TableNode $table): void
    {
        $this->insertRule($this->referenceToId($groupRef), $this->referenceToId($taxRef), $table->getRowsHash());
    }

    private function insertRule(int $groupId, int $taxId, array $d): void
    {
        $countryId = (int) Db::getInstance()->getValue('SELECT id_country FROM '._DB_PREFIX_.'country WHERE iso_code="'.pSQL($d['country']).'"');
        $stateId = (int) Db::getInstance()->getValue('SELECT id_state FROM '._DB_PREFIX_.'state WHERE iso_code="'.pSQL($d['state']).'" AND id_country='.(int)$countryId);
        $rule = new TaxRule();
        $rule->id_tax_rules_group = $groupId; $rule->id_tax = $taxId; $rule->id_country = $countryId;
        $rule->id_state = $stateId; $rule->behavior = 0; $rule->description = '';
        $rule->zipcode_from = 0; $rule->zipcode_to = 0; $rule->add();
    }

    /** @When /^I delete tax rules that has tax "([^"]+)":$/ */
    public function deleteRules(string $taxRef): void
    {
        TaxRule::deleteTaxRuleByIdTax($this->referenceToId($taxRef));
        Cache::clean('Product::getTaxesInformations*');
    }

    /** @Then /^product ([^ ]+) should not have any suppliers assigned$/ */
    public function noSuppliers(string $ref): void
    {
        $id = $this->referenceToId($ref);
        Assert::assertSame([], Db::getInstance()->executeS('SELECT id_supplier FROM '._DB_PREFIX_.'product_supplier WHERE id_product='.(int)$id));
    }

    /** @Then /^product ([^ ]+) should not have a default supplier$/ */
    public function noDefaultSupplier(string $ref): void
    {
        Assert::assertSame(0, (int) (new Product($this->referenceToId($ref)))->id_supplier);
    }
}
