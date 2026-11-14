<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Shop\Cart;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Context\Setup\CartContext;
use Sylius\Behat\Context\Setup\ShopSecurityContext;
use Sylius\Behat\Service\SecurityServiceInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Core\Model\OrderInterface;
use Webmozart\Assert\Assert;

final class CartLogoutContext implements Context
{
    public function __construct(
        private readonly CartContext $cartContext,
        private readonly ShopSecurityContext $securityContext,
        private readonly SecurityServiceInterface $securityService,
        private readonly SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I add this product to the cart')]
    public function iAddThisProductToTheCart(): void
    {
        $this->cartContext->iAddedProductToTheCart(
            $this->sharedStorage->get('product'),
            $this->sharedStorage->get('cart_token'),
        );
    }

    #[When('/^I log in as "([^"]+)" with "([^"]+)" password$/')]
    public function iLogInAs(string $email, string $password): void
    {
        $this->securityContext->iAmLoggedInAs($email);
    }

    #[When('I log out')]
    public function iLogOut(): void
    {
        $this->securityService->logOut();
    }

    #[Then('I should not have access to the summary of my previous cart')]
    public function iShouldNotHaveAccessToTheSummaryOfMyPreviousCart(): void
    {
        Assert::null($this->sharedStorage->get('user'));
        Assert::null($this->sharedStorage->get('token'));
    }
}
