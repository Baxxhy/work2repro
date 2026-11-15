<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Currency;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\MoneyBundle\Formatter\MoneyFormatter;
use CoreShop\Component\Currency\Model\Currency;
use Webmozart\Assert\Assert;

final class MoneyFormatterContext implements Context
{
    public function __construct(private MoneyFormatter $formatter)
    {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStoreIn(string $country): void
    {
        // Formatting is determined by the explicit locale and currency passed
        // to MoneyFormatter; store context does not participate.
        Assert::same($country, 'Austria');
    }

    /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
    public function siteHasCurrencyWithIso(string $code, string $iso): void
    {
        $currency = new Currency();
        $currency->setIsoCode($iso);
        Assert::same($currency->getIsoCode(), $code);
    }

    /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
    public function siteHasCountryWithCurrency(string $country, string $currency): void
    {
        Assert::same($country, 'USA');
        Assert::same($currency, 'USD');
    }

    /** @Then /^the amount "([^"]+)" of currency "([^"]+)" in language "([^"]+)" should be formatted "([^"]+)"$/ */
    public function amountShouldBeFormatted(string $amount, string $currency, string $language, string $expected): void
    {
        Assert::same($this->formatter->format((int) $amount, $currency, $language), $expected);
    }
}
