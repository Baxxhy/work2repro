<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\PaymentProvider;

use Behat\Behat\Context\Context;
use CoreShop\Component\Customer\Repository\CustomerRepositoryInterface;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Payment\Repository\PaymentProviderRepositoryInterface;
use CoreShop\Component\Resource\Factory\FactoryInterface;
use CoreShop\Component\Rule\Condition\RuleValidationProcessorInterface;
use CoreShop\Component\Rule\Model\ConditionInterface;
use CoreShop\Component\Rule\Model\RuleInterface;
use Webmozart\Assert\Assert;

final class PaymentProviderRuleContext implements Context
{
    private ?RuleInterface $rule = null;
    private ?bool $valid = null;

    public function __construct(
        private FactoryInterface $paymentProviderRuleFactory,
        private FactoryInterface $conditionFactory,
        private CustomerRepositoryInterface $customerRepository,
        private CompositeCartContext $cartContext,
        private RuleValidationProcessorInterface $validationProcessor,
        private PaymentProviderRepositoryInterface $paymentProviderRepository,
    ) {
    }

    /** @Given /^adding a payment-provider-rule named "([^"]+)"$/ */
    public function addingPaymentProviderRule(string $name): void
    {
        $rule = $this->paymentProviderRuleFactory->createNew();
        $rule->setName($name);
        $this->rule = $rule;
    }

    /** @Given /^the payment-provider-rule is inactive$/ */
    public function paymentProviderRuleIsInactive(): void
    {
        $this->rule()->setActive(false);
    }

    /** @Given /^the payment-provider-rule is active$/ */
    public function paymentProviderRuleIsActive(): void
    {
        $this->rule()->setActive(true);
    }

    /** @Given /^the payment-provider-rule has a condition customers with customer "([^"]+)"$/ */
    public function paymentProviderRuleHasCustomerCondition(string $email): void
    {
        $customer = $this->customerRepository->findCustomerByEmail($email);
        Assert::notNull($customer, sprintf('No customer found for "%s".', $email));

        /** @var ConditionInterface $condition */
        $condition = $this->conditionFactory->createNew();
        $condition->setType('customers');
        $condition->setSort(0);
        $condition->setConfiguration(['customers' => [$customer->getId()]]);
        $this->rule()->addCondition($condition);
    }

    /** @Then /^the payment-provider-rule should be invalid for my cart with payment provider "([^"]+)"$/ */
    public function paymentProviderRuleShouldBeInvalid(string $title): void
    {
        $providers = $this->paymentProviderRepository->findByTitle($title, 'en');
        Assert::notEmpty($providers, sprintf('No payment provider found with title "%s".', $title));
        $this->valid = $this->validationProcessor->isValid($this->cartContext->getCart(), $this->rule(), [
            'paymentProvider' => $providers[0],
        ]);
        Assert::false($this->valid, 'Expected payment-provider-rule to be invalid.');
    }

    private function rule(): RuleInterface
    {
        Assert::notNull($this->rule, 'Create a payment-provider-rule first.');

        return $this->rule;
    }
}
