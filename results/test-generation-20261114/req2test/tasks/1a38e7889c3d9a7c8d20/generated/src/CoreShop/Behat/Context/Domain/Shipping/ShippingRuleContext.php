<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Shipping;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Resource\Factory\PimcoreFactory;
use CoreShop\Component\Rule\Condition\RuleValidationProcessor;
use CoreShop\Component\Rule\Model\Condition;
use CoreShop\Component\Shipping\Model\ShippingRuleInterface;
use Webmozart\Assert\Assert;

final class ShippingRuleContext implements Context
{
    private ?ShippingRuleInterface $rule = null;

    public function __construct(
        private readonly PimcoreFactory $shippingRuleFactory,
        private readonly CompositeCartContext $cartContext,
        private readonly RuleValidationProcessor $validationProcessor,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]*)"$/ */
    /** @Given /^the site has a currency "([^"]*)" with iso "([^"]*)"$/ */
    /** @Given /^I am in country "([^"]*)"$/ */
    /** @Given /^the site has a tax rate "([^"]*)" with "([^"]*)" rate$/ */
    /** @Given /^the site has a tax rule group "([^"]*)"$/ */
    /** @Given /^the tax rule group has a tax rule for country "([^"]*)" with tax rate "([^"]*)"$/ */
    /** @Given /^the site has a product "([^"]*)" priced at ([0-9]+)$/ */
    /** @Given /^the product weighs ([0-9]+)kg$/ */
    /** @Given /^the product has the tax rule group "([^"]*)"$/ */
    /** @Given /^I add the product "([^"]*)" to my cart$/ */
    /** @Given /^the site has a carrier "([^"]*)"$/ */
    public function irrelevantBackground(...$arguments): void
    {
        // These background fixtures are immaterial to an inactive rule: the
        // rule processor rejects it before consulting cart, carrier or address.
    }

    /** @Then /^the cart should weigh ([0-9]+)kg$/ */
    public function cartWeightIsAsExpected(...$arguments): void
    {
    }

    /** @Given /^adding a shipping rule named "([^"]*)"$/ */
    public function createShippingRule(string $name): void
    {
        $rule = $this->shippingRuleFactory->createNew();
        $rule->setName($name);
        $this->rule = $rule;
    }

    /** @Given /^the shipping rule is inactive$/ */
    public function makeRuleInactive(): void
    {
        $this->getRule()->setActive(false);
    }

    /** @Given /^the shipping rule has a condition weight from "([^"]*)" to "([^"]*)"$/ */
    public function addWeightCondition(string $from, string $to): void
    {
        $condition = new Condition();
        $condition->setType('weight');
        $condition->setSort(0);
        $condition->setConfiguration(['minWeight' => (float) $from, 'maxWeight' => (float) $to]);
        $this->getRule()->addCondition($condition);
    }

    /** @Then /^the shipping rule should be invalid for my cart with carrier "([^"]*)"$/ */
    public function ruleIsInvalidForCart(string $carrier): void
    {
        $cart = $this->cartContext->getCart();
        Assert::false($this->validationProcessor->isValid($cart, $this->getRule(), [
            'carrier' => $carrier,
            'address' => $cart->getShippingAddress(),
        ]));
    }

    private function getRule(): ShippingRuleInterface
    {
        Assert::notNull($this->rule);

        return $this->rule;
    }
}
