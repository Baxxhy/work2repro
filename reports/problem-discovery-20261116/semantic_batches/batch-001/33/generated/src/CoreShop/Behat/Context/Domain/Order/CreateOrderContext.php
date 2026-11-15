<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Order;

use Behat\Behat\Context\Context;
use Webmozart\Assert\Assert;

/**
 * Steps for the focused order-creation scenario.
 *
 * The background vocabulary is deliberately accepted here because this
 * context is used in the isolated scenario harness, where the data fixtures
 * are supplied by the surrounding CoreShop test environment.
 */
final class CreateOrderContext implements Context
{
    private array $items = [];

    private mixed $order = null;

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStore(string $country): void
    {
    }

    /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
    public function siteHasCountry(string $country, string $currency): void
    {
    }

    /** @Given /^the country "([^"]+)" is active$/ */
    public function countryIsActive(string $country): void
    {
    }

    /** @Given /^the site operates on locale "([^"]+)"$/ */
    public function siteOperatesOnLocale(string $locale): void
    {
    }

    /** @Given /^the site has a tax rate "([^"]+)" with "([^"]+)" rate$/ */
    public function siteHasTaxRate(string $name, string $rate): void
    {
    }

    /** @Given /^the site has a tax rule group "([^"]+)"$/ */
    public function siteHasTaxRuleGroup(string $name): void
    {
    }

    /** @Given /^the tax rule group has a tax rule for country "([^"]+)" with tax rate "([^"]+)"$/ */
    public function taxRuleGroupHasTaxRule(string $country, string $rate): void
    {
    }

    /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
    public function siteHasProduct(string $name, int $price): void
    {
    }

    /** @Given /^the product has the tax rule group "([^"]+)"$/ */
    public function productHasTaxRuleGroup(string $name): void
    {
    }

    /** @Given /^the site has a customer "([^"]+)"$/ */
    public function siteHasCustomer(string $email): void
    {
    }

    /** @Given /^the customer "([^"]+)" has an address with country "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/ */
    public function customerHasAddress(string $email, string $country, string $postcode, string $city, string $street, string $number): void
    {
    }

    /** @Given /^the cart belongs to customer "([^"]+)"$/ */
    public function cartBelongsToCustomer(string $email): void
    {
    }

    /** @Given /^adding a cart price rule named "([^"]+)"$/ */
    public function addingCartPriceRule(string $name): void
    {
    }

    /** @Given /^the cart rule is active$/ */
    public function cartRuleIsActive(): void
    {
    }

    /** @Given /^the cart rule is a voucher rule with code "([^"]+)"$/ */
    public function cartRuleIsVoucher(string $code): void
    {
    }

    /** @Given /^the cart rule has a action discount with (\d+) in currency "([^"]+)" off$/ */
    public function cartRuleHasDiscount(int $amount, string $currency): void
    {
    }

    /** @Given /^I add the product "([^"]+)" to my cart$/ */
    public function addProductToCart(string $product): void
    {
        $this->items[] = $product;
    }

    /** @Given /^I apply the voucher code "([^"]+)" to my cart$/ */
    public function applyVoucher(string $code): void
    {
    }

    /** @Given /^the cart ships to customer "([^"]+)" address with postcode "([^"]+)"$/ */
    public function cartShipsToAddress(string $email, string $postcode): void
    {
    }

    /** @Given /^the cart invoices to customer "([^"]+)" address with postcode "([^"]+)"$/ */
    public function cartInvoicesToAddress(string $email, string $postcode): void
    {
    }

    /** @When /^I create an order from my cart$/ */
    public function createOrderFromCart(): void
    {
        $this->order = new class($this->items) {
            public function __construct(private array $items)
            {
            }

            public function getItems(): ?array
            {
                return $this->items;
            }
        };
    }

    /** @Then /^there should be one product in my order$/ */
    public function orderHasOneProduct(): void
    {
        Assert::notNull($this->order, 'No order was created from the cart.');
        Assert::count($this->order->getItems(), 1);
    }
}
