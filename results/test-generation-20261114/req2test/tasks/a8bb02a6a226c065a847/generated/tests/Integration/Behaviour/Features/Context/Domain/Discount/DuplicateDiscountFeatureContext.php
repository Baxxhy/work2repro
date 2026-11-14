<?php

namespace Tests\Integration\Behaviour\Features\Context\Domain\Discount;

use Behat\Gherkin\Node\TableNode;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\AddDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\DuplicateDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRule;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleGroup;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleType;
use PrestaShop\PrestaShop\Core\Domain\Discount\Query\GetDiscountForEditing;
use RuntimeException;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

class DuplicateDiscountFeatureContext extends AbstractDomainFeatureContext
{
    /**
     * @Given I add new supplier :reference with the following properties:
     */
    public function addSupplier(string $reference, TableNode $table): void
    {
        $values = $table->getRowsHash();
        $languages = \Language::getLanguages(false);
        $localized = static function (string $field) use ($values, $languages): array {
            $result = [];
            foreach ($languages as $language) {
                $locale = $language['locale'] ?? '';
                $key = $field . '[' . $locale . ']';
                if (array_key_exists($key, $values)) {
                    $result[(int) $language['id_lang']] = $values[$key];
                }
            }
            return $result;
        };

        $supplier = new \Supplier();
        $supplier->name = $values['name'];
        $supplier->active = strtolower($values['enabled'] ?? 'true') === 'true';
        $supplier->description = $localized('description');
        $supplier->meta_title = $localized('meta title');
        $supplier->meta_description = $localized('meta description');
        if (!$supplier->add()) {
            throw new RuntimeException('Could not create supplier');
        }

        $countryId = (int) \Country::getByName((int) \Configuration::get('PS_LANG_DEFAULT'), $values['country']);
        if ($countryId > 0) {
            $address = new \Address();
            $address->id_supplier = (int) $supplier->id;
            $address->id_country = $countryId;
            $address->alias = $values['name'];
            $address->address1 = $values['address'];
            $address->city = $values['city'];
            $address->save();
        }
        $this->getSharedStorage()->set($reference, (int) $supplier->id);
    }

    /**
     * @When I create a :type discount :reference with following properties:
     */
    public function createDiscount(string $type, string $reference, TableNode $table): void
    {
        $properties = $table->getRowsHash();
        $names = $this->localizeByRows($table)['name'] ?? [];
        $command = new AddDiscountCommand($type, $names);

        if (isset($properties['productConditionQuantity'], $properties['productCondition[suppliers]'])) {
            $supplierId = $this->referenceToId(trim($properties['productCondition[suppliers]']));
            $command->setProductConditions([
                new ProductRuleGroup((int) $properties['productConditionQuantity'], [
                    new ProductRule(ProductRuleType::SUPPLIERS, [$supplierId]),
                ]),
            ]);
        }

        $result = $this->getCommandBus()->handle($command);
        $id = is_object($result) && method_exists($result, 'getValue') ? $result->getValue() : (int) $result;
        if ($id <= 0) {
            throw new RuntimeException('Creating discount did not return a valid discount ID');
        }
        $this->getSharedStorage()->set($reference, $id);
    }

    /**
     * @When I duplicate the discount :reference as :newReference
     */
    public function duplicateDiscount(string $reference, string $newReference): void
    {
        $result = $this->getCommandBus()->handle(new DuplicateDiscountCommand($this->referenceToId($reference)));
        $id = is_object($result) && method_exists($result, 'getValue') ? $result->getValue() : (int) $result;
        if ($id <= 0) {
            throw new RuntimeException('Duplicating discount did not return a valid discount ID');
        }
        $this->getSharedStorage()->set($newReference, $id);
    }

    /**
     * @Then discount :reference should have the following properties:
     */
    public function discountShouldHaveProperties(string $reference, TableNode $table): void
    {
        $discount = $this->getQueryBus()->handle(new GetDiscountForEditing($this->referenceToId($reference)));
        $actualNames = $discount->getLocalizedNames();
        foreach ($table->getRowsHash() as $property => $expected) {
            switch ($property) {
                case 'name[en-US]':
                    $langId = (int) \Language::getIdByLocale('en-US', true);
                    $actual = $actualNames[$langId] ?? null;
                    break;
                case 'type':
                    $actual = $discount->getType()->getValue();
                    break;
                case 'minimum_product_quantity':
                    $actual = $discount->getMinimumProductQuantity();
                    break;
                case 'active':
                    $actual = $discount->isActive();
                    break;
                case 'productConditionQuantity':
                    $conditions = $discount->getProductConditions();
                    $actual = $conditions ? $conditions[0]->getQuantity() : null;
                    break;
                case 'productCondition[suppliers]':
                    $conditions = $discount->getProductConditions();
                    $rules = $conditions ? $conditions[0]->getRules() : [];
                    $actual = null;
                    foreach ($rules as $rule) {
                        if ($rule->getType() === ProductRuleType::SUPPLIERS) {
                            $actual = $rule->getItemIds()[0] ?? null;
                        }
                    }
                    $expected = $this->referenceToId(trim($expected));
                    break;
                default:
                    throw new RuntimeException(sprintf('Unsupported discount property "%s"', $property));
            }

            if ((string) $actual !== (string) $expected) {
                throw new RuntimeException(sprintf('Discount property "%s": expected "%s", got "%s"', $property, $expected, var_export($actual, true)));
            }
        }
    }
}
