<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Checkout;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Context\Setup\Checkout\PaymentContext;
use Sylius\Behat\Context\Setup\Checkout\ShippingContext;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Bundle\ApiBundle\Command\Checkout\CompleteOrder;
use Sylius\Component\Core\Model\OrderInterface;
use Sylius\Component\Core\Model\PaymentMethodInterface;
use Sylius\Component\Core\Model\ShippingMethodInterface;
use Symfony\Component\Messenger\MessageBusInterface;
use Webmozart\Assert\Assert;

final readonly class OrderContext implements Context
{
    public function __construct(
        private ShippingContext $shippingContext,
        private PaymentContext $paymentContext,
        private SharedStorageInterface $sharedStorage,
        private MessageBusInterface $commandBus,
    ) {
    }

    #[When('I proceed with :shippingMethod shipping method and :paymentMethod payment')]
    public function iProceedWithShippingAndPayment(ShippingMethodInterface $shippingMethod, PaymentMethodInterface $paymentMethod): void
    {
        $this->shippingContext->chooseShippingMethod($shippingMethod);
        $this->paymentContext->choosePaymentMethod($paymentMethod);
    }

    #[When('I confirm my order')]
    public function iConfirmMyOrder(): void
    {
        /** @var OrderInterface $order */
        $order = $this->sharedStorage->get('order');
        $this->commandBus->dispatch(new CompleteOrder($order->getTokenValue()));
        $this->sharedStorage->set('placed_order', $order);
    }

    #[Then('the administrator should see that order placed by :email has :currency currency')]
    public function administratorShouldSeeOrderCurrency(string $email, string $currency): void
    {
        /** @var OrderInterface $order */
        $order = $this->sharedStorage->get('placed_order');
        Assert::same($order->getCustomer()->getEmail(), $email);
        Assert::same($order->getCurrencyCode(), $currency);
    }
}
