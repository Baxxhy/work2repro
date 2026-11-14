<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Service\Checker\EmailCheckerInterface;
use Sylius\Component\Core\Model\OrderInterface;
use Symfony\Component\HttpFoundation\Response;
use Webmozart\Assert\Assert;

final readonly class ResendingOrderConfirmationEmailContext implements Context
{
    public function __construct(
        private ApiClientInterface $adminApiClient,
        private EmailCheckerInterface $emailChecker,
    ) {
    }

    #[When('/^I view the summary of the order "([^"]+)"$/')]
    public function iViewTheSummaryOfTheOrder(OrderInterface $order): void
    {
        $response = $this->adminApiClient->show('orders', (string) $order->getTokenValue());
        Assert::eq(Response::HTTP_OK, $response->getStatusCode());
    }

    #[When('I cancel this order')]
    public function iCancelThisOrder(OrderInterface $order): void
    {
        $response = $this->adminApiClient->requestPatch('/api/v2/admin/orders/' . $order->getTokenValue() . '/cancel');
        Assert::eq(Response::HTTP_OK, $response->getStatusCode());
    }

    #[Then('I should not be able to resend the order confirmation email')]
    public function iShouldNotBeAbleToResendTheOrderConfirmationEmail(OrderInterface $order): void
    {
        $response = $this->adminApiClient->customAction(
            '/api/v2/admin/orders/' . $order->getTokenValue() . '/resend-confirmation-email',
            'POST',
        );
        Assert::notEq(Response::HTTP_ACCEPTED, $response->getStatusCode());
    }

    #[Then('/^an email with the confirmation of the order "([^"]+)" should not be sent to "([^"]+)"$/')]
    public function anEmailWithTheConfirmationShouldNotBeSentTo(string $orderNumber, string $email): void
    {
        Assert::false($this->emailChecker->hasRecipient($email), sprintf('An email was sent to %s.', $email));
    }
}
