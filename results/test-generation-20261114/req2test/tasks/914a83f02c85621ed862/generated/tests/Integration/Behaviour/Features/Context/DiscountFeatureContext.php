<?php

namespace Tests\Integration\Behaviour\Features\Context;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use DateTimeImmutable;
use Language;
use PrestaShop\Decimal\DecimalNumber;
use PrestaShop\PrestaShop\Core\Domain\Discount\Command\AddDiscountCommand;
use PrestaShop\PrestaShop\Core\Domain\Discount\Query\GetDiscountForEditing;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

class DiscountFeatureContext extends AbstractDomainFeatureContext implements Context
{
    /**
     * @When /^I create a "([^"]+)" discount "([^"]+)" with following properties:$/
     */
    public function createDiscount(string $type, string $reference, TableNode $table): void
    {
        $values = $table->getRowsHash();
        $localizedNames = [];
        foreach ($values as $key => $value) {
            if (preg_match('/^name\[([^\]]+)\]$/', $key, $matches)) {
                $languageId = (int) Language::getIdByLocale($matches[1], true);
                if (!$languageId) {
                    throw new \RuntimeException(sprintf('Language locale %s was not found', $matches[1]));
                }
                $localizedNames[$languageId] = $value;
            }
        }

        $command = new AddDiscountCommand($type, $localizedNames);
        if (isset($values['active'])) {
            $command->setActive(filter_var($values['active'], FILTER_VALIDATE_BOOLEAN));
        }
        if (isset($values['valid_from'])) {
            $command->setValidityDateRange(
                new DateTimeImmutable($values['valid_from']),
                isset($values['valid_to']) ? new DateTimeImmutable($values['valid_to']) : null
            );
        }
        if (isset($values['reduction_percent'])) {
            $command->setReductionPercent(new DecimalNumber($values['reduction_percent']));
        }

        $discountId = $this->getCommandBus()->handle($command);
        if (is_object($discountId) && method_exists($discountId, 'getValue')) {
            $discountId = $discountId->getValue();
        }
        $this->getSharedStorage()->set($reference, (int) $discountId);
    }

    /**
     * @Then /^discount "([^"]+)" should have the following properties:$/
     */
    public function discountHasProperties(string $reference, TableNode $table): void
    {
        $discount = $this->getQueryBus()->handle(new GetDiscountForEditing($this->referenceToId($reference)));
        $names = $discount->getLocalizedNames();
        foreach ($table->getRowsHash() as $key => $expected) {
            if (!preg_match('/^name\[([^\]]+)\]$/', $key, $matches)) {
                continue;
            }
            $languageId = (int) Language::getIdByLocale($matches[1], true);
            if (!isset($names[$languageId]) || $names[$languageId] !== $expected) {
                throw new \RuntimeException(sprintf('Discount name for %s did not match "%s"', $matches[1], $expected));
            }
        }
    }
}
