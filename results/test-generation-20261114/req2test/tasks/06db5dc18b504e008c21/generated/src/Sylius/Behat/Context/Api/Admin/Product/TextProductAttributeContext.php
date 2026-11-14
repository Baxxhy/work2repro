<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin\Product;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Product\Model\ProductAttributeInterface;
use Sylius\Component\Product\Model\ProductAttributeValueInterface;
use Sylius\Resource\Doctrine\Persistence\RepositoryInterface;
use Webmozart\Assert\Assert;

final class TextProductAttributeContext implements Context
{
    private array $data = [];
    private array $attributes = [];
    private ?string $code = null;

    public function __construct(
        private ApiClientInterface $adminClient,
        private ApiClientInterface $shopClient,
        private SharedStorageInterface $sharedStorage,
        private RepositoryInterface $productAttributeTranslationRepository,
        private RepositoryInterface $productAttributeValueRepository,
    ) {
    }

    #[When('I want to create a new configurable product')]
    public function startCreating(): void
    {
        $this->data = ['enabled' => true, 'translations' => [], 'attributes' => []];
        $this->attributes = [];
        $this->code = null;
    }

    #[When('I specify its code as :code')]
    public function specifyCode(string $code): void
    {
        $this->code = $code;
        $this->data['code'] = $code;
    }

    #[When('/^I name it "([^"]+)" in "([^"]+)" locale$/')]
    public function nameIt(string $name, string $locale): void
    {
        $this->data['translations']['en_US'] = ['name' => $name, 'slug' => $this->data['translations']['en_US']['slug'] ?? ''];
    }

    #[When('I set its slug to :slug')]
    public function setSlug(string $slug): void
    {
        $this->data['translations']['en_US']['slug'] = $slug;
    }

    #[When('I add the :name attribute')]
    public function addAttribute(string $name): void
    {
        $this->attributes[$name] = ['attribute' => $this->attribute($name), 'value' => null, 'locale' => 'en_US'];
    }

    #[When('/^I set the "([^"]+)" attribute value to "([^"]+)" in "([^"]+)" locale$/')]
    public function setAttributeValue(string $name, string $value, string $locale): void
    {
        $this->attributes[$name]['value'] = $value;
    }

    #[When('I remove its :name attribute')]
    public function removeAttribute(string $name): void
    {
        unset($this->attributes[$name]);
    }

    #[When('I add it')]
    public function createProduct(): void
    {
        foreach ($this->attributes as $entry) {
            $this->data['attributes'][] = [
                'attribute' => '/api/v2/admin/product-attributes/' . $entry['attribute']->getCode(),
                'value' => $entry['value'],
                'localeCode' => $entry['locale'],
            ];
        }
        $this->adminClient->buildCreateRequest('/api/v2/admin/products')->setRequestData($this->data)->create();
        Assert::true($this->adminClient->getLastResponse()->isSuccessful(), (string) $this->adminClient->getLastResponse()->getContent());
        $this->sharedStorage->set('created_product_code', $this->code);
    }

    #[Then('I should be notified that it has been successfully created')]
    public function creationSucceeded(): void
    {
        Assert::true($this->adminClient->getLastResponse()->isSuccessful());
    }

    #[Then('/^the product "([^"]+)" should appear in the store$/')]
    public function productAppears(string $name): void
    {
        $response = $this->shopClient->requestGet('/api/v2/shop/products/' . $this->code);
        Assert::true($response->isSuccessful());
    }

    #[Then('/^attribute "([^"]+)" of product "([^"]+)" should be "([^"]+)"$/')]
    public function attributeValueIs(string $name, string $product, string $expected): void
    {
        $attribute = $this->attribute($name);
        $values = $this->productAttributeValueRepository->findBy(['subject' => $this->code]);
        foreach ($values as $value) {
            if ($value instanceof ProductAttributeValueInterface && $value->getAttribute()->getCode() === $attribute->getCode()) {
                Assert::eq($value->getValue(), $expected);
                return;
            }
        }
        Assert::fail(sprintf('Attribute "%s" was not saved', $name));
    }

    #[Then('/^product "([^"]+)" should not have a "([^"]+)" attribute$/')]
    public function productDoesNotHaveAttribute(string $product, string $name): void
    {
        $attribute = $this->attribute($name);
        $values = $this->productAttributeValueRepository->findBy(['subject' => $this->code]);
        foreach ($values as $value) {
            Assert::notEq($value->getAttribute()->getCode(), $attribute->getCode());
        }
    }

    private function attribute(string $name): ProductAttributeInterface
    {
        $translations = $this->productAttributeTranslationRepository->findBy(['name' => $name]);
        Assert::notEmpty($translations);
        return $translations[0]->getTranslatable();
    }
}
