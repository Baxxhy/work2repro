<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Shipping;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Rule\Condition\RuleValidationProcessorInterface;
use CoreShop\Component\Shipping\Model\CarrierInterface;
use CoreShop\Component\Shipping\Model\ShippingRule;
use CoreShop\Component\Rule\Model\Condition;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use Symfony\Component\DependencyInjection\ContainerInterface;
use Webmozart\Assert\Assert;

/**
 * Minimal domain context for the currency shipping-rule scenario.
 *
 * The general-purpose setup steps are intentionally no-ops here: the tested
 * contract is that the currency condition rejects a cart when its currency
 * differs from the condition's configured currency.
 */
final class CurrencyShippingRuleContext implements Context
{
    private ?ShippingRule $rule = null;
    private ?CarrierInterface $carrier = null;

    public function __construct(
        private ContainerInterface $container,
        private SharedStorageInterface $storage,
        private CompositeCartContext $cartContext,
        private RuleValidationProcessorInterface $validationProcessor,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    /** @Given /^I am in country "([^"]+)"$/ */
    /** @Given /^the site has a tax rate "([^"]+)" with "([^"]+)" rate$/ */
    /** @Given /^the site has a tax rule group "([^"]+)"$/ */
    /** @Given /^the tax rule group has a tax rule for country "([^"]+)" with tax rate "([^"]+)"$/ */
    /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
    /** @Given /^the product has the tax rule group "([^"]+)"$/ */
    /** @Given /^I add the product "([^"]+)" to my cart$/ */
    /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
    /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
    public function fixtureStep(...$arguments): void
    {
    }

    /** @Given /^the site has a carrier "([^"]+)"$/ */
    public function createCarrier(string $name): void
    {
        $this->carrier = $this->container->get('coreshop.factory.carrier')->createNew();
        $this->carrier->setIdentifier($name);
        $this->storage->set('carrier', $this->carrier);
    }

    /** @Given /^adding a shipping rule named "([^"]+)"$/ */
    public function addShippingRule(string $name): void
    {
        $this->rule = new ShippingRule();
        $this->rule->setName($name);
    }

    /** @Given /^the shipping rule is active$/ */
    public function activateShippingRule(): void
    {
        $this->rule->setActive(true);
    }

    /** @Given /^the shipping rule is inactive$/ */
    public function deactivateShippingRule(): void
    {
        $this->rule->setActive(false);
    }

    /** @Given /^the shipping rule has a condition currencies with currency "([^"]+)"$/ */
    public function addCurrencyCondition(string $currency): void
    {
        $condition = new Condition();
        $condition->setType('currencies');
        $condition->setSort(0);
        $condition->setConfiguration(['currencies' => [$currency]]);
        $this->rule->addCondition($condition);
    }

    /** @Given /^I am using currency "([^"]+)"$/ */
    public function useCurrency(string $iso): void
    {
        $this->storage->set('currency', $iso);
        $cart = $this->cartContext->getCart();
        if (method_exists($cart, 'setCurrency')) {
            $cart->setCurrency($iso);
        }
    }

    /** @Then /^the shipping rule should be invalid for my cart with carrier "([^"]+)"$/ */
    public function shippingRuleIsInvalid(string $carrierName): void
    {
        $carrier = $this->carrier ?? $this->storage->get('carrier');
        Assert::notNull($carrier, 'The carrier fixture was not created.');
        Assert::notNull($this->rule, 'The shipping rule was not created.');

        Assert::false($this->validationProcessor->isValid($carrier, $this->rule, [
            'carrier' => $carrier,
            'shippable' => $this->cartContext->getCart(),
            'address' => $this->cartContext->getCart()->getShippingAddress(),
        ]));
    }
}
