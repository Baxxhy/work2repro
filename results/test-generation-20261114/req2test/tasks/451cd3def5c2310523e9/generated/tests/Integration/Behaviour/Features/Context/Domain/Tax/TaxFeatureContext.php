<?php
/**
 * For the full copyright and license information, please view the
 * docs/licenses/LICENSE.txt file that was distributed with this source code.
 */

namespace Tests\Integration\Behaviour\Features\Context\Domain\Tax;

use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use Configuration;
use PrestaShop\PrestaShop\Core\Domain\Tax\Command\AddTaxCommand;
use PrestaShop\PrestaShop\Core\Domain\Tax\Command\BulkToggleTaxStatusCommand;
use PrestaShop\PrestaShop\Core\Domain\Tax\Query\GetTaxForEditing;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

class TaxFeatureContext extends AbstractDomainFeatureContext implements Context
{
    /**
     * @When /^I add new tax "([^"]*)" with following properties:$/
     */
    public function addNewTax(string $reference, TableNode $table): void
    {
        $properties = $table->getRowsHash();
        $localizedNames = [(int) Configuration::get('PS_LANG_DEFAULT') => $properties['name']];
        $enabled = filter_var($properties['is_enabled'], FILTER_VALIDATE_BOOLEAN);

        $taxId = $this->getCommandBus()->handle(new AddTaxCommand(
            $localizedNames,
            (float) $properties['rate'],
            $enabled
        ));

        if (is_object($taxId) && method_exists($taxId, 'getValue')) {
            $taxId = $taxId->getValue();
        }
        $this->getSharedStorage()->set($reference, (int) $taxId);
    }

    /**
     * @When /^I disable taxes: "([^"]*)"$/
     */
    public function disableTaxes(string $references): void
    {
        $this->getCommandBus()->handle(new BulkToggleTaxStatusCommand(
            $this->referencesToIds($references),
            true
        ));
    }

    /**
     * @Then /^taxes: "([^"]*)" should be disabled$/
     */
    public function taxesShouldBeDisabled(string $references): void
    {
        foreach ($this->referencesToIds($references) as $taxId) {
            $tax = $this->getQueryBus()->handle(new GetTaxForEditing($taxId));
            \PHPUnit\Framework\Assert::assertFalse(
                $tax->isActive(),
                sprintf('Tax %d should be disabled', $taxId)
            );
        }
    }
}
