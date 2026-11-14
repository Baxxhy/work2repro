<?php

namespace Tests\Integration\Behaviour\Features\Context\Domain\Discount;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use DateTimeImmutable;
use PHPUnit\Framework\Assert;
use PrestaShop\Decimal\DecimalNumber;
use PrestaShop\PrestaShop\Core\Domain\Cart\Command\AddCartRuleToCartCommand;
use PrestaShop\PrestaShop\Core\Domain\Cart\Command\AddProductToCartCommand;
use PrestaShop\PrestaShop\Core\Domain\Cart\Query\GetCartForOrderCreation;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\AddDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\Query\GetDiscountForEditing;
use PrestaShop\PrestaShop\Core\Domain\Discount\ValueObject\DiscountId;
use PrestaShop\PrestaShop\Core\Domain\Product\Query\SearchProducts;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/**
 * Glue for the free-shipping/minimum-order acceptance scenario.
 *
 * @see \Tests\Integration\Behaviour\Features\Scenario\Discount\FO\discount_with_code.feature
 */
class DiscountFeatureContext extends AbstractDomainFeatureContext implements Context
{
    /** @When I create a :type discount :reference with following properties: */
    public function createDiscount(string $type, string $reference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $names = [];
        foreach ($data as $key => $value) {
            if (preg_match('/^name\[([^\]]+)\]$/', $key, $match)) {
                $names[(int) \Language::getIdByLocale($match[1], true)] = $value;
            }
        }
        $currencyId = (int) \Currency::getIdByIsoCode('USD');
        $command = (new AddDiscountCommand($type, $names))
            ->setActive(filter_var($data['active'], FILTER_VALIDATE_BOOLEAN))
            ->setCode($data['code'])
            ->setValidityDateRange(new DateTimeImmutable($data['valid_from']), new DateTimeImmutable($data['valid_to']))
            ->setMinimumAmount(new DecimalNumber($data['minimum_amount']), $currencyId,
                filter_var($data['minimum_amount_tax_included'], FILTER_VALIDATE_BOOLEAN),
                filter_var($data['minimum_amount_shipping_included'], FILTER_VALIDATE_BOOLEAN));
        $id = $this->getCommandBus()->handle($command);
        $this->getSharedStorage()->set($reference, $id instanceof DiscountId ? $id->getValue() : (int) $id);
    }

    /** @Then discount :reference should have the following properties: */
    public function assertDiscount(string $reference, TableNode $table): void
    {
        $discount = $this->getQueryBus()->handle(new GetDiscountForEditing($this->referenceToId($reference)));
        $data = $table->getRowsHash();
        foreach ($data as $key => $expected) {
            if (preg_match('/^name\[([^\]]+)\]$/', $key, $match)) {
                $langId = (int) \Language::getIdByLocale($match[1], true);
                Assert::assertSame($expected, $discount->getLocalizedNames()[$langId]);
            } elseif ($key === 'active') {
                Assert::assertSame(filter_var($expected, FILTER_VALIDATE_BOOLEAN), $discount->isActive());
            } elseif ($key === 'code') {
                Assert::assertSame($expected, $discount->getCode());
            } elseif ($key === 'valid_from' || $key === 'valid_to') {
                $date = $key === 'valid_from' ? $discount->getValidFrom() : $discount->getValidTo();
                Assert::assertSame((new DateTimeImmutable($expected))->format('Y-m-d H:i:s'), $date->format('Y-m-d H:i:s'));
            } elseif ($key === 'minimum_amount_shipping_included') {
                Assert::assertSame(filter_var($expected, FILTER_VALIDATE_BOOLEAN), $discount->getMinimumAmount()->isShippingIncluded());
            } elseif ($key === 'minimum_amount') {
                Assert::assertSame($expected, (string) $discount->getMinimumAmount()->getAmount());
            }
        }
    }

    /** @When I add :quantity product :product to the cart :cart */
    public function addProduct(int $quantity, string $product, string $cart): void
    {
        $results = $this->getQueryBus()->handle(new SearchProducts($product, 10, 'en'));
        $this->getCommandBus()->handle(new AddProductToCartCommand(
            $this->referenceToId($cart), $results[0]->getProductId(), $quantity
        ));
    }

    /** @When I use a voucher :discount on the cart :cart */
    public function useVoucher(string $discount, string $cart): void
    {
        try {
            $this->getCommandBus()->handle(new AddCartRuleToCartCommand(
                $this->referenceToId($cart), $this->referenceToId($discount)
            ));
        } catch (\Throwable $e) {
            $this->setLastException($e);
        }
    }

    /** @Then I should get cart rule validation error */
    public function assertCartRuleError(): void
    {
        Assert::assertTrue($this->getSharedStorage()->exists(\Tests\Integration\Behaviour\Features\Context\CommonFeatureContext::LAST_EXCEPTION_STORAGE_KEY));
    }

    /** @Then cart :cart total with tax included should be :expected */
    public function assertCartTotal(string $cart, string $expected): void
    {
        Assert::assertSame($this->money($expected), $this->cartSummary($cart)->getTotalPriceWithTaxes());
    }

    /** @Then my cart :cart should have the following details: */
    public function assertCartDetails(string $cart, TableNode $table): void
    {
        $summary = $this->cartSummary($cart);
        $actual = [
            'total_products' => $summary->getTotalProductsPrice(),
            'shipping' => $summary->getTotalShippingPrice(),
            'total_discount' => $summary->getTotalDiscount(),
            'total' => $summary->getTotalPriceWithTaxes(),
        ];
        foreach ($table->getRowsHash() as $key => $value) {
            Assert::assertSame($this->money($value), $actual[$key]);
        }
    }

    private function cartSummary(string $reference)
    {
        return $this->getQueryBus()->handle(new GetCartForOrderCreation($this->referenceToId($reference)))->getSummary();
    }

    private function money(string $value): string
    {
        return number_format((float) str_replace(['$', ','], '', $value), 2, '.', '');
    }
}
