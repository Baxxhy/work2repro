<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Taxation;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use CoreShop\Component\Resource\Factory\FactoryInterface;
use CoreShop\Component\Taxation\Model\TaxRateInterface;
use CoreShop\Component\Taxation\Repository\TaxRateRepositoryInterface;
use Webmozart\Assert\Assert;

final class AddingTaxContext implements Context
{
    public function __construct(
        private TaxRateRepositoryInterface $taxRateRepository,
        private FactoryInterface $taxRateFactory,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    /**
     * @Given /^the site has a tax rate "([^"]+)" with "([^"]+)" rate$/
     */
    public function theSiteHasATaxRateWithRate(string $name, string $rate): void
    {
        /** @var TaxRateInterface $taxRate */
        $taxRate = $this->taxRateFactory->createNew();
        $taxRate->setName($name, 'en');
        $taxRate->setRate((float) rtrim($rate, '%'));
        $this->taxRateRepository->add($taxRate);
        $this->sharedStorage->set('tax_rate', $taxRate);
    }

    /**
     * @Given /^the tax rate "([^"]+)" is active$/
     */
    public function theTaxRateIsActive(string $name): void
    {
        $taxRate = $this->sharedStorage->get('tax_rate');
        Assert::notNull($taxRate);
        Assert::same($name, $taxRate->getName('en'));

        $taxRate->setActive(true);
        $this->taxRateRepository->add($taxRate);
    }

    /**
     * @Then /^there should be a tax rate "([^"]+)" with "([^"]+)" rate$/
     */
    public function thereShouldBeATaxRateWithRate(string $name, string $rate): void
    {
        $taxRates = $this->taxRateRepository->findByName($name, 'en');
        Assert::count($taxRates, 1);
        Assert::same((float) rtrim($rate, '%'), (float) $taxRates[0]->getRate());
    }
}
