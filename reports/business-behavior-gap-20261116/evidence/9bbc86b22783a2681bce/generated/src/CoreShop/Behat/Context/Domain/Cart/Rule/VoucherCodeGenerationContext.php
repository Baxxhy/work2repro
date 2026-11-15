<?php

declare(strict_types=1);

namespace CoreShop\Behat\Context\Domain\Cart\Rule;

use Behat\Behat\Context\Context;
use CoreShop\Component\Order\Generator\CodeGeneratorCheckerInterface;
use CoreShop\Component\Order\Model\CartPriceRule;
use CoreShop\Component\Order\Model\CartPriceRuleVoucherGenerator;
use Webmozart\Assert\Assert;

final class VoucherCodeGenerationContext implements Context
{
    private ?CartPriceRule $rule = null;
    private ?CartPriceRuleVoucherGenerator $generator = null;

    public function __construct(private CodeGeneratorCheckerInterface $checker)
    {
    }

    /** @Given /^the site operates on a store in "([^"]+)"$/ */
    public function storeInCountry(string $country): void
    {
    }

    /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
    public function currency(string $name, string $iso): void
    {
    }

    /** @Given /^I am in country "([^"]+)"$/ */
    public function inCountry(string $country): void
    {
    }

    /** @Given /^adding a cart price rule named "([^"]+)"$/ */
    public function addingCartPriceRule(string $name): void
    {
        $this->rule = new CartPriceRule();
        $this->rule->setName($name);
    }

    /** @When /^I want to generate (\d+) codes with a length of (\d+) in ([a-z]+) characters for the cart rule$/ */
    public function configureGeneration(int $amount, int $length, string $format): void
    {
        Assert::notNull($this->rule, 'A cart price rule must be created first.');

        $this->generator = new CartPriceRuleVoucherGenerator();
        $this->generator->setAmount($amount);
        $this->generator->setLength($length);
        $this->generator->setFormat($format);
        $this->generator->setPrefix('');
        $this->generator->setCartPriceRule($this->rule);
    }

    /** @Then /^the generation of the codes failed$/ */
    public function generationFailed(): void
    {
        Assert::notNull($this->generator, 'Generation parameters must be configured first.');
        Assert::false($this->checker->isGenerationPossible($this->generator));
    }
}
