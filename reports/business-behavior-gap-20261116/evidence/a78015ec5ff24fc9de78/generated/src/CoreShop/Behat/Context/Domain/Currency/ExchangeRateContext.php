<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Currency;

use Behat\Behat\Context\Context;
use CoreShop\Component\Currency\Converter\CurrencyConverter;
use CoreShop\Component\Currency\Model\CurrencyInterface;
use CoreShop\Component\Currency\Repository\CurrencyRepositoryInterface;
use CoreShop\Component\Currency\Repository\ExchangeRateRepositoryInterface;
use CoreShop\Component\Resource\Factory\FactoryInterface;
use CoreShop\Component\Store\Repository\StoreRepositoryInterface;
use CoreShop\Component\Address\Repository\CountryRepositoryInterface;
use Webmozart\Assert\Assert;

final class ExchangeRateContext implements Context
{
    private ?CurrencyInterface $usd = null;
    private ?CurrencyInterface $eur = null;

    public function __construct(
        private FactoryInterface $currencyFactory,
        private FactoryInterface $exchangeRateFactory,
        private FactoryInterface $countryFactory,
        private FactoryInterface $storeFactory,
        private CurrencyRepositoryInterface $currencyRepository,
        private ExchangeRateRepositoryInterface $exchangeRateRepository,
        private CountryRepositoryInterface $countryRepository,
        private StoreRepositoryInterface $storeRepository,
        private CurrencyConverter $converter,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]*)"$/ */
    public function siteOperatesOnStoreIn(string $countryName): void
    {
        $country = $this->country($countryName, $countryName === 'Austria' ? 'AT' : $countryName);
        $store = $this->storeFactory->createNew();
        $store->setName($countryName);
        $store->setIsDefault(true);
        $store->addCountry($country);
        $this->storeRepository->add($store);
    }

    /** @Given /^the site has a currency "([^"]*)" with iso "([^"]*)"$/ */
    public function siteHasCurrency(string $code, string $iso): void
    {
        $existing = $this->currencyRepository->getByCode($code);
        if ($existing !== null) {
            $this->usd = $existing;
            return;
        }

        $currency = $this->currencyFactory->createNew();
        $currency->setName($code);
        $currency->setIsoCode($iso);
        $currency->setNumericIsoCode(0);
        $currency->setSymbol($code);
        $this->currencyRepository->add($currency);
        if ($code === 'USD') {
            $this->usd = $currency;
        }
    }

    /** @Given /^the site has a country "([^"]*)" with currency "([^"]*)"$/ */
    public function siteHasCountry(string $name, string $currencyCode): void
    {
        $currency = $this->currencyRepository->getByCode($currencyCode);
        Assert::notNull($currency, sprintf('Currency %s must exist first', $currencyCode));
        $this->country($name, $name === 'USA' ? 'US' : $name)->setCurrency($currency);
    }

    /** @Given /^the currency has a exchange-rate to currency "([^"]*)" of "([^"]*)"$/ */
    public function currencyHasExchangeRate(string $toCode, string $rate): void
    {
        $this->usd ??= $this->currencyRepository->getByCode('USD');
        $this->eur = $this->currencyRepository->getByCode($toCode);
        Assert::notNull($this->usd, 'USD currency must exist');
        if ($this->eur === null) {
            $this->siteHasCurrency($toCode, $toCode);
            $this->eur = $this->currencyRepository->getByCode($toCode);
        }
        Assert::notNull($this->eur, sprintf('%s currency must exist', $toCode));

        $exchangeRate = $this->exchangeRateFactory->createNew();
        $exchangeRate->setFromCurrency($this->usd);
        $exchangeRate->setToCurrency($this->eur);
        $exchangeRate->setExchangeRate((float) $rate);
        $this->exchangeRateRepository->add($exchangeRate);
    }

    /** @Then /^price "([^"]*)" of currency "([^"]*)" should exchange to price "([^"]*)" in currency "([^"]*)"$/ */
    public function priceShouldExchange(string $amount, string $from, string $expected, string $to): void
    {
        Assert::same((int) $expected, $this->converter->convert((int) $amount, $from, $to));
    }

    private function country(string $name, string $iso): \CoreShop\Component\Core\Model\CountryInterface
    {
        $country = $this->countryFactory->createNew();
        $country->setName($name, 'en');
        $country->setIsoCode($iso);
        $this->countryRepository->add($country);

        return $country;
    }

}
