<?php

namespace Tests\Integration\Behaviour\Features\Context\Order;

use Address;
use Behat\Behat\Context\Context;
use Behat\Gherkin\Node\TableNode;
use Country;
use Customer;
use PrestaShop\PrestaShop\Core\Domain\Address\Command\AddCustomerAddressCommand;
use PrestaShop\PrestaShop\Core\Domain\Order\Command\ChangeOrderDeliveryAddressCommand;
use PrestaShop\PrestaShop\Core\Domain\Order\Query\GetOrderForViewing;
use PrestaShop\PrestaShop\Core\Domain\State\ValueObject\NoStateId;
use PrestaShop\PrestaShop\Core\Domain\State\ValueObject\StateId;
use Tests\Integration\Behaviour\Features\Context\Domain\AbstractDomainFeatureContext;

/**
 * Glue for changing an order's delivery address.
 *
 * @todo The original order suite also supplies the common order/customer fixtures in its
 * background. This context deliberately uses the domain commands for the operations under test.
 */
class ChangeOrderShippingAddressContext extends AbstractDomainFeatureContext implements Context
{
    /** @Given I create customer :reference with following details: */
    public function createCustomer(string $reference, TableNode $table): void
    {
        $data = $table->getRowsHash();
        $customer = new Customer();
        $customer->firstname = $data['firstName'];
        $customer->lastname = $data['lastName'];
        $customer->email = $data['email'];
        $customer->passwd = password_hash($data['password'], PASSWORD_BCRYPT);
        $customer->id_default_group = (int) \Configuration::get('PS_CUSTOMER_GROUP');
        $customer->id_lang = (int) \Configuration::get('PS_LANG_DEFAULT');
        $customer->active = true;
        if (!$customer->add()) {
            throw new \RuntimeException('Could not create customer ' . $data['email']);
        }
        $this->getSharedStorage()->set($reference, (int) $customer->id);
    }

    /** @When I add new address to customer :customerReference with following details: */
    public function addCustomerAddress(string $customerReference, TableNode $table): void
    {
        $row = $table->getRowsHash();
        $country = new Country((int) Country::getByIso('US'));
        $stateId = (int) \Db::getInstance()->getValue(
            'SELECT id_state FROM `' . _DB_PREFIX_ . 'state` WHERE name = "' . pSQL($row['State']) . '" AND id_country = ' . (int) $country->id
        );
        if (!$stateId) {
            throw new \RuntimeException('State not found: ' . $row['State']);
        }
        $addressId = $this->getCommandBus()->handle(new AddCustomerAddressCommand(
            $this->referenceToId($customerReference),
            $row['Address alias'],
            $row['First name'],
            $row['Last name'],
            $row['Address'],
            $row['City'],
            (int) $country->id,
            $row['Postal code'],
            null,
            null,
            null,
            null,
            $stateId
        ));
        $this->getSharedStorage()->set($row['Address alias'], $addressId->getValue());
    }

    /** @When I change order :orderReference shipping address to :addressReference */
    public function changeShippingAddress(string $orderReference, string $addressReference): void
    {
        $this->getCommandBus()->handle(new ChangeOrderDeliveryAddressCommand(
            $this->referenceToId($orderReference),
            $this->referenceToId($addressReference)
        ));
    }

    /** @Then order :orderReference shipping address should be :addressReference */
    public function assertShippingAddress(string $orderReference, string $addressReference): void
    {
        $order = $this->getQueryBus()->handle(new GetOrderForViewing($this->referenceToId($orderReference)));
        $actual = $order->getShippingAddress()->getAddressId();
        $expected = $this->referenceToId($addressReference);
        if ($actual !== $expected) {
            throw new \RuntimeException(sprintf('Expected shipping address %d, got %d', $expected, $actual));
        }
    }
}
