<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Product;

use Behat\Behat\Context\Context;
use CoreShop\Bundle\ResourceBundle\Pimcore\PimcoreRepository;
use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
use CoreShop\Component\Core\Context\ShopperContext;
use CoreShop\Component\Rule\Condition\RuleValidationProcessor;
use Webmozart\Assert\Assert;

/**
 * Steps for exercising a product-specific rule against the current shopper.
 *
 * @SuppressWarnings(PHPMD.LongVariable)
 */
final class SpecificPriceRuleContext implements Context
{
    public function __construct(
        private PimcoreRepository $productRepository,
        private PimcoreRepository $customerRepository,
        private PimcoreRepository $ruleRepository,
        private PimcoreRepository $conditionRepository,
        private ShopperContext $shopperContext,
        private RuleValidationProcessor $ruleValidator,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    /** @Given /^adding a product specific price rule to product "([^"]+)" named "([^"]+)"$/ */
    public function addRule(string $productName, string $name): void
    {
        $product = $this->findByName($this->productRepository, $productName);
        $rule = $this->ruleRepository->getFactory()->createNew();
        $rule->setName($name);
        $rule->setActive(false);

        $rules = $product->getSpecificPriceRules();
        $rules[] = $rule;
        $product->setSpecificPriceRules($rules);
        $this->sharedStorage->set('specific_price_rule', $rule);
        $this->sharedStorage->set('specific_price_rule_product', $product);
    }

    /** @Given /^the specific price rule is active$/ */
    public function activateRule(): void
    {
        $this->sharedStorage->get('specific_price_rule')->setActive(true);
    }

    /** @Given /^the specific price rule has a condition customers with customer "([^"]+)"$/ */
    public function addCustomerCondition(string $email): void
    {
        $customer = $this->findByEmail($email);
        $condition = $this->conditionRepository->getFactory()->createNew();
        $condition->setType('customers');
        $condition->setSort(0);
        $condition->setConfiguration(['customers' => [$customer->getId()]]);
        $this->sharedStorage->get('specific_price_rule')->addCondition($condition);
    }

    /** @Then /^the specific price rule should be invalid for product "([^"]+)"$/ */
    public function assertInvalid(string $productName): void
    {
        $product = $this->findByName($this->productRepository, $productName);
        Assert::false($this->ruleValidator->isValid(
            $product,
            $this->sharedStorage->get('specific_price_rule'),
            $this->shopperContext->getContext(),
        ));
    }

    private function findByName(PimcoreRepository $repository, string $name): object
    {
        $listing = $repository->getList();
        $listing->setCondition('name = ?', [$name]);
        $item = $listing->current();
        Assert::notNull($item, sprintf('Could not find "%s".', $name));

        return $item;
    }

    private function findByEmail(string $email): object
    {
        $listing = $this->customerRepository->getList();
        $listing->setCondition('email = ?', [$email]);
        $customer = $listing->current();
        Assert::notNull($customer, sprintf('Could not find customer "%s".', $email));

        return $customer;
    }
}
