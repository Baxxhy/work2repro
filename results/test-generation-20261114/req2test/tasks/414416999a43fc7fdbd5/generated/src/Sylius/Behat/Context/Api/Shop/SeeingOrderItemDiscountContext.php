<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\OrderInterface;
use Webmozart\Assert\Assert;

/**
 * Assertions for the order summary exposed by the shop API.
 *
 * The API checkout setup contexts keep the active order in shared storage; the
 * assertions deliberately inspect that order rather than its serialized
 * representation, so they remain independent of the API's JSON-LD shape.
 */
final readonly class SeeingOrderItemDiscountContext implements Context
{
    public function __construct(private SharedStorageInterface $sharedStorage)
    {
    }

    #[Then('I should be on the checkout summary step')]
    public function iShouldBeOnTheCheckoutSummaryStep(): void
    {
        $order = $this->order();
        Assert::notNull($order->getCheckoutState());
    }

    #[Then('the :product product should have unit price discounted by :discount')]
    public function theProductShouldHaveUnitPriceDiscountedBy(string $product, string $discount): void
    {
        $order = $this->order();
        $expected = (int) round((float) str_replace(['$', ','], '', $discount) * 100);

        foreach ($order->getItems() as $item) {
            if ($item->getProductName() !== $product) {
                continue;
            }

            Assert::same($item->getUnitPrice() - $item->getDiscountedUnitPrice(), $expected);

            return;
        }

        Assert::fail(sprintf('Product "%s" was not found in the order.', $product));
    }

    #[Then('my order total should be :total')]
    public function myOrderTotalShouldBe(string $total): void
    {
        $expected = (int) round((float) str_replace(['$', ','], '', $total) * 100);
        Assert::same($this->order()->getTotal(), $expected);
    }

    private function order(): OrderInterface
    {
        $order = $this->sharedStorage->has('order')
            ? $this->sharedStorage->get('order')
            : $this->sharedStorage->get('cart');
        Assert::isInstanceOf($order, OrderInterface::class);

        return $order;
    }
}
