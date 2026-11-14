<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\Then;
use Behat\Step\When;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\ProductInterface;
use Webmozart\Assert\Assert;

final class ManagingCatalogPromotionsContext implements Context
{
    private ?string $code = null;
    private ?string $name = null;
    private ?ProductInterface $product = null;
    private array $actions = [];

    public function __construct(
        private readonly ApiClientInterface $adminClient,
        private readonly SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I want to create a new catalog promotion')]
    public function wantToCreateCatalogPromotion(): void
    {
        $this->code = null;
        $this->name = null;
        $this->product = null;
        $this->actions = [];
    }

    #[When('I specify its code as :code')]
    public function specifyCode(string $code): void
    {
        $this->code = $code;
    }

    #[When('I name it :name')]
    public function nameIt(string $name): void
    {
        $this->name = $name;
    }

    #[When('/^I add scope that applies on ("[^"]+" product)$/')]
    public function addProductScope(ProductInterface $product): void
    {
        $this->product = $product;
    }

    #[When('/^I add action that gives "([^"]+)" percentage discount$/')]
    public function addPercentageDiscount(string $percentage): void
    {
        $this->actions[] = [
            'type' => 'percentage_discount',
            'configuration' => ['amount' => (float) rtrim($percentage, '%')],
        ];
    }

    #[When('I add it')]
    public function addIt(): void
    {
        Assert::notNull($this->code);
        Assert::notNull($this->name);
        Assert::notNull($this->product);

        $payload = [
            'code' => $this->code,
            'name' => $this->name,
            'scopes' => [[
                'type' => 'for_products',
                'configuration' => ['products' => [$this->product->getCode()]],
            ]],
            'actions' => $this->actions,
        ];

        $this->adminClient->buildCreateRequest('catalog-promotions')->setRequestData($payload);
        $response = $this->adminClient->create();
        Assert::eq($response->getStatusCode(), 201);
        $this->sharedStorage->set('created_catalog_promotion', json_decode($response->getContent(), true));
    }

    #[Then('there should be :count new catalog promotion on the list')]
    public function thereShouldBeCatalogPromotionOnTheList(int $count): void
    {
        $response = $this->adminClient->index('catalog-promotions');
        $content = json_decode($response->getContent(), true);
        Assert::eq(count($content['hydra:member'] ?? $content['member'] ?? []), $count);
    }

    #[Then('/^it should have "([^"]+)" code and "([^"]+)" name$/')]
    public function itShouldHaveCodeAndName(string $code, string $name): void
    {
        $created = $this->sharedStorage->get('created_catalog_promotion');
        Assert::eq($created['code'] ?? null, $code);
        Assert::eq($created['name'] ?? null, $name);
    }

    #[Then('/^the "([^"]+)" catalog promotion should apply to all variants of ("[^"]+" product)$/')]
    public function promotionShouldApplyToProduct(string $name, ProductInterface $product): void
    {
        $created = $this->sharedStorage->get('created_catalog_promotion');
        Assert::eq($created['name'] ?? null, $name);
        $scopes = $created['scopes'] ?? [];
        Assert::true((bool) array_filter($scopes, static fn (array $scope): bool =>
            ($scope['type'] ?? null) === 'for_product'
            && in_array($product->getCode(), $scope['configuration']['products'] ?? [], true)
        ));
    }
}
