<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Order;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use CoreShop\Bundle\WorkflowBundle\Applier\StateMachineApplierInterface;
use CoreShop\Component\Order\Model\OrderInterface;
use CoreShop\Component\Payment\Model\PaymentInterface;
use CoreShop\Component\Resource\Factory\FactoryInterface;
use CoreShop\Component\Resource\Repository\RepositoryInterface;
use Webmozart\Assert\Assert;

/**
 * Order/payment steps for order_payment.feature.
 *
 * The shared clipboard keys are the ones used by the CoreShop domain contexts:
 * `order`, `payment_provider`, and `payment`.
 */
final class OrderPaymentContext implements Context
{
    public function __construct(
        private SharedStorageInterface $storage,
        private FactoryInterface $paymentFactory,
        private RepositoryInterface $paymentRepository,
        private StateMachineApplierInterface $stateMachineApplier,
    ) {
    }

    /** @Given /^I create a payment for my order with payment provider "([^"]+)" and amount (\d+)$/ */
    public function createPayment(string $providerName, int $amount): void
    {
        /** @var OrderInterface $order */
        $order = $this->storage->get('order');
        $provider = $this->storage->get('payment_provider');

        $payment = $this->paymentFactory->createNew();
        $payment->setPaymentProvider($provider);
        $payment->setTotalAmount($amount);
        $payment->setState(PaymentInterface::STATE_NEW);
        $payment->setDatePayment(new \DateTime());
        $payment->setCurrencyCode($order->getCurrency()->getIsoCode());
        $payment->setNumber(uniqid('behat-payment-', true));
        $payment->setDescription('Behat order payment');
        $payment->setDetails([]);
        $payment->setOrder($order);
        $this->paymentRepository->add($payment);

        $this->storage->set('payment', $payment);
    }

    /** @Given /^I apply payment transition "([^"]+)" to latest order payment$/ */
    public function applyPaymentTransition(string $transition): void
    {
        $payment = $this->storage->get('payment');
        $this->stateMachineApplier->apply($payment, 'coreshop_payment', $transition);
    }

    /** @Then /^the order payment state should be "([^"]+)"$/ */
    public function orderPaymentStateShouldBe(string $state): void
    {
        /** @var OrderInterface $order */
        $order = $this->storage->get('order');
        Assert::same($order->getPaymentState(), $state);
    }

    /** @Then /^the order state should be "([^"]+)"$/ */
    public function orderStateShouldBe(string $state): void
    {
        /** @var OrderInterface $order */
        $order = $this->storage->get('order');
        Assert::same($order->getOrderState(), $state);
    }
}
