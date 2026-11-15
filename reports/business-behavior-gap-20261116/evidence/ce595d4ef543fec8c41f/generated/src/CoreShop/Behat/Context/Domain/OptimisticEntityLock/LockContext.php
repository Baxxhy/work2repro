<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\OptimisticEntityLock;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\OptimisticEntityLockBundle\Exception\OptimisticLockException;
use CoreShop\Bundle\OptimisticEntityLockBundle\Manager\EntityLockManagerInterface;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use Pimcore\Model\DataObject\Concrete;
use Webmozart\Assert\Assert;

final class LockContext implements Context
{
    public function __construct(
        private SharedStorageInterface $sharedStorage,
        private EntityLockManagerInterface $entityLockManager,
    ) {
    }

    /**
     * @Given /^I successfully lock the (object-instance) with the current version$/
     */
    public function lockObjectWithCurrentVersion(Concrete $object): void
    {
        $this->entityLockManager->lock($object, $object->getOptimisticLockVersion());
    }

    /** @Then /^I successfully save versioned object-instance-2$/ */
    public function saveVersionedObject2(): void
    {
        $object = $this->sharedStorage->get('object-instance-2');
        Assert::isInstanceOf($object, Concrete::class);
        $object->save();
    }

    /** @Then /^I unsuccessfully save versioned object-instance$/ */
    public function unsuccessfullySaveVersionedObject(): void
    {
        $object = $this->sharedStorage->get('object-instance');
        Assert::isInstanceOf($object, Concrete::class);

        try {
            $object->save();
        } catch (OptimisticLockException) {
            return;
        }

        Assert::fail('Expected saving the stale object to raise an optimistic lock exception.');
    }
}
