<?php

namespace Tests\Integration\Behaviour\Features\Context;

use Behat\Gherkin\Node\TableNode;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\AddDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRule;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleGroup;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleGroupType;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleType;
use PrestaShop\PrestaShop\Core\Domain\Discount\Query\GetDiscountForEditing;
use PrestaShop\PrestaShop\Core\Domain\Manufacturer\Command\AddManufacturerCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\ValueObject\DiscountId;
use PrestaShop\PrestaShop\Core\Domain\Manufacturer\ValueObject\ManufacturerId;
use RuntimeException;
use Shop;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

class DiscountBrandTriggerContext extends AbstractDomainFeatureContext
{
    /** @Given /^shop "([^"]+)" with name "([^"]+)" exists$/ */
    public function ensureShopExists(string $reference, string $name): void
    {
        $shop = $this->getSharedStorage()->exists($reference) ? new Shop((int) $this->getSharedStorage()->get($reference)) : null;
        if ($shop === null || !\Validate::isLoadedObject($shop)) {
            $shop = new Shop();
            $shop->name = $name;
            $shop->id_category = (int) \Configuration::get('PS_ROOT_CATEGORY');
            $shop->id_theme = (int) \Configuration::get('PS_THEME');
            $shop->active = true;
            $shop->add();
        }
        $this->getSharedStorage()->set($reference, (int) $shop->id);
    }

    /** @Given /^there is a currency named "([^"]+)" with iso code "([^"]+)" and exchange rate of ([0-9.]+)$/ */
    public function ensureCurrencyExists(string $reference, string $isoCode, string $exchangeRate): void
    {
        $currencyId = (int) \Currency::getIdByIsoCode($isoCode);
        if (!$currencyId) {
            $currency = new Currency();
            $currency->name = strtoupper($reference);
            $currency->iso_code = $isoCode;
            $currency->conversion_rate = (float) $exchangeRate;
            $currency->active = true;
            $currency->add();
            $currencyId = (int) $currency->id;
        }
        $this->getSharedStorage()->set($reference, $currencyId);
    }

    /** @Given /^I add new manufacturer "([^"]+)" with following properties:$/ */
    public function addManufacturer(string $reference, TableNode $table): void
    {
        $properties = $this->parseLocalizedRow($table->getRowsHash());
        $command = new AddManufacturerCommand(
            $properties['name'],
            filter_var($properties['enabled'], FILTER_VALIDATE_BOOLEAN),
            $properties['short_description'] ?? [],
            $properties['description'] ?? [],
            $properties['meta_title'] ?? [],
            $properties['meta_description'] ?? [],
            [Shop::getContextShopID()]
        );
        /** @var ManufacturerId $manufacturerId */
        $manufacturerId = $this->getCommandBus()->handle($command);
        $this->getSharedStorage()->set($reference, $manufacturerId->getValue());
    }

    /** @When /^I create a "([^"]+)" discount "([^"]+)" with following properties:$/ */
    public function createDiscount(string $type, string $reference, TableNode $table): void
    {
        $raw = $table->getRowsHash();
        $properties = [];
        $names = [];
        $conditions = [];
        foreach ($raw as $key => $value) {
            if (preg_match('/^name\[([^\]]+)\]$/', $key, $match)) {
                $languageId = (int) \Language::getIdByLocale($match[1], true);
                $names[$languageId] = $value;
            } elseif (preg_match('/^productCondition\[([^\]]+)\]$/', $key, $match)) {
                $conditions[$match[1]] = $value;
            } else {
                $properties[$key] = $value;
            }
        }
        $command = new AddDiscountCommand($type, $names);
        $command->setMinimumProductQuantity(0);

        if (isset($properties['productConditionQuantity'], $conditions['manufacturers'])) {
            $manufacturerIds = $this->referencesToIds($conditions['manufacturers']);
            $command->setProductConditions([
                new ProductRuleGroup(
                    (int) $properties['productConditionQuantity'],
                    [new ProductRule(ProductRuleType::MANUFACTURERS, $manufacturerIds)],
                    ProductRuleGroupType::AT_LEAST_ONE_PRODUCT_RULE
                ),
            ]);
        }

        /** @var DiscountId $discountId */
        $discountId = $this->getCommandBus()->handle($command);
        $this->getSharedStorage()->set($reference, $discountId->getValue());
    }

    /** @Then /^discount "([^"]+)" should have the following properties:$/ */
    public function assertDiscount(string $reference, TableNode $table): void
    {
        $properties = $table->getRowsHash();
        $expectedName = null;
        $expectedType = null;
        $expectedMinimumQuantity = null;
        $expectedConditionQuantity = null;
        $expectedManufacturer = null;
        foreach ($properties as $property => $value) {
            if (preg_match('/^name\[([^\]]+)\]$/', $property, $match)) {
                $expectedName = [(int) \Language::getIdByLocale($match[1], true), $value];
            } elseif ($property === 'type') {
                $expectedType = $value;
            } elseif ($property === 'minimum_product_quantity') {
                $expectedMinimumQuantity = (int) $value;
            } elseif ($property === 'productConditionQuantity') {
                $expectedConditionQuantity = (int) $value;
            } elseif (preg_match('/^productCondition\[manufacturers\]$/', $property)) {
                $expectedManufacturer = $value;
            }
        }
        $discount = $this->getQueryBus()->handle(new GetDiscountForEditing($this->referenceToId($reference)));

        if ($expectedName !== null && ($discount->getLocalizedNames()[$expectedName[0]] ?? null) !== $expectedName[1]) {
            throw new RuntimeException('Discount localized name did not match');
        }
        if ($expectedType !== null && $discount->getType()->getValue() !== $expectedType) {
            throw new RuntimeException('Discount type did not match');
        }
        if ($expectedMinimumQuantity !== null && $discount->getMinimumProductQuantity() !== $expectedMinimumQuantity) {
            throw new RuntimeException('Discount minimum product quantity did not match');
        }
        if ($expectedConditionQuantity !== null || $expectedManufacturer !== null) {
            $groups = $discount->getProductConditions();
            if (count($groups) !== 1) {
                throw new RuntimeException('Expected one product-condition group');
            }
            $group = $groups[0];
            if ($expectedConditionQuantity !== null && $group->getQuantity() !== $expectedConditionQuantity) {
                throw new RuntimeException('Discount product-condition quantity did not match');
            }
            if ($expectedManufacturer !== null) {
                $rule = $group->getRules()[0] ?? null;
                $expectedIds = $this->referencesToIds($expectedManufacturer);
                if ($rule === null || $rule->getType() !== ProductRuleType::MANUFACTURERS || $rule->getItemIds() !== $expectedIds) {
                    throw new RuntimeException('Discount manufacturer condition did not match');
                }
            }
        }
    }
}
