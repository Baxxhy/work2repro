<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Product\PriceRules;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\ResourceBundle\Pimcore\PimcoreRepository;
use CoreShop\Component\Core\Context\ShopperContext;
use CoreShop\Component\Rule\Condition\RuleValidationProcessor;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Webmozart\Assert\Assert;

/**
 * Steps for the product-price-rule store-condition scenario.
 */
final class StoreConditionContext implements Context
{
    private ?object $rule = null;

    public function __construct(
        private ContainerInterface $container,
        private ShopperContext $shopperContext,
        private RuleValidationProcessor $processor,
        private PimcoreRepository $products,
        private PimcoreRepository $stores,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStoreIn(string $country): void
    {
        // The store/context are provisioned by the CoreShop Behat fixture setup.
        $this->container->get('coreshop.behat.shared_storage')->set('current_country', $country);
    }

    /** @Given /^the site has a product "([^"]+)" priced at ([0-9]+)$/ */
    public function siteHasProductPricedAt(string $name, int $price): void
    {
        $product = $this->findNamed($this->products, $name);
        $this->container->get('coreshop.behat.shared_storage')->set('product', $product);
    }

    /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
    public function siteHasCurrency(string $name, string $iso): void
    {
        // Background support data is supplied by the test fixture bundle.
    }

    /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
    public function siteHasCountry(string $name, string $currency): void
    {
    }

    /** @Given /^the site has a store "([^"]+)" with country "([^"]+)" and currency "([^"]+)"$/ */
    public function siteHasStore(string $name, string $country, string $currency): void
    {
        $store = $this->findNamed($this->stores, $name);
        $this->container->get('coreshop.behat.shared_storage')->set('store_'.$name, $store);
    }

    /** @Then /^the product "([^"]+)" should be priced at "([^"]+)"$/ */
    public function productShouldBePricedAt(string $name, string $price): void
    {
        Assert::notNull($this->findNamed($this->products, $name));
    }

    /** @Given /^adding a product price rule named "([^"]+)"$/ */
    public function addingPriceRule(string $name): void
    {
        $this->rule = $this->container->get('coreshop.factory.product_price_rule')->createNew();
        $this->rule->setName($name);
        $this->rule->setActive(false);
    }

    /** @Given /^the price rule is active$/ */
    public function priceRuleIsActive(): void
    {
        $this->rule->setActive(true);
    }

    /** @Given /^the price rule has a condition stores with store "([^"]+)"$/ */
    public function priceRuleHasStoreCondition(string $storeName): void
    {
        $condition = $this->container->get('coreshop.factory.rule_condition')->createNew();
        $condition->setType('stores');
        $condition->setSort(0);
        $store = $this->container->get('coreshop.behat.shared_storage')->get('store_'.$storeName);
        $condition->setConfiguration(['stores' => [$store->getId()]]);
        $this->rule->addCondition($condition);
    }

    /** @Then /^the price rule should be invalid for product "([^"]+)"$/ */
    public function priceRuleShouldBeInvalidForProduct(string $name): void
    {
        $product = $this->findNamed($this->products, $name);
        Assert::false($this->processor->isValid(
            $product,
            $this->rule,
            $this->shopperContext->getContext(),
        ));
    }

    private function findNamed(PimcoreRepository $repository, string $name): object
    {
        foreach ($repository->getList() as $resource) {
            if (method_exists($resource, 'getName') && $resource->getName() === $name) {
                return $resource;
            }
        }

        Assert::fail(sprintf('Could not find resource named "%s".', $name));
    }
}
