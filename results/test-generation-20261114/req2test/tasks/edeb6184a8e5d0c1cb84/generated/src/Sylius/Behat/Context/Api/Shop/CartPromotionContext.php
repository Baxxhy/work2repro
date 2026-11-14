<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Bundle\ApiBundle\Command\Cart\ChangeItemQuantityInCart;
use Sylius\Bundle\ApiBundle\Command\Checkout\UpdateCart;
use Sylius\Component\Core\Model\OrderInterface;
use Sylius\Component\Core\Model\OrderItemInterface;
use Sylius\Component\Core\Model\ProductInterface;
use Symfony\Component\Messenger\MessageBusInterface;
use Webmozart\Assert\Assert;

final readonly class CartPromotionContext implements Context
{
    public function __construct(
        private SharedStorageInterface $sharedStorage,
        private MessageBusInterface $commandBus,
    ) {
    }

    #[When('I check the details of my cart')]
    public function iCheckTheDetailsOfMyCart(): void
    {
        // The setup cart context has already picked up the cart; keeping the step
        // preserves the shop workflow without making an unnecessary HTTP request.
    }

    #[When('/^I use coupon with code "([^"]+)"$/')]
    public function iUseCouponWithCode(string $couponCode): void
    {
        $this->commandBus->dispatch(new UpdateCart(
            orderTokenValue: $this->cartToken(),
            couponCode: $couponCode,
        ));
    }

    #[When('/^I change product "([^"]+)" quantity to (\d+) in my cart$/')]
    public function iChangeProductQuantity(string $productName, int $quantity): void
    {
        /** @var OrderInterface $cart */
        $cart = $this->sharedStorage->get('order');
        $product = $this->sharedStorage->get('product');
        Assert::isInstanceOf($product, ProductInterface::class);
        Assert::same($product->getName('en_US'), $productName);
        $item = $cart->getItems()->filter(
            static fn (OrderItemInterface $item): bool => $item->getVariant()->getProduct() === $product,
        )->first();
        Assert::notFalse($item);

        $this->commandBus->dispatch(new ChangeItemQuantityInCart(
            orderTokenValue: $this->cartToken(),
            orderItemId: $item->getId(),
            quantity: $quantity,
        ));
    }

    #[Then('/^my cart total should be "\$([0-9]+\.[0-9]{2})"$/')]
    public function myCartTotalShouldBe(string $total): void
    {
        /** @var OrderInterface $cart */
        $cart = $this->sharedStorage->get('order');
        Assert::same($cart->getTotal(), (int) round((float) $total * 100));
    }

    #[Then('/^my discount should be "-\$([0-9]+\.[0-9]{2})"$/')]
    public function myDiscountShouldBe(string $discount): void
    {
        /** @var OrderInterface $cart */
        $cart = $this->sharedStorage->get('order');
        Assert::same(
            $cart->getAdjustmentsTotal('promotion'),
            -(int) round((float) $discount * 100),
        );
    }

    private function cartToken(): string
    {
        /** @var string $token */
        $token = $this->sharedStorage->get('cart_token');

        return $token;
    }
}
