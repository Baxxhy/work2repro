<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Index;

use Behat\Behat\Context\Context;
use CoreShop\Component\Index\Model\Index;
use CoreShop\Component\Index\Model\IndexInterface;
use CoreShop\Component\Index\Worker\WorkerInterface;
use CoreShop\Component\Registry\ServiceRegistryInterface;
use CoreShop\Component\Resource\Repository\RepositoryInterface;
use Doctrine\DBAL\Connection;
use Pimcore\Model\DataObject\ClassDefinition;
use Pimcore\Model\DataObject\Concrete;
use Webmozart\Assert\Assert;

final class IndexContext implements Context
{
    private ?IndexInterface $index = null;

    public function __construct(
        private RepositoryInterface $indexRepository,
        private ServiceRegistryInterface $workers,
        private Connection $connection,
    ) {
    }

    /**
     * @Given /^the site has a index "([^"]+)" for behat-class "([^"]+)" with type "([^"]+)"$/
     */
    public function createIndex(string $name, string $className, string $type): void
    {
        $class = ClassDefinition::getByName($className);
        Assert::notNull($class);

        $index = new Index();
        $index->setName($name);
        $index->setClass('Pimcore\\Model\\DataObject\\' . $class->getName());
        $index->setWorker($type);
        $this->indexRepository->add($index);

        /** @var WorkerInterface $worker */
        $worker = $this->workers->get($type);
        $worker->createOrUpdateIndexStructures($index);
        $this->index = $index;
    }

    /**
     * @Then /^the index should not have indexed the object$/
     */
    public function indexShouldNotContainObject(Concrete $object): void
    {
        Assert::notNull($this->index);
        $worker = $this->workers->get($this->index->getWorker());
        Assert::isCallable([$worker, 'getTablename']);
        $table = $worker->getTablename($this->index->getName());
        $count = $this->connection->fetchOne(
            sprintf('SELECT COUNT(*) FROM `%s` WHERE `o_id` = ?', str_replace('`', '``', $table)),
            [$object->getId()],
        );
        Assert::same(0, (int) $count);
    }
}
