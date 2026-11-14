<?php

namespace Tests\Integration\Behaviour\Features\Context\Domain\Currency;

use Behat\Gherkin\Node\TableNode;
use Language;
use PrestaShop\PrestaShop\Core\Domain\Currency\Query\GetReferenceCurrency;
use Shop;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;
use Tests\Integration\Behaviour\Features\Context\Util\DataComparator;

class CurrencyDataFeatureContext extends AbstractDomainFeatureContext
{
    private const CURRENCY_STORAGE_KEY = 'currency_reference_data';

    /**
     * @Given /^shop "([^"]+)" with name "([^"]+)" exists$/
     */
    public function shopExists(string $reference, string $name): void
    {
        $shopId = Shop::getIdByName($name);
        if (!$shopId) {
            $shopId = $this->getDefaultShopId();
        }
        $this->getSharedStorage()->set($reference, (int) $shopId);
    }

    /**
     * @Given /^language "([^"]+)" with locale "([^"]+)" exists$/
     */
    public function languageExists(string $reference, string $locale): void
    {
        $languageId = (int) Language::getIdByLocale($locale, true);
        if (!$languageId) {
            throw new \RuntimeException(sprintf('Language with locale "%s" does not exist', $locale));
        }
        $this->getSharedStorage()->set($reference, $languageId);
    }

    /**
     * @When /^I request reference data for "([^"]+)"$/
     */
    public function requestReferenceCurrency(string $isoCode): void
    {
        $result = $this->getQueryBus()->handle(new GetReferenceCurrency($isoCode));
        $this->getSharedStorage()->set(self::CURRENCY_STORAGE_KEY, $result);
    }

    /**
     * @Then /^I should get currency data:$/
     */
    public function assertCurrencyData(TableNode $table): void
    {
        $currency = $this->getSharedStorage()->get(self::CURRENCY_STORAGE_KEY);
        $expected = $this->localizeByRows($table);
        $actual = [
            'iso_code' => $currency->getIsoCode(),
            'numeric_iso_code' => $currency->getNumericIsoCode(),
            'precision' => $currency->getPrecision(),
            'names' => $currency->getNames(),
            'symbols' => $currency->getSymbols(),
            'patterns' => $currency->getPatterns(),
        ];

        DataComparator::assertDataSetsAreIdentical($expected, $actual);
    }
}
