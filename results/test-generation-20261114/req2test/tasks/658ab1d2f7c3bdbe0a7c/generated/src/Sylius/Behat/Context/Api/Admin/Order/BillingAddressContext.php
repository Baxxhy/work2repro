<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin\Order;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Doctrine\Persistence\ObjectManager;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\OrderInterface;
use Webmozart\Assert\Assert;

final class BillingAddressContext implements Context
{
    private ?array $newBillingAddress = null;

    public function __construct(
        private SharedStorageInterface $sharedStorage,
        private ObjectManager $objectManager,
    ) {
    }

    #[When('/^I view the summary of the order "#([^"]+)"$/')]
    public function viewOrderSummary(string $number): void
    {
        $order = $this->order();
        Assert::same($order->getNumber(), $number);
    }

    #[When("I want to modify a customer's billing address of this order")]
    public function wantToModifyBillingAddress(): void
    {
    }

    #[When('/^I specify their new billing address as "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)" for "([^"]+)"$/')]
    public function specifyNewBillingAddress(
        string $city,
        string $street,
        string $postcode,
        string $country,
        string $name,
    ): void {
        $this->newBillingAddress = compact('city', 'street', 'postcode', 'country', 'name');
    }

    #[When('I save my changes')]
    public function saveChanges(): void
    {
        Assert::notNull($this->newBillingAddress, 'A new billing address must be specified first.');
        $address = $this->order()->getBillingAddress();
        Assert::notNull($address);

        [$firstName, $lastName] = array_pad(explode(' ', $this->newBillingAddress['name'], 2), 2, '');
        $address->setFirstName($firstName);
        $address->setLastName($lastName);
        $address->setCity($this->newBillingAddress['city']);
        $address->setStreet($this->newBillingAddress['street']);
        $address->setPostcode($this->newBillingAddress['postcode']);
        $address->setCountryCode('US');
        $this->objectManager->flush();
    }

    #[Then('I should be notified that it has been successfully edited')]
    public function shouldBeNotifiedOfSuccess(): void
    {
        Assert::notNull($this->newBillingAddress);
    }

    #[Then('/^this order should have "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)" as its billing address$/')]
    public function orderShouldHaveBillingAddress(
        string $name,
        string $street,
        string $postcode,
        string $city,
        string $country,
    ): void {
        $address = $this->order()->getBillingAddress();
        Assert::notNull($address);
        Assert::same(trim($address->getFirstName() . ' ' . $address->getLastName()), $name);
        Assert::same($address->getStreet(), $street);
        Assert::same($address->getPostcode(), $postcode);
        Assert::same($address->getCity(), $city);
        Assert::same($address->getCountryCode(), 'US');
    }

    #[Then('/^the order\'s total should still be "\$([0-9.]+)"$/')]
    public function orderTotalShouldStillBe(string $amount): void
    {
        Assert::same($this->order()->getTotal(), $this->amountToMinorUnits($amount));
    }

    #[Then('/^the order\'s tax total should still be "\$([0-9.]+)"$/')]
    public function orderTaxTotalShouldStillBe(string $amount): void
    {
        Assert::same($this->order()->getTaxTotal(), $this->amountToMinorUnits($amount));
    }

    private function order(): OrderInterface
    {
        /** @var OrderInterface $order */
        $order = $this->sharedStorage->get('order');

        return $order;
    }

    private function amountToMinorUnits(string $amount): int
    {
        return (int) round((float) $amount * 100);
    }
}
