<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Cart;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Order\Model\OrderInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Webmozart\Assert\Assert;

/**
 * Steps for the net-cart tax feature.
 *
 * The fixture creation steps deliberately use the CoreShop Behat fixture
 * builders when present; all created resources are kept in shared storage so
 * the later product steps use the exact objects created by the background.
 */
final class CartTaxationContext implements Context
{
    public function __construct(
        private ContainerInterface $container,
        private SharedStorageInterface $storage,
        private CompositeCartContext $cartContext,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStore(string $country): void
    {
        $this->fixture('store', ['country' => $country]);
    }

    /** @Given /^the site has a tax rate "([^"]+)" with "([^"]+)" rate$/ */
    public function siteHasTaxRate(string $name, string $rate): void
    {
        $this->fixture('tax_rate', ['name' => $name, 'rate' => $rate]);
    }

    /** @Given /^the site has a tax rule group "([^"]+)"$/ */
    public function siteHasTaxRuleGroup(string $name): void
    {
        $this->fixture('tax_rule_group', ['name' => $name]);
    }

    /** @Given /^the tax rule group has a tax rule for country "([^"]+)" with tax rate "([^"]+)"$/ */
    public function taxRuleGroupHasRule(string $country, string $rate): void
    {
        $this->fixture('tax_rule', ['country' => $country, 'rate' => $rate]);
    }

    /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
    public function siteHasProduct(string $name, int $price): void
    {
        $product = $this->fixture('product', ['name' => $name, 'price' => $price]);
        $this->storage->set('product_'.$name, $product);
        $this->storage->set('last_product', $product);
    }

    /** @Given /^the product has the tax rule group "([^"]+)"$/ */
    public function productHasTaxRuleGroup(string $group): void
    {
        $product = $this->storage->get('last_product');
        $this->fixture('assign_product_tax_rule_group', ['product' => $product, 'group' => $group]);
    }

    /** @Given /^I add the product "([^"]+)" to my cart$/ */
    public function addProductToCart(string $name): void
    {
        $product = $this->storage->get('product_'.$name);
        Assert::notNull($product, sprintf('Product "%s" was not found.', $name));

        /** @var OrderInterface $cart */
        $cart = $this->cartContext->getCart();
        $modifier = $this->container->get('coreshop.cart.modifier');
        $itemFactory = $this->container->get('coreshop.factory.order_item');
        $item = $itemFactory->createNew();
        $item->setProduct($product);
        $item->setQuantity(1);
        $modifier->addToList($cart, $item);
    }

    /** @Then /^the cart total tax should be "([^"]+)"$/ */
    public function cartTotalTaxShouldBe(string $expected): void
    {
        Assert::same((int) $expected, $this->cartContext->getCart()->getTotalTax());
    }

    /**
     * Dispatch to the fixture service supplied by the CoreShop test environment.
     *
     * Keeping fixture construction behind this adapter avoids duplicating
     * Pimcore object lifecycle/persistence rules in the step definitions.
     */
    private function fixture(string $type, array $data): mixed
    {
        $builder = $this->container->get('coreshop.behat.fixture_builder');

        return $builder->create($type, $data);
    }
}
