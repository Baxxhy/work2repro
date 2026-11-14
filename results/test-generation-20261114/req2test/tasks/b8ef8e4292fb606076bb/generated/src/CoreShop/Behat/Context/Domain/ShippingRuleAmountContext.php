<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Resource\Factory\PimcoreFactory;
use CoreShop\Component\Rule\Condition\RuleValidationProcessor;
use CoreShop\Component\Rule\Model\Condition;
use CoreShop\Component\Shipping\Model\CarrierInterface;
use CoreShop\Component\Shipping\Model\ShippingRuleInterface;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use Webmozart\Assert\Assert;

final class ShippingRuleAmountContext implements Context
{
    private ?ShippingRuleInterface $rule = null;

    public function __construct(
        private PimcoreFactory $shippingRuleFactory,
        private CompositeCartContext $cartContext,
        private RuleValidationProcessor $validationProcessor,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    /** @Given /^adding a shipping rule named "([^"]+)"$/ */
    public function addingShippingRule(string $name): void
    {
        $this->rule = $this->shippingRuleFactory->createNew();
        $this->rule->setName($name);
    }

    /** @Given /^the shipping rule is active$/ */
    public function shippingRuleIsActive(): void
    {
        $this->rule()->setActive(true);
    }

    /** @Given /^the shipping rule has a condition amount from "([^"]+)" to "([^"]+)"$/ */
    public function shippingRuleHasAmountCondition(string $minimum, string $maximum): void
    {
        $condition = (new Condition())
            ->setType('amount')
            ->setSort(0)
            ->setConfiguration(['minAmount' => (int) $minimum, 'maxAmount' => (int) $maximum]);
        $this->rule()->addCondition($condition);
    }

    /** @Then /^the shipping rule should be invalid for my cart with carrier "([^"]+)"$/ */
    public function shippingRuleIsInvalidForCart(string $carrierName): void
    {
        $carrier = $this->sharedStorage->get('carrier');
        Assert::isInstanceOf($carrier, CarrierInterface::class);
        Assert::same($carrierName, $carrier->getName());

        $cart = $this->cartContext->getCart();
        $address = $cart->getShippingAddress();
        Assert::notNull($address);
        Assert::false($this->validationProcessor->isValid($cart, $this->rule(), [
            'carrier' => $carrier,
            'address' => $address,
        ]));
    }

    private function rule(): ShippingRuleInterface
    {
        Assert::notNull($this->rule, 'Create the shipping rule before configuring it.');

        return $this->rule;
    }
}
