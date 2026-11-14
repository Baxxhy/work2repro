<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\ResponseCheckerInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Addressing\Model\ZoneInterface;
use Symfony\Component\HttpFoundation\Response;
use Webmozart\Assert\Assert;

final class EditingZoneContext implements Context
{
    private ?ZoneInterface $zone = null;
    private ?string $memberCode = null;
    private ?Response $response = null;

    public function __construct(
        private readonly ApiClientInterface $client,
        private readonly ResponseCheckerInterface $checker,
        private readonly SharedStorageInterface $storage,
    ) {
    }

    #[When('I want to modify the zone named :name')]
    public function modifyZone(string $name): void
    {
        $this->zone = $this->storage->get('zone');
        Assert::isInstanceOf($this->zone, ZoneInterface::class);
        $this->client->buildUpdateRequest('/admin/zones/' . $this->zone->getCode());
    }

    #[When('I remove the :member country member')]
    public function removeCountryMember(string $member): void
    {
        $this->memberCode = match ($member) {
            'Germany' => 'DE',
            'France' => 'FR',
            default => $member,
        };
        $members = [];
        foreach ($this->zone->getMembers() as $zoneMember) {
            if ($zoneMember->getCode() !== $this->memberCode) {
                $members[] = '/api/v2/admin/countries/' . $zoneMember->getCode();
            }
        }
        $this->client->setRequestData(['members' => $members]);
    }

    #[When('I save my changes')]
    public function saveChanges(): void
    {
        $this->response = $this->client->update();
    }

    #[Then('I should be notified that it has been successfully edited')]
    public function shouldBeSuccessfullyEdited(): void
    {
        Assert::true($this->checker->isUpdateSuccessful($this->response));
    }

    #[Then('this zone should have only the :member country member')]
    public function zoneShouldHaveOnlyCountry(string $member): void
    {
        Assert::same([$member === 'France' ? 'FR' : $member], array_map(
            static fn ($zoneMember) => $zoneMember->getCode(),
            $this->zone->getMembers()->toArray(),
        ));
    }
}
