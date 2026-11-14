<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Shipping;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Context\CompositeCartContext;
use Webmozart\Assert\Assert;

/**
 * Steps for the default-carrier regression scenario.
 *
 * @see \CoreShop\Component\Shipping\Model\CarrierAwareTrait::getCarrier()
 */
final class DefaultCarrierContext implements Context
{
    public function __construct(private CompositeCartContext $cartContext)
    {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStore(string $country): void
    {
    }

    /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
    public function siteHasCurrency(string $name, string $iso): void
    {
    }

    /** @Given /^I am in country "([^"]+)"$/ */
    public function iAmInCountry(string $country): void
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
    public function taxRuleGroupHasRule(string $country, string $rate): void
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

    /** @Given /^the site has a carrier "([^"]+)"$/ */
    public function siteHasCarrier(string $name): void
    {
    }

    /** @Given /^adding a shipping rule named "([^"]+)"$/ */
    public function addingShippingRule(string $name): void
    {
    }

    /** @Given /^the shipping rule is active$/ */
    public function shippingRuleIsActive(): void
    {
    }

    /** @Given /^the shipping rule has a action price of (\d+) in currency "([^"]+)"$/ */
    public function shippingRuleHasActionPrice(int $price, string $currency): void
    {
    }

    /** @Given /^the shipping rule belongs to carrier "([^"]+)"$/ */
    public function shippingRuleBelongsToCarrier(string $carrier): void
    {
    }

    /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
    public function siteHasCountry(string $country, string $currency): void
    {
    }

    /** @Given /^the shipping rule has a condition countries with country "([^"]+)"$/ */
    public function shippingRuleHasCountryCondition(string $country): void
    {
    }

    /** @When /^I add the product "([^"]+)" to my cart$/ */
    public function addProductToCart(string $product): void
    {
    }

    /** @Then /^the cart should not have a carrier$/ */
    public function cartShouldNotHaveCarrier(): void
    {
        Assert::null($this->cartContext->getCart()->getCarrier());
    }
}
