<?php

declare(strict_types=1);

namespace Sylius\Behat\Context\Api\Admin;

use Behat\Behat\Context\Context;
use Behat\Step\When;
use Behat\Step\Then;
use Sylius\Behat\Client\ApiClientInterface;
use Sylius\Behat\Client\ResponseCheckerInterface;
use Sylius\Behat\Service\SharedStorageInterface;
use Sylius\Component\Promotion\Model\PromotionInterface;
use Webmozart\Assert\Assert;

final class PromotionCouponGenerationContext implements Context
{
    private int $amount = 0;
    private int $codeLength = 0;
    private ?int $usageLimit = null;
    private ?\Symfony\Component\HttpFoundation\Response $response = null;

    public function __construct(
        private ApiClientInterface $adminApiClient,
        private ResponseCheckerInterface $responseChecker,
        private SharedStorageInterface $sharedStorage,
    ) {
    }

    #[When('I want to generate new coupons for this promotion')]
    public function wantToGenerateCoupons(): void
    {
        $this->sharedStorage->set('coupon_generation_promotion', $this->sharedStorage->get('promotion'));
    }

    #[When('/^I choose the amount of (\d+) coupons to be generated$/')]
    public function chooseAmount(int $amount): void
    {
        $this->amount = $amount;
    }

    #[When('/^I specify their code length as (\d+)$/')]
    public function specifyCodeLength(int $length): void
    {
        $this->codeLength = $length;
    }

    #[When('/^I limit generated coupons usage to (\d+) times$/')]
    public function limitUsage(int $limit): void
    {
        $this->usageLimit = $limit;
    }

    #[When('I generate these coupons')]
    public function generateCoupons(): void
    {
        /** @var PromotionInterface $promotion */
        $promotion = $this->sharedStorage->get('coupon_generation_promotion');
        $this->response = $this->adminApiClient
            ->buildCreateRequest(sprintf('promotions/%s/coupons/generate', $promotion->getCode()))
            ->setRequestData([
                'amount' => $this->amount,
                'codeLength' => $this->codeLength,
                'usageLimit' => $this->usageLimit,
            ])
            ->create();
    }

    #[Then('I should be notified that they have been successfully generated')]
    public function couponsWereSuccessfullyGenerated(): void
    {
        Assert::notNull($this->response);
        Assert::true($this->responseChecker->isCreationSuccessful($this->response));
    }

    #[Then('/^there should be (\d+) coupons related to this promotion$/')]
    public function thereShouldBeCoupons(int $amount): void
    {
        /** @var PromotionInterface $promotion */
        $promotion = $this->sharedStorage->get('coupon_generation_promotion');
        $response = $this->adminApiClient->index(sprintf('promotions/%s/coupons', $promotion->getCode()));
        Assert::same($amount, $this->responseChecker->countCollectionItems($response));
    }
}
