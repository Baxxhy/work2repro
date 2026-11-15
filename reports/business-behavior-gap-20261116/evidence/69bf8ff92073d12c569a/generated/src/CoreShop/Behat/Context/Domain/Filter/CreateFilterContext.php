<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Filter;

use Behat\Behat\Context\Context;
use CoreShop\Component\Index\Model\Filter;
use CoreShop\Component\Index\Model\Index;
use CoreShop\Component\Resource\Repository\RepositoryInterface;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use Webmozart\Assert\Assert;

final class CreateFilterContext implements Context
{
    public function __construct(
        private RepositoryInterface $indexRepository,
        private RepositoryInterface $filterRepository,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function siteOperatesOnStore(string $country): void
    {
        // Index/filter creation in this scenario is independent of store setup.
    }

    /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
    public function siteHasProduct(string $name, int $price): void
    {
        // No product is consumed by this scenario's index/filter operations.
    }

    /** @Given /^the site has a index "([^"]+)" for class "([^"]+)" with type "([^"]+)"$/ */
    public function siteHasIndex(string $name, string $class, string $type): void
    {
        $index = new Index();
        $index->setName($name);
        $index->setClass($class);
        $index->setWorker($type);
        $this->indexRepository->add($index);
        $this->sharedStorage->set('index', $index);
    }

    /** @Given /^the site has a filter "([^"]+)" for index "([^"]+)"$/ */
    public function siteHasFilter(string $name, string $indexName): void
    {
        $index = $this->indexRepository->findOneBy(['name' => $indexName]);
        Assert::notNull($index, sprintf('Index "%s" was not found.', $indexName));

        $filter = new Filter();
        $filter->setName($name);
        $filter->setIndex($index);
        $this->filterRepository->add($filter);
        $this->sharedStorage->set('filter', $filter);
    }

    /** @Then /^there should be a filter with name "([^"]+)"$/ */
    public function filterShouldExist(string $name): void
    {
        $filter = $this->filterRepository->findOneBy(['name' => $name]);
        Assert::notNull($filter, sprintf('Filter "%s" was not found.', $name));
        Assert::same($name, $filter->getName());
    }
}
