<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\PaymentProvider;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Context\CompositeCartContext;
use CoreShop\Component\Payment\Model\PaymentProviderRule;
use CoreShop\Component\Payment\Repository\PaymentProviderRepositoryInterface;
use CoreShop\Component\Resource\Model\ResourceInterface;
use CoreShop\Component\Rule\Condition\RuleValidationProcessor;
use Doctrine\ORM\EntityManagerInterface;
use Webmozart\Assert\Assert;

/**
 * Steps for the payment-provider zone-rule scenario.
 *
 * Rule groups are persisted with a rule because the payment-provider checker
 * evaluates groups attached to the selected provider.
 */
final class PaymentProviderZoneRuleContext implements Context
{
    private ?PaymentProviderRule $rule = null;
    private array $zones = [];

    public function __construct(
        private EntityManagerInterface $entityManager,
        private CompositeCartContext $cartContext,
        private RuleValidationProcessor $ruleValidationProcessor,
        private PaymentProviderRepositoryInterface $paymentProviderRepository,
        private string $locale = 'en',
    ) {
    }

    /** @Given /^adding a payment-provider-rule named "([^"]*)"$/ */
    public function addingPaymentProviderRule(string $name): void
    {
        $this->rule = new PaymentProviderRule();
        $this->rule->setName($name);
        $this->rule->setLabel($name, $this->locale);
    }

    /** @Given /^the payment-provider-rule is active$/ */
    public function paymentProviderRuleIsActive(): void
    {
        Assert::notNull($this->rule, 'Create the payment-provider rule first.');
        $this->rule->setActive(true);
    }

    /** @Given /^the site has a zone "([^"]*)"$/ */
    public function siteHasZone(string $name): void
    {
        $class = \CoreShop\Component\Address\Model\Zone::class;
        $zone = $this->entityManager->getRepository($class)->findOneBy(['name' => $name]);
        if (null === $zone) {
            $zone = new $class();
            $zone->setName($name);
            $this->entityManager->persist($zone);
            $this->entityManager->flush();
        }
        $this->zones[$name] = $zone;
    }

    /** @Given /^the payment-provider-rule has a condition zones with zone "([^"]*)"$/ */
    public function paymentProviderRuleHasZoneCondition(string $zoneName): void
    {
        Assert::notNull($this->rule, 'Create the payment-provider rule first.');
        Assert::keyExists($this->zones, $zoneName, 'Create the zone first.');

        $condition = new \CoreShop\Component\Rule\Model\Condition();
        $condition->setType('zones');
        $condition->setSort(0);
        $condition->setConfiguration(['zones' => [$this->zones[$zoneName]->getId()]]);
        $this->rule->addCondition($condition);
    }

    /** @Then /^the payment-provider-rule should be invalid for my cart with payment provider "([^"]*)"$/ */
    public function paymentProviderRuleShouldBeInvalid(string $providerTitle): void
    {
        Assert::notNull($this->rule, 'Create the payment-provider rule first.');
        $providers = $this->paymentProviderRepository->findByTitle($providerTitle, $this->locale);
        Assert::count($providers, 1, sprintf('Expected one payment provider titled "%s".', $providerTitle));

        // The rule-validation processor receives the cart as its resource subject.
        $cart = $this->cartContext->getCart();
        Assert::false(
            $this->ruleValidationProcessor->isValid($cart, $this->rule, ['paymentProvider' => $providers[0]]),
            'Expected the payment-provider rule to be invalid for this cart.',
        );
    }
}
