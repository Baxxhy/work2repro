<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\OrderInterface;
use Webmozart\Assert\Assert;

final readonly class PromotionCartContext implements Context
{
    public function __construct(
        private ApiClientInterface $shopApiClient,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I check the details of my cart')]
    public function iCheckTheDetailsOfMyCart(): void
    {
        $this->shopApiClient->requestGet('/shop/orders/' . $this->sharedStorage->get('cart_token'));

        /** @var OrderInterface $order */
        $order = $this->sharedStorage->get('order');
        $this->sharedStorage->set('checked_cart', $order);
    }

    #[Then('/^(?:its|theirs) subtotal price should be decreased by "([^"]+)"$/')]
    public function subtotalPriceShouldBeDecreasedBy(string $amount): void
    {
        $order = $this->checkedCart();
        $regularSubtotal = 0;
        foreach ($order->getItems() as $item) {
            $regularSubtotal += $item->getVariant()->getChannelPricings()->first()->getPrice() * $item->getQuantity();
        }

        Assert::same($regularSubtotal - $order->getItemsSubtotal(), $this->moneyToCents($amount));
    }

    #[Then('my cart total should be :total')]
    public function myCartTotalShouldBe(string $total): void
    {
        Assert::same($this->checkedCart()->getTotal(), $this->moneyToCents($total));
    }

    #[Then('my discount should be :discount')]
    public function myDiscountShouldBe(string $discount): void
    {
        Assert::same($this->checkedCart()->getOrderPromotionTotal(), $this->moneyToCents(ltrim($discount, '-')));
    }

    private function checkedCart(): OrderInterface
    {
        /** @var OrderInterface $order */
        $order = $this->sharedStorage->get('checked_cart');

        return $order;
    }

    private function moneyToCents(string $money): int
    {
        return (int) round((float) preg_replace('/[^0-9.]/', '', $money) * 100);
    }
}
