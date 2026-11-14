<?php

namespace Tests\Integration\Behaviour\Features\Context\Discount;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use DateTimeImmutable;
use Language;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\AddDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRule;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleGroup;
use PrestaShop\PrestaShop\Core\Domain\Discount\ProductRuleType;
use PrestaShop\PrestaShop\Core\Domain\Discount\Query\GetDiscountForEditing;
use PrestaShop\PrestaShop\Core\Domain\Discount\QueryResult\DiscountForEditing;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;
use Tests\Integration\Behaviour\Features\Context\CommonFeatureContext;

/**
 * @todo Product and shop/customer fixture setup is deliberately kept in this context:
 * the original feature context tree was removed from the generated repository.
 */
class RestrictedProductsDiscountContext extends AbstractDomainFeatureContext implements Context
{
    /** @var array<string, int> */
    private array $productIds = [];

    /**
     * @Given /^there is a customer named "([^"]+)" whose email is "([^"]+)"$/
     */
    public function customer(string $reference, string $email): void
    {
        $customer = new \Customer();
        $customer->email = $email;
        $customer->firstname = 'Test';
        $customer->lastname = 'Customer';
        $customer->passwd = \Tools::hash('password');
        $customer->id_default_group = (int) \Configuration::get('PS_CUSTOMER_GROUP');
        $customer->add();
        $this->getSharedStorage()->set($reference, (int) $customer->id);
    }

    /** @Given /^language with iso code "([^"]+)" is the default one$/ */
    public function defaultLanguage(string $iso): void
    {
        $language = new Language((int) Language::getIdByIso($iso));
        \Configuration::updateValue('PS_LANG_DEFAULT', (int) $language->id);
    }

    /** @Given /^language "([^"]+)" with locale "([^"]+)" exists$/ */
    public function language(string $name, string $locale): void
    {
        if (Language::getIdByLocale($locale, true)) {
            return;
        }
        $language = new Language();
        $language->name = $name;
        $language->iso_code = substr($locale, 0, 2);
        $language->language_code = str_replace('-', '_', $locale);
        $language->locale = $locale;
        $language->active = true;
        $language->add();
    }

    /** @Given /^shop "([^"]+)" with name "([^"]+)" exists$/ */
    public function shop(string $reference, string $name): void
    {
        $shop = new \Shop((int) \Configuration::get('PS_SHOP_DEFAULT'));
        $this->getSharedStorage()->set($reference, (int) $shop->id);
    }

    /** @Given /^there is a currency named "([^"]+)" with iso code "([^"]+)" and exchange rate of ([\d.]+)$/ */
    public function currency(string $reference, string $iso, string $rate): void
    {
        $currency = \Currency::getCurrencyInstance((int) \Currency::getIdByIsoCode($iso));
        if (!\Validate::isLoadedObject($currency)) {
            $currency = new \Currency();
            $currency->name = $iso;
            $currency->iso_code = $iso;
            $currency->conversion_rate = (float) $rate;
            $currency->active = true;
            $currency->add();
        }
        $this->getSharedStorage()->set($reference, (int) $currency->id);
    }

    /** @Given /^I add product "([^"]+)" with following information:$/ */
    public function addProduct(string $reference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $product = new \Product();
        $product->name = array_fill_keys(array_keys(\Language::getLanguages(false)), $data['name[en-US]']);
        foreach ($data as $key => $value) {
            if (preg_match('/^name\[(.+)\]$/', $key, $m)) {
                $id = (int) Language::getIdByLocale($m[1], true);
                if ($id) {
                    $product->name[$id] = $value;
                }
            }
        }
        $product->link_rewrite = array_map(static fn ($v) => \Tools::str2url($v), $product->name);
        $product->price = 0;
        $product->id_tax_rules_group = 0;
        $product->active = 0;
        $product->add();
        $this->productIds[$reference] = (int) $product->id;
        $this->getSharedStorage()->set($reference, (int) $product->id);
    }

    /** @Given /^I update product "([^"]+)" stock with following information:$/ */
    public function stock(string $reference, TableNode $table): void
    {
        \StockAvailable::setQuantity($this->productId($reference), 0, (int) $table->getRowsHash()['delta_quantity']);
    }

    /** @Given /^I enable product "([^"]+)"$/ */
    public function enableProduct(string $reference): void
    {
        $product = new \Product($this->productId($reference));
        $product->active = true;
        $product->save();
    }

    /** @Given /^I update product "([^"]+)" with following values:$/ */
    public function updateProduct(string $reference, TableNode $table): void
    {
        $product = new \Product($this->productId($reference));
        $product->price = (float) $table->getRowsHash()['price'];
        $product->save();
    }

    /** @When /^I create a "([^"]+)" discount "([^"]+)" with following properties:$/ */
    public function createDiscount(string $type, string $reference, TableNode $table): void
    {
        $rows = $table->getRowsHash();
        $names = [];
        foreach (['en-US', 'fr-FR'] as $locale) {
            $id = (int) Language::getIdByLocale($locale, true);
            if ($id) {
                $names[$id] = $rows["name[$locale]"];
            }
        }
        $command = new AddDiscountCommand($type, $names);
        $command->setActive(filter_var($rows['active'], FILTER_VALIDATE_BOOLEAN));
        $command->setCode($rows['code']);
        $command->setValidityDateRange(new DateTimeImmutable($rows['valid_from']), new DateTimeImmutable($rows['valid_to']));
        $ids = array_map(fn ($ref) => $this->productId(trim($ref)), explode(',', $rows['productCondition[products]']));
        $command->setProductConditions([new ProductRuleGroup((int) $rows['productConditionQuantity'], [new ProductRule(ProductRuleType::PRODUCTS, $ids)])]);
        $result = $this->getCommandBus()->handle($command);
        $id = is_object($result) && method_exists($result, 'getValue') ? $result->getValue() : (int) $result;
        $this->getSharedStorage()->set($reference, $id);
    }

    /** @Then /^discount "([^"]+)" should have the following properties:$/ */
    public function assertDiscount(string $reference, TableNode $table): void
    {
        $discount = $this->getQueryBus()->handle(new GetDiscountForEditing($this->referenceToId($reference)));
        if (!$discount instanceof DiscountForEditing) {
            throw new \RuntimeException('Expected discount editing result');
        }
        $actual = [
            'active' => $discount->isActive() ? 'true' : 'false',
            'code' => $discount->getCode(),
            'minimum_product_quantity' => (string) $discount->getMinimumProductQuantity(),
            'valid_from' => $discount->getValidFrom()->format('Y-m-d H:i:s'),
            'valid_to' => $discount->getValidTo()->format('Y-m-d H:i:s'),
        ];
        foreach ($table->getRowsHash() as $key => $expected) {
            if (preg_match('/^name\[(.+)\]$/', $key, $m)) {
                $langId = (int) Language::getIdByLocale($m[1], true);
                if (($discount->getLocalizedNames()[$langId] ?? null) !== $expected) {
                    throw new \RuntimeException("Discount localized name mismatch for {$m[1]}");
                }
            } elseif ($key === 'productConditionQuantity') {
                $groups = $discount->getProductConditions();
                if (!$groups || $groups[0]->getQuantity() !== (int) $expected) {
                    throw new \RuntimeException('Discount product condition quantity mismatch');
                }
            } elseif ($key === 'productCondition[products]') {
                $rules = $discount->getProductConditions()[0]->getRules();
                $ids = array_map(fn ($ref) => $this->productId(trim($ref)), explode(',', $expected));
                if ($rules[0]->getItemIds() !== $ids) {
                    throw new \RuntimeException('Discount product condition products mismatch');
                }
            } elseif (($actual[$key] ?? null) !== $expected) {
                throw new \RuntimeException("Discount property {$key} mismatch");
            }
        }
    }

    private function productId(string $reference): int
    {
        return $this->productIds[$reference] ?? $this->referenceToId($reference);
    }
}
