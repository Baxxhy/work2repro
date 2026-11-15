# 需求指定业务行为的执行与观察缺口


## 阶段性判断

当前证据支持“存在重复出现的执行、准备或观察缺口”。“经常发生”的总体频率仍无法确定。旧6例来自按结果筛选的24例，新增20例按项目定额筛选，模型和生成配置也仅覆盖本次Codex GPT-6 Luna medium复现。

旧6例跨6个项目，复核后为A操作未执行2例、B目标状态未观察1例、C结果关系或异常约束未断言2例、A_setup必要准备状态未建立1例。coddy同时具有A/B/C，以A作互斥主分类。Sylius和python-docx的真实目标操作已有动态执行证据，上一轮分类在本报告修正。

新增20条通过但非KillComplete案例中，5条观察到明确缺口，分布于CoreShop与e-petitions。包括3条背景准备缺失、1条管理员状态/页面未观察、1条列表关系断言缺失。另2条证据不足，13条未确认明确需求缺口。5/20只描述本次筛选集合，其中3条CoreShop背景缺失与主要操作漏检的因果关系尚未证明。

15条新增KillComplete对照中，1条仍有列表对象—值关系断言缺失。缺口可以伴随KillComplete出现；低分也可能来自参考额外准备、调用或检查。现有结果不足以据此识别模型能力的单一根因。

## 固定数据与计分

旧子集160条，官方排除1条census_pass，实际计分159条。执行通过44条，其中20条KillComplete、24条通过且存在存活变异体。官方G_i为参考测试杀死集合，扣除reference_excluded与reviewed nondeterministic；n_scored=|G_i|−n_dropped，recall=n_killed/n_scored。KillComplete还要求原实现通过、n_scored>0且全部scored变异被杀死。项目timeout/drop规则沿用锁定源码。coddy旧任务的5个drop和Kapua重复观测告警均保留。

新增样本来自780条已完成任务的固定快照，占2051条计划集合38.03%。780是完成记录数，不能直接用作官方质量计分分母。新35条均为原实现通过且mutation_status=scored，15条控制为KillComplete。完成快照之后的运行进度不影响本轮分析。


[官方计分源码](../pass-nonkill-20261116/source-context/official-score.py)；[新增固定任务清单](manifest.json)；[核对结果](audit-summary.json)

## 证据等级与类别

A指需求指定的目标操作被空步骤、自建对象或自定义行为替代。A_setup单列必要前置状态缺失，以免把已执行的目标操作误写为未执行。B指真实操作执行后未观察需求指定角色、对象或外部边界。C指观察存在，但断言未核验具体值、类型或对象关系。D用于检查了无直接关系的其他行为，本轮没有需要单独确认的D案例。E为证据不足。N表示当前审查没有确认该缺口，不能解释为已证明需求完全满足。

“确认缺口”由需求与代码义务对照决定。“代表性存活可解释”需要相应变异和执行标签支持。“实际变异传播路径已观测”需要变异运行轨迹或失败位置。本轮取得官方参考基线gold_run的direct_calls及coverage_lines，逐变异pool主要提供killed标签，无法补全每个变异的失败堆栈。以下明确区分这些层级。

## 旧6例重新核验


### coreshop/features/domain/order/create_order_with_discount.feature:23


主分类与兼类 `A`，证据状态 `CONFIRMED_GAP`。原实现 `passed`，杀死 0/200，存活 200。

```gherkin
  Background:
    Given the site operates on a store in "Austria"
    And the site has a country "Germany" with currency "EUR"
    And the country "Germany" is active
    And the site operates on locale "en"
    And the site has a tax rate "AT" with "20%" rate
    And the site has a tax rule group "AT"
    And the tax rule group has a tax rule for country "Austria" with tax rate "AT"
    And the site has a product "T-Shirt" priced at 2000
    And the product has the tax rule group "AT"
    And the site has a customer "some-customer@something.com"
    And the customer "some-customer@something.com" has an address with country "Austria", "4600", "Wels", "Freiung", "9-11/N3"
    And the customer "some-customer@something.com" has an address with country "Germany", "04600", "Wels", "Freiung", "9-11/N3"
    And the cart belongs to customer "some-customer@something.com"
    And adding a cart price rule named "discount"
    And the cart rule is active
    And the cart rule is a voucher rule with code "asdf"
    And the cart rule has a action discount with 20 in currency "EUR" off
  Scenario: Create a new order and add a product
    Given I add the product "T-Shirt" to my cart
    And I apply the voucher code "asdf" to my cart
    And the cart ships to customer "some-customer@something.com" address with postcode "4600"
    And the cart invoices to customer "some-customer@something.com" address with postcode "4600"
    And I create an order from my cart
    Then there should be one product in my order
```

商品存入本地数组，匿名 order 返回同一数组；voucher、地址及多个背景步骤为空。Then 只数自建对象条目。参考 OrderContext.transformCartToOrder 执行生产状态机。候选 direct_calls 仅1条，参考3157条，结合生成源码确认实际购物车转订单未执行。200个存活的需求相关性仍须逐个判断。

#### 实际调用、状态读取与断言位置


[CreateOrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/generated/src/CoreShop/Behat/Context/Domain/Order/CreateOrderContext.php)


```text
  22 
  23     /** @Given /^the site operates on a store in "([^"]+)"$/ */
  24     public function siteOperatesOnStore(string $country): void
  25     {
  26     }
  27 
  28     /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
  29     public function siteHasCountry(string $country, string $currency): void
  30     {
  31     }
  32 
  33     /** @Given /^the country "([^"]+)" is active$/ */
  34     public function countryIsActive(string $country): void
  35     {
  36     }
  37 
  51     }
  52 
  53     /** @Given /^the tax rule group has a tax rule for country "([^"]+)" with tax rate "([^"]+)"$/ */
  54     public function taxRuleGroupHasTaxRule(string $country, string $rate): void
  55     {
  56     }
  57 
  71     }
  72 
  73     /** @Given /^the customer "([^"]+)" has an address with country "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/ */
  74     public function customerHasAddress(string $email, string $country, string $postcode, string $city, string $street, string $number): void
  75     {
  76     }
  77 
  96     }
  97 
  98     /** @Given /^the cart rule has a action discount with (\d+) in currency "([^"]+)" off$/ */
  99     public function cartRuleHasDiscount(int $amount, string $currency): void
 100     {
 101     }
 102 
 125     public function createOrderFromCart(): void
 126     {
 127         $this->order = new class($this->items) {
 128             public function __construct(private array $items)
 129             {
 130             }
 131 
 132             public function getItems(): ?array
 133             {
 134                 return $this->items;
 135             }
 141     {
 142         Assert::notNull($this->order, 'No order was created from the cart.');
 143         Assert::count($this->order->getItems(), 1);
 144     }
 145 }
```

#### 开发者路径及执行证据


参考源码入口见 [OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Domain/OrderContext.php)、[ActionFormTrait.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ActionFormTrait.php)、[CartContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartContext.php)、[CartPriceRuleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartPriceRuleContext.php)、[ConditionFormTrait.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ConditionFormTrait.php)、[CountryContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)、[CustomerContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CustomerContext.php)、[LocaleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/LocaleContext.php)、[OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/OrderContext.php)、[ProductContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ProductContext.php)、[StoreContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)、[TaxRateContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRateContext.php)、[TaxRuleGroupContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRuleGroupContext.php)、[CartContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartContext.php)、[CartPriceRuleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartPriceRuleContext.php)、[CountryContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CountryContext.php)、[CurrencyContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CurrencyContext.php)、[CustomerContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CustomerContext.php)、[OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/OrderContext.php)、[ProductContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/ProductContext.php)、[TaxRateContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRateContext.php)、[TaxRuleGroupContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRuleGroupContext.php)。

[OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Domain/OrderContext.php)


```text
  40     {
  41         Assert::eq(
  42             count($order->getItems()),
  43             1,
  44             sprintf(
  45                 'There should be only one product in the order, but found %d',
  46                 count($order->getItems()),
  47             ),
  48         );
  49     }
 347         );
 348 
 349         foreach ($order->getItems() as $item) {
 350             Assert::true(
 351                 $item->isImmutable(),
 352                 'Order Item is mutable, but should be immutable!',
```

[ActionFormTrait.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ActionFormTrait.php)


```text

```

[CartContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartContext.php)


```text
  77         $foundItem = null;
  78 
  79         foreach ($cart->getItems() as $cartItem) {
  80             if ($cartItem->getProduct()->getId() === $product->getId()) {
  81                 $foundItem = $cartItem;
  82             }
 142         $cart = $this->cartContext->getCart();
 143 
 144         foreach ($cart->getItems() as $cartItem) {
 145             if ($cartItem->getProduct()->getId() === $product->getId()) {
 146                 $this->cartModifier->removeFromList($cart, $cartItem);
 147 
 167     public function theCartShipsToCustomersFirstAddress(CustomerInterface $customer): void
 168     {
 169         Assert::greaterThan(count($customer->getAddresses()), 0);
 170 
 171         $address = $customer->getAddresses();
 172 
 180     public function theCartShipsToCustomersAddressWithPostcode(CustomerInterface $customer, $postcode): void
 181     {
 182         Assert::greaterThan(count($customer->getAddresses()), 0);
 183 
 184         $address = current(array_filter($customer->getAddresses(), function ($address) use ($postcode) {
 185             return $address->getPostcode() === $postcode;
 197     public function theCartInvoicesToCustomersAddressWithPostcode(CustomerInterface $customer, $postcode): void
 198     {
 199         Assert::greaterThan(count($customer->getAddresses()), 0);
 200 
 201         $address = current(array_filter($customer->getAddresses(), function ($address) use ($postcode) {
 202             return $address->getPostcode() === $postcode;
```

[CartPriceRuleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartPriceRuleContext.php)


```text
  22 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Action\GiftProductConfigurationType;
  23 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Condition\CategoriesConfigurationType;
  24 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Condition\CountriesConfigurationType;
  25 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Condition\CurrenciesConfigurationType;
  26 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Condition\CustomerGroupsConfigurationType;
  27 use CoreShop\Bundle\CoreBundle\Form\Type\Rule\Condition\CustomersConfigurationType;
  32 use CoreShop\Bundle\OrderBundle\Form\Type\CartPriceRuleConditionType;
  33 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Action\CartItemActionConfigurationType;
  34 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Action\DiscountAmountConfigurationType;
  35 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Action\DiscountPercentConfigurationType;
  36 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Action\SurchargeAmountConfigurationType;
  37 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Action\SurchargePercentConfigurationType;
  38 use CoreShop\Bundle\OrderBundle\Form\Type\Rule\Condition\AmountConfigurationType;
  44 use CoreShop\Component\Address\Model\ZoneInterface;
  45 use CoreShop\Component\Core\Model\CategoryInterface;
  46 use CoreShop\Component\Core\Model\CountryInterface;
  47 use CoreShop\Component\Core\Model\CurrencyInterface;
  48 use CoreShop\Component\Core\Model\CustomerInterface;
  49 use CoreShop\Component\Core\Model\OrderInterface;
 207 
 208     /**
 209      * @Given /^the (cart rule "[^"]+") has a condition countries with (country "[^"]+")$/
 210      * @Given /^the (cart rule) has a condition countries with (country "[^"]+")$/
 211      */
 212     public function theCartPriceRuleHasACountriesCondition(CartPriceRuleInterface $rule, CountryInterface $country): void
 213     {
 214         $this->assertConditionForm(CountriesConfigurationType::class, 'countries');
 215 
 216         $this->addCondition($rule, $this->createConditionWithForm('countries', [
 217             'countries' => [
 218                 $country->getId(),
 219             ],
 220         ]));
 221     }
 421 
 422     /**
 423      * @Given /^the (cart rule "[^"]+") has a action discount-percent with ([^"]+)% discount$/
 424      * @Given /^the (cart rule) has a action discount-percent with ([^"]+)% discount$/
 425      */
 426     public function theCartPriceRuleHasADiscountPercentAction(CartPriceRuleInterface $rule, $discount): void
 427     {
 428         $this->assertActionForm(DiscountPercentConfigurationType::class, 'discountPercent');
 429 
 430         $this->addAction($rule, $this->createActionWithForm('discountPercent', [
 431             'percent' => (int) $discount,
 432         ]));
 433     }
 434 
 435     /**
 436      * @Given /^the (cart rule "[^"]+") has a action discount with ([^"]+) in (currency "[^"]+") off$/
 437      * @Given /^the (cart rule) has a action discount with ([^"]+) in (currency "[^"]+") off$/
 438      * @Given /^the (cart rule "[^"]+") has a action discount with ([^"]+) in (currency "[^"]+") off applied on ([^"]+)$/
 439      * @Given /^the (cart rule) has a action discount with ([^"]+) in (currency "[^"]+") off applied on ([^"]+)$/
 440      */
 441     public function theCartPriceRuleHasADiscountAmountAction(CartPriceRuleInterface $rule, $amount, CurrencyInterface $currency, string $appliedOn = 'total'): void
 442     {
 443         $this->assertActionForm(DiscountAmountConfigurationType::class, 'discountAmount');
 444 
 445         $this->addAction($rule, $this->createActionWithForm('discountAmount', [
 446             'amount' => (int) $amount,
 447             'currency' => $currency->getId(),
 448             'applyOn' => $appliedOn,
 475 
 476     /**
 477      * @Given /^the (cart rule "[^"]+") has a action surcharge-percent with ([^"]+)% discount$/
 478      * @Given /^the (cart rule) has a action surcharge-percent with ([^"]+)% discount$/
 479      */
 480     public function theCartPriceRuleHasASurchargePercentAction(CartPriceRuleInterface $rule, $surcharge): void
 481     {
 600 
 601     /**
 602      * @Given /^the (cart item action) has a action discount-percent with ([^"]+)% discount$/
 603      */
 604     public function theCartItemActionHasADiscountPercentAction(ActionInterface $action, $discount): void
 605     {
 606         $this->assertActionForm(DiscountPercentConfigurationType::class, 'discountPercent');
 607 
 608         $this->actionAddAction($action, $this->createActionWithForm('discountPercent', [
 609             'percent' => (int) $discount,
 610         ]));
 611     }
 612 
 613     /**
 614      * @Given /^the (cart item action) has a action discount with ([^"]+) in (currency "[^"]+") off$/
 615      * @Given /^the (cart item action) has a action discount with ([^"]+) in (currency "[^"]+") off applied on ([^"]+)$/
 616      */
 617     public function theCartItemActionHasADiscountAmountAction(ActionInterface $action, $amount, CurrencyInterface $currency, string $appliedOn = 'total'): void
 618     {
 619         $this->assertActionForm(DiscountAmountConfigurationType::class, 'discountAmount');
 620 
 621         $this->actionAddAction($action, $this->createActionWithForm('discountAmount', [
 622             'amount' => (int) $amount,
 623             'currency' => $currency->getId(),
 624             'applyOn' => $appliedOn,
```

[ConditionFormTrait.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ConditionFormTrait.php)


```text

```

[CountryContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)


```text
  20 use Behat\Behat\Context\Context;
  21 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  22 use CoreShop\Component\Address\Context\FixedCountryContext;
  23 use CoreShop\Component\Address\Model\ZoneInterface;
  24 use CoreShop\Component\Core\Model\CountryInterface;
  25 use CoreShop\Component\Core\Model\CurrencyInterface;
  26 use CoreShop\Component\Core\Model\StoreInterface;
  27 use CoreShop\Component\Core\Repository\CountryRepositoryInterface;
  28 use CoreShop\Component\Resource\Factory\FactoryInterface;
  29 use Doctrine\Persistence\ObjectManager;
  30 use Symfony\Component\Process\Process;
  31 
  32 final class CountryContext implements Context
  33 {
  34     public function __construct(
  35         private SharedStorageInterface $sharedStorage,
  36         private ObjectManager $objectManager,
  37         private FactoryInterface $countryFactory,
  38         private CountryRepositoryInterface $countryRepository,
  39         private FixedCountryContext $fixedCountryContext,
  40         private string $kernelRootDirectory,
  41     ) {
  42     }
  43 
  44     /**
  45      * @Given /^the (country "[^"]+") is valid for (store "[^"]+")$/
  46      * @Given /^the (country) is valid for (store "[^"]+")$/
  47      */
  48     public function currencyIsValidForStore(CountryInterface $country, StoreInterface $store): void
  49     {
  50         $store->addCountry($country);
  51 
  52         $this->objectManager->persist($store);
  53         $this->objectManager->flush();
  55 
  56     /**
  57      * @Given /^the (country "[^"]+") is invalid for (store "[^"]+")$/
  58      */
  59     public function currencyIsInValidForStore(CountryInterface $country, StoreInterface $store): void
  60     {
  61         $store->removeCountry($country);
  62 
  63         $this->objectManager->persist($store);
  64         $this->objectManager->flush();
  66 
  67     /**
  68      * @Given /^the site has a country "([^"]+)" with (currency "[^"]+")$/
  69      */
  70     public function theSiteHasACountry($name, CurrencyInterface $currency): void
  71     {
  72         $this->createCountry($name, $currency);
  73     }
  74 
  75     /**
  76      * @Then /^the (country "[^"]+") is in (zone "[^"]+")$/
  77      */
  78     public function theCountryIsInZone(CountryInterface $country, ZoneInterface $zone): void
  79     {
  80         $country->setZone($zone);
  81 
  82         $this->saveCountry($country);
  83     }
  84 
  85     /**
  86      * @Then /^the (country "[^"]+") is active$/
  87      */
  88     public function theCountryIsActive(CountryInterface $country): void
  89     {
  90         $country->setActive(true);
  91 
  92         $this->saveCountry($country);
  93     }
  94 
  95     /**
  96      * @Given /^I am in (country "[^"]+")$/
  97      */
  98     public function iAmInCountry(CountryInterface $country): void
  99     {
 100         $this->fixedCountryContext->setCountry($country);
 101     }
 102 
 103     /**
 104      * @Given /^the (countries) address format is "(.*)"$/
 105      * @Given /^the (countries "[^"]+") address format is "(.*)"$/
 106      */
 107     public function theCountriesAddressFormatIs(CountryInterface $country, $format): void
 108     {
 109         $country->setAddressFormat(str_replace("'", '"', $format));
 110 
 111         $this->saveCountry($country);
 112     }
 113 
 114     /**
 132      * @param string $name
 133      */
 134     private function createCountry($name, CurrencyInterface $currency): void
 135     {
 136         $country = $this->countryRepository->findByName($name, 'en');
 137 
 138         if (!$country) {
 139             /**
 140              * @var CountryInterface $country
 141              */
 142             $country = $this->countryFactory->createNew();
 143             $country->setName($name, 'en');
 144             $country->setIsoCode($name);
 145             $country->setActive(true);
 146             $country->setCurrency($currency);
 147 
 148             $this->saveCountry($country);
 149         }
 150     }
 151 
 152     private function saveCountry(CountryInterface $country): void
 153     {
 154         $this->objectManager->persist($country);
 155         $this->objectManager->flush();
 156 
 157         $this->sharedStorage->set('country', $country);
 158     }
 159 }
```

[CustomerContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CustomerContext.php)


```text
  21 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  22 use CoreShop\Component\Address\Model\AddressInterface;
  23 use CoreShop\Component\Core\Model\CountryInterface;
  24 use CoreShop\Component\Core\Model\CustomerInterface;
  25 use CoreShop\Component\Core\Model\UserInterface;
  26 use CoreShop\Component\Customer\Context\FixedCustomerContext;
  85      * @Then /^the (customer "[^"]+") was deleted$/
  86      */
  87     public function accountWasDeleted(CustomerInterface $customer): void
  88     {
  89         $customer->delete();
  90     }
 118 
 119     /**
 120      * @Given /^the (customer "[^"]+") has an address with (country "[^"]+"), "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/
 121      * @Given /^the (customer) has an address with (country "[^"]+"), "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/
 122      */
 123     public function theCustomerHasAnAddress(
 124         CustomerInterface $customer,
 125         CountryInterface $country,
 126         $postcode,
 127         $city,
 128         $street,
 133          */
 134         $address = $this->addressFactory->createNew();
 135         $address->setCountry($country);
 136         $address->setPostcode($postcode);
 137         $address->setCity($city);
 138         $address->setStreet($street);
 150 
 151     /**
 152      * @Then /^the (customer "[^"]+") address is (country "[^"]+"), "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/
 153      * @Then /^the (customer) address is (country "[^"]+"), "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/
 154      */
 155     public function theCustomersAddress(
 156         CustomerInterface $customer,
 157         CountryInterface $country,
 158         $postcode,
 159         $city,
 160         $street,
 177                 $found = true;
 178             }
 179             if ($address->getCountry() == $country) {
 180                 $found = true;
 181             }
 182         }
```

[LocaleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/LocaleContext.php)


```text

```

[OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/OrderContext.php)


```text
  42      * @Given /^I create an order from (my cart)$/
  43      */
  44     public function transformCartToOrder(OrderInterface $cart): void
  45     {
  46         $cart->setStore($this->storeContext->getStore());
  47 
```

[ProductContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ProductContext.php)


```text

```

[StoreContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)


```text
  20 use Behat\Behat\Context\Context;
  21 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  22 use CoreShop\Component\Core\Model\CountryInterface;
  23 use CoreShop\Component\Core\Model\CurrencyInterface;
  24 use CoreShop\Component\Core\Model\StoreInterface;
  25 use CoreShop\Component\Resource\Factory\FactoryInterface;
  34         private FactoryInterface $storeFactory,
  35         private FactoryInterface $currencyFactory,
  36         private FactoryInterface $countryFactory,
  37         private FixedStoreContext $fixedStoreContext,
  38     ) {
  39     }
  70 
  71     /**
  72      * @Given /^the site has a store "([^"]+)" with (country "[^"]+") and (currency "[^"]+")$/
  73      */
  74     public function siteHasAStoreWithCountryAndCurrency($name, CountryInterface $country, CurrencyInterface $currency): void
  75     {
  76         $store = $this->createStore($name, $currency, $country);
  77 
  78         $this->saveStore($store);
  79     }
  80 
  81     /**
  82      * @Given /^the site has a store "([^"]+)" with (country "[^"]+") and (currency "[^"]+") and gross values$/
  83      */
  84     public function siteHasAStoreWithCountryAndCurrencyAndGrossValues($name, CountryInterface $country, CurrencyInterface $currency): void
  85     {
  86         $store = $this->createStore($name, $currency, $country, true);
  87 
  88         $this->saveStore($store);
  89     }
 112         string $name,
 113         ?CurrencyInterface $currency = null,
 114         ?CountryInterface $country = null,
 115         $grossValues = false,
 116         $defaultStore = false,
 117     ): StoreInterface {
 135         }
 136 
 137         if (null === $country) {
 138             /**
 139              * @var CountryInterface $country
 140              */
 141             $country = $this->countryFactory->createNew();
 142             $country->setName('Austria', 'en');
 143             $country->setIsoCode('AT');
 144             $country->setCurrency($currency);
 145             $country->setActive(true);
 146             $country->setAddressFormat('
 147                 {{ company }}
 148                 {{ salutation }} {{ firstname }} {{ lastname }}
 149                 {{ street }}
 150                 {{ postcode }}
 151                 {{ country.name }}
 152             ');
 153 
 154             $this->entityManager->persist($country);
 155 
 156             $this->sharedStorage->set('country', $country);
 157         }
 158 
 159         $this->entityManager->flush();
 161         $store->setName($name);
 162         $store->setCurrency($currency);
 163         $store->setBaseCountry($country);
 164         $store->addCountry($country);
 165         $store->setUseGrossPrice($grossValues);
 166 
 167         return $store;
```

[TaxRateContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRateContext.php)


```text

```

[TaxRuleGroupContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRuleGroupContext.php)


```text
  20 use Behat\Behat\Context\Context;
  21 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  22 use CoreShop\Component\Core\Model\CountryInterface;
  23 use CoreShop\Component\Core\Model\TaxRuleInterface;
  24 use CoreShop\Component\Resource\Factory\FactoryInterface;
  25 use CoreShop\Component\Taxation\Calculator\TaxCalculatorInterface;
  47 
  48     /**
  49      * @Given /^the (tax rule group "[^"]+") has a tax rule for (country "[^"]+") with (tax rate "[^"]+")$/
  50      * @Given /^the ([^"]+) has a tax rule for (country "[^"]+") with (tax rate "[^"]+")$/
  51      */
  52     public function theTaxRuleGroupHasATaxRuleForCountryWithTax(TaxRuleGroupInterface $taxRuleGroup, CountryInterface $country, TaxRateInterface $taxRate): void
  53     {
  54         /**
  55          * @var TaxRuleInterface $taxRule
  58         $taxRule->setTaxRuleGroup($taxRuleGroup);
  59         $taxRule->setTaxRate($taxRate);
  60         $taxRule->setCountry($country);
  61         $taxRule->setBehavior(TaxCalculatorInterface::DISABLE_METHOD);
  62 
  63         $this->objectManager->persist($taxRule);
  66 
  67     /**
  68      * @Given /^the (tax rule group "[^"]+") has a tax rule for (country "[^"]+") with (tax rate "[^"]+") and it combines all rules$/
  69      * @Given /^([^"]+) has a tax rule for (country "[^"]+") with (tax rate "[^"]+") and it combines all rules$/
  70      */
  71     public function theTaxRuleGroupHasATaxRuleForCountryWithTaxAndCombination(TaxRuleGroupInterface $taxRuleGroup, CountryInterface $country, TaxRateInterface $taxRate): void
  72     {
  73         /**
  74          * @var TaxRuleInterface $taxRule
  77         $taxRule->setTaxRuleGroup($taxRuleGroup);
  78         $taxRule->setTaxRate($taxRate);
  79         $taxRule->setCountry($country);
  80         $taxRule->setBehavior(TaxCalculatorInterface::COMBINE_METHOD);
  81 
  82         $this->objectManager->persist($taxRule);
  85 
  86     /**
  87      * @Given /^the (tax rule group "[^"]+") has a tax rule for (country "[^"]+") with (tax rate "[^"]+") and it calculates them one after another$/
  88      * @Given /^([^"]+) has a tax rule for (country "[^"]+") with (tax rate "[^"]+") and it calculates them one after another$/
  89      */
  90     public function theTaxRuleGroupHasATaxRuleForCountryWithTaxAndOneAfterAnother(TaxRuleGroupInterface $taxRuleGroup, CountryInterface $country, TaxRateInterface $taxRate): void
  91     {
  92         /**
  93          * @var TaxRuleInterface $taxRule
  96         $taxRule->setTaxRuleGroup($taxRuleGroup);
  97         $taxRule->setTaxRate($taxRate);
  98         $taxRule->setCountry($country);
  99         $taxRule->setBehavior(TaxCalculatorInterface::ONE_AFTER_ANOTHER_METHOD);
 100 
 101         $this->objectManager->persist($taxRule);
```

[CartContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartContext.php)


```text

```

[CartPriceRuleContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartPriceRuleContext.php)


```text

```

[CountryContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CountryContext.php)


```text
  20 use Behat\Behat\Context\Context;
  21 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  22 use CoreShop\Component\Core\Model\CountryInterface;
  23 use CoreShop\Component\Core\Repository\CountryRepositoryInterface;
  24 use Webmozart\Assert\Assert;
  25 
  26 final class CountryContext implements Context
  27 {
  28     public function __construct(
  29         private SharedStorageInterface $sharedStorage,
  30         private CountryRepositoryInterface $countryRepository,
  31     ) {
  32     }
  33 
  34     /**
  35      * @Transform /^country "([^"]+)"$/
  36      * @Transform /^countries "([^"]+)"$/
  37      */
  38     public function getCountryByName($name): CountryInterface
  39     {
  40         /**
  41          * @var CountryInterface[] $countries
  42          */
  43         $countries = $this->countryRepository->findByName($name, 'en');
  44 
  45         Assert::eq(
  46             count($countries),
  47             1,
  48             sprintf('%d country has been found with name "%s".', count($countries), $name),
  49         );
  50 
  51         return reset($countries);
  52     }
  53 
  54     /**
  55      * @Transform /^country$/
  56      * @Transform /^countries$/
  57      */
  58     public function country(): CountryInterface
  59     {
  60         return $this->sharedStorage->get('country');
  61     }
  62 }
```

[CurrencyContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CurrencyContext.php)


```text
  43 
  44         Assert::eq(
  45             count($currencies),
  46             1,
  47             sprintf('%d currencies has been found with iso "%s".', count($currencies), $iso),
  48         );
  49 
  50         return reset($currencies);
```

[CustomerContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CustomerContext.php)


```text

```

[OrderContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/OrderContext.php)


```text

```

[ProductContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/ProductContext.php)


```text
  49 
  50         Assert::eq(
  51             count($list->getObjects()),
  52             1,
  53             sprintf('%d products has been found with name "%s".', count($list->getObjects()), $productName),
  54         );
  55 
  56         $objects = $list->getObjects();
  77 
  78         Assert::eq(
  79             count($list->getObjects()),
  80             1,
  81             sprintf('%d products has been found with key "%s".', count($list->getObjects()), $productName),
  82         );
  83 
  84         $objects = $list->getObjects();
```

[TaxRateContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRateContext.php)


```text
  41 
  42         Assert::eq(
  43             count($rates),
  44             1,
  45             sprintf('%d country has been found with name "%s".', count($rates), $name),
  46         );
  47 
  48         return reset($rates);
```

[TaxRuleGroupContext.php](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRuleGroupContext.php)


```text
  43 
  44         Assert::eq(
  45             count($groups),
  46             1,
  47             sprintf('%d tax rule groups has been found with name "%s".', count($groups), $name),
  48         );
  49 
  50         return reset($groups);
```

候选基线direct_calls有1条，官方参考基线有3157条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/execution.json)；[参考实际基线调用](gold-execution/f54d3444bfce11f4c30f.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

### coddy-agent/features/ask_mode_http.feature:22


主分类与兼类 `A;B;C`，证据状态 `CONFIRMED_GAP`。原实现 `passed`，杀死 138/388，存活 250。

```gherkin
  The ask profile is a session mode like agent and plan: POST /v1/responses with
  model "ask" runs the ReAct loop over the real OpenAI-compatible transport with
  the read-only tool set, and a mutating call the model emits anyway is refused
  on its way to the tool. Agent and plan keep the tool sets they had, so the
  third mode changes nothing for the two that already exist.
  Scenario: The same model in agent mode still writes the file
    Given a coddy gateway backed by a streaming stub model that writes a file, then answers
    When a client sends a streaming "agent" prompt over POST /v1/responses
    Then the workspace file was written
    And the model was offered the full agent tool set
    And the transcript reports the session in "agent" mode
```

自定义 runner 直接 os.WriteFile，tools() 构造 full-agent-tool-set，send() 将输入mode赋给transcript。HTTP入口的部分代码被调用，但需求指定的生产 Agent.Run、真实工具提供和会话模式观察被替代。参考动态记录包含 NewAgent、Agent.Run 和真实transport调用。生成的写文件、工具和模式断言均检查自建结果。toolsets return defs→nil 的存活与未调用该生产路径一致。

#### 实际调用、状态读取与断言位置


[bdd_ask_mode_e2e_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/generated/external/httpserver/bdd_ask_mode_e2e_test.go)


```text
  26 	workspace, file string
  27 	toolNames []string
  28 	transcript string
  29 }
  30 
  31 func TestAskModeHTTPE2E(t *testing.T) {
  40 			sc.Step(`^the workspace file was written$`, w.written)
  41 			sc.Step(`^the model was offered the full agent tool set$`, w.tools)
  42 			sc.Step(`^the transcript reports the session in "([^"]*)" mode$`, w.mode)
  43 		},
  44 		Options: &godog.Options{Format:"progress", Paths:[]string{"features/ask_mode_http.feature"}},
  45 	}
  46 	if status:=suite.Run(); status!=0 { t.Fatalf("godog suite failed: %d", status) }
  47 }
  48 
  49 func (w *askModeHTTPWorld) gateway() error {
  55 		for _,b:=range prompt { if b.Type=="text" { st.AddMessage(llm.Message{Role:llm.RoleUser,Content:b.Text}) } }
  56 		st.AddMessage(llm.Message{Role:llm.RoleAssistant,Content:"done"})
  57 		if err:=os.WriteFile(w.file,[]byte("written"),0644); err!=nil{return "",err}
  58 		return string(acp.StopReasonEndTurn),nil
  59 	}
  60 	mgr:=session.NewManager(cfg,noopSender{},run,slog.Default(),root,nil)
  69 	if res.StatusCode<200||res.StatusCode>=300{return fmt.Errorf("responses status %d",res.StatusCode)}
  70 	// The gateway delegates the turn to the configured session runner.
  71 	w.transcript=mode
  72 	return nil
  73 }
  74 func(w *askModeHTTPWorld) written()error{ if _,err:=os.Stat(w.file);err!=nil{return fmt.Errorf("workspace file missing: %w",err)}; return nil }
  75 func(w *askModeHTTPWorld) tools()error{
  76 	// A nil tool allowlist is the production agent's unrestricted/full registry.
  77 	w.toolNames=[]string{"full-agent-tool-set"}
  78 	if len(w.toolNames)==0{return fmt.Errorf("agent tool set was empty")}; return nil
  79 }
  80 func(w *askModeHTTPWorld) mode(mode string)error{if w.transcript!=mode{return fmt.Errorf("transcript mode %q, want %q",w.transcript,mode)};return nil}
```

[bdd_compaction_http_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/generated/external/httpserver/bdd_compaction_http_test.go)


```text

```

#### 开发者路径及执行证据


参考源码入口见 [bdd_ask_mode_e2e_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_ask_mode_e2e_test.go)、[bdd_compaction_http_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_compaction_http_test.go)。

[bdd_ask_mode_e2e_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_ask_mode_e2e_test.go)


```text
 182 	}
 183 	readPath := filepath.Join(s.cwd, "ask-e2e-note.txt")
 184 	if err := os.WriteFile(readPath, []byte(askE2ENoteToken+"\n"), 0o644); err != nil {
 185 		return err
 186 	}
 187 	s.backend = &askModeStubBackend{
 201 	log := slog.Default()
 202 	runner := func(ctx context.Context, st *session.State, prompt []acp.ContentBlock, snd acp.UpdateSender) (string, error) {
 203 		return agent.NewAgent(cfg, st, snd, log).Run(ctx, prompt)
 204 	}
 205 	store := &session.FileStore{Root: filepath.Join(s.root, "sessions")}
 206 	mgr := session.NewManager(cfg, noopSender{}, runner, log, s.cwd, store)
 238 }
 239 
 240 // offeredTools returns the tool names the first request of the turn carried.
 241 func (s *askModeE2EState) offeredTools() ([]string, error) {
 242 	requests := s.backend.snapshot()
 243 	if len(requests) == 0 {
 244 		return nil, fmt.Errorf("the stub model was never called")
 255 
 256 func (s *askModeE2EState) offeredOnlyReadOnlyTools() error {
 257 	names, err := s.offeredTools()
 258 	if err != nil {
 259 		return err
 260 	}
 275 
 276 func (s *askModeE2EState) offeredFullAgentToolSet() error {
 277 	names, err := s.offeredTools()
 278 	if err != nil {
 279 		return err
 280 	}
 292 
 293 func (s *askModeE2EState) offeredPlanToolSet() error {
 294 	names, err := s.offeredTools()
 295 	if err != nil {
 296 		return err
 297 	}
 344 }
 345 
 346 func (s *askModeE2EState) transcriptReportsMode(mode string) error {
 347 	res, err := http.Get(s.ts.URL + "/coddy/sessions/" + s.sid + "/messages")
 348 	if err != nil {
 349 		return err
 355 	}
 356 	if got := gjson.GetBytes(raw, "mode").String(); got != mode {
 357 		return fmt.Errorf("transcript mode = %q, want %q", got, mode)
 358 	}
 359 	if n := gjson.GetBytes(raw, "messages.#").Int(); n == 0 {
 360 		return fmt.Errorf("transcript is empty: %s", raw)
 361 	}
 362 	return nil
 363 }
 426 	sc.Step(`^the model was offered the plan tool set$`, s.offeredPlanToolSet)
 427 	sc.Step(`^the client received the answer over SSE with the file contents$`, s.answerOverSSEWithFileContents)
 428 	sc.Step(`^the transcript reports the session in "([^"]+)" mode$`, s.transcriptReportsMode)
 429 	sc.Step(`^the workspace file was not written$`, s.fileNotWritten)
 430 	sc.Step(`^the workspace file was written$`, s.fileWritten)
 431 	sc.Step(`^the stream carries a cancelled tool call with the ask-mode refusal$`, s.streamCarriesCancelledRefusal)
 444 		},
 445 	}
 446 	if suite.Run() != 0 {
 447 		t.Fatal("ask mode HTTP feature suite failed")
 448 	}
 449 }
```

[bdd_compaction_http_test.go](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_compaction_http_test.go)


```text
 110 	}
 111 	runner := func(ctx context.Context, st *session.State, prompt []acp.ContentBlock, snd acp.UpdateSender) (string, error) {
 112 		ag := agent.NewAgent(cfg, st, snd, slog.Default())
 113 		ag.SetProviderFactory(fakeFactory)
 114 		return ag.Run(ctx, prompt)
 115 	}
 116 	store := &session.FileStore{Root: sessRoot}
 117 	s.mgr = session.NewManager(cfg, noopSender{}, runner, slog.Default(), s.root, store)
 295 }
 296 
 297 // transcriptJSON fetches GET /coddy/sessions/{id}/messages as raw JSON.
 298 func (s *compactHTTPFeatureState) transcriptJSON() (string, error) {
 299 	req, err := http.NewRequest(http.MethodGet, s.ts.URL+"/coddy/sessions/"+s.sessionID+"/messages", nil)
 300 	if err != nil {
 301 		return "", err
 316 }
 317 
 318 func (s *compactHTTPFeatureState) transcriptHasSummaryRow() error {
 319 	raw, err := s.transcriptJSON()
 320 	if err != nil {
 321 		return err
 322 	}
 323 	if !strings.Contains(raw, `"compaction_summary":true`) {
 324 		return fmt.Errorf("transcript has no compaction summary row: %s", raw)
 325 	}
 326 	return nil
 327 }
 328 
 329 func (s *compactHTTPFeatureState) transcriptKeepsAllExchanges() error {
 330 	raw, err := s.transcriptJSON()
 331 	if err != nil {
 332 		return err
 333 	}
 335 		if !strings.Contains(raw, fmt.Sprintf("question %d", i)) ||
 336 			!strings.Contains(raw, fmt.Sprintf("answer %d", i)) {
 337 			return fmt.Errorf("transcript lost exchange %d", i)
 338 		}
 339 	}
 340 	return nil
 341 }
 342 
 343 func (s *compactHTTPFeatureState) transcriptShowsCompactCommand() error {
 344 	raw, err := s.transcriptJSON()
 345 	if err != nil {
 346 		return err
 347 	}
 348 	if !strings.Contains(raw, `"/compact"`) {
 349 		return fmt.Errorf("the /compact command is missing from the transcript")
 350 	}
 351 	return nil
 352 }
 424 	sc.Step(`^the compact request succeeds$`, s.compactRequestSucceeds)
 425 	sc.Step(`^the compact response reports the summary and message counts$`, s.compactResponseReportsSummaryAndCounts)
 426 	sc.Step(`^the session transcript contains a compaction summary row$`, s.transcriptHasSummaryRow)
 427 	sc.Step(`^the session transcript still contains all (\d+) original exchanges$`, func(int) error { return s.transcriptKeepsAllExchanges() })
 428 	sc.Step(`^the "/compact" command is part of the transcript$`, s.transcriptShowsCompactCommand)
 429 	sc.Step(`^the HTTP stream reports the smaller context usage$`, s.streamReportsSmallerContextUsage)
 430 	sc.Step(`^HTTP session stats match the compacted LLM context$`, s.statsMatchCompactedContext)
 431 }
 442 		},
 443 	}
 444 	if suite.Run() != 0 {
 445 		t.Fatal("context compaction command feature suite failed")
 446 	}
 447 }
```

候选基线direct_calls有185条，官方参考基线有626条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/execution.json)；[参考实际基线调用](gold-execution/af2db3aaa3d3aed0e730.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

### sylius/features/hybrid/checkout/placing_order_on_multi_channel/placing_an_order_on_a_single_channel_store.feature:20


主分类与兼类 `B`，证据状态 `CONFIRMED_GAP`。原实现 `passed`，杀死 260/402，存活 142。

```gherkin
    In order to be sure how much should I pay for my cart
    As an Administrator
    I want user to place orders in channel’s base currency
    Background:
        Given the store operates on a channel named "United States" in "USD" currency
        And the store ships to "United States"
        And the store has a zone "United States" with code "US"
        And this zone has the "United States" country member
        And the store has a product "PHP T-Shirt" priced at "$19.99"
        And the store ships everywhere for Free
        And the store allows paying Offline
        And there is an administrator "sylius@example.com" identified by "sylius"
        And there is a customer account "customer@example.com" identified by "sylius"
        And I am logged in as "customer@example.com"
    Scenario: Placing an order in a channels base currency
        Given I added product "PHP T-Shirt" to the cart
        And I addressed the cart
        When I proceed with "Free" shipping method and "Offline" payment
        And I confirm my order
        Then the administrator should see that order placed by "customer@example.com" has "USD" currency
```

候选和参考动态调用都记录 CompleteOrderHandler 到 CompositeStateMachine.apply，确认下单操作执行。候选读取 sharedStorage 内原 order 的email/currency；参考管理员登录后通过adminClient.show观察currencyCode。明确缺口位于需求指定的管理员读取边界。上一轮包含A的标签应撤回。142个存活中管理查询/序列化路径提供支持，其他变异仍保留未定。

#### 实际调用、状态读取与断言位置


[OrderContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/generated/src/Sylius/Behat/Context/Api/Checkout/OrderContext.php)


```text
  10 use Sylius\Behat\Context\Setup\Checkout\PaymentContext;
  11 use Sylius\Behat\Context\Setup\Checkout\ShippingContext;
  12 use Sylius\Behat\Service\SharedStorageInterface;
  13 use Sylius\Bundle\ApiBundle\Command\Checkout\CompleteOrder;
  14 use Sylius\Component\Core\Model\OrderInterface;
  15 use Sylius\Component\Core\Model\PaymentMethodInterface;
  16 use Sylius\Component\Core\Model\ShippingMethodInterface;
  23         private ShippingContext $shippingContext,
  24         private PaymentContext $paymentContext,
  25         private SharedStorageInterface $sharedStorage,
  26         private MessageBusInterface $commandBus,
  27     ) {
  28     }
  39     {
  40         /** @var OrderInterface $order */
  41         $order = $this->sharedStorage->get('order');
  42         $this->commandBus->dispatch(new CompleteOrder($order->getTokenValue()));
  43         $this->sharedStorage->set('placed_order', $order);
  44     }
  45 
  46     #[Then('the administrator should see that order placed by :email has :currency currency')]
  47     public function administratorShouldSeeOrderCurrency(string $email, string $currency): void
  48     {
  49         /** @var OrderInterface $order */
  50         $order = $this->sharedStorage->get('placed_order');
  51         Assert::same($order->getCustomer()->getEmail(), $email);
  52         Assert::same($order->getCurrencyCode(), $currency);
  53     }
  54 }
```

#### 开发者路径及执行证据


参考源码入口见 [Resources.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Resources.php)、[CheckoutShippingContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/Checkout/CheckoutShippingContext.php)、[CheckoutContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/CheckoutContext.php)、[OrderContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/OrderContext.php)。

[Resources.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Resources.php)


```text
  20     public const ADJUSTMENTS = 'adjustments';
  21 
  22     public const ADMINISTRATORS = 'administrators';
  23 
  24     public const AVATAR_IMAGE = 'avatar-image';
  25 
```

[CheckoutShippingContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/Checkout/CheckoutShippingContext.php)


```text
  20 use Sylius\Behat\Client\ApiClientInterface;
  21 use Sylius\Behat\Client\ResponseCheckerInterface;
  22 use Sylius\Behat\Service\SharedStorageInterface;
  23 use Sylius\Component\Core\Model\ShippingMethodInterface;
  24 use Sylius\Component\Core\OrderCheckoutStates;
  25 use Sylius\Component\Core\Repository\ShippingMethodRepositoryInterface;
  32         private ApiClientInterface $client,
  33         private ResponseCheckerInterface $responseChecker,
  34         private SharedStorageInterface $sharedStorage,
  35         private IriConverterInterface $iriConverter,
  36         private ShippingMethodRepositoryInterface $shippingMethodRepository,
  37     ) {
  49     public function iTryToSelectNonExistingShippingMethod(): void
  50     {
  51         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
  52         $content = $this->responseChecker->getResponseContent($response);
  53 
  54         $this->client->requestPatch(
  55             uri: sprintf(
  56                 'orders/%s/shipments/%s',
  57                 $this->sharedStorage->get('cart_token'),
  58                 $content['shipments'][0]['id'],
  59             ),
  60             body: ['shippingMethod' => '/api/v2/shop/shipping-methods/NON_EXISTING'],
  68         $shippingMethod = $this->shippingMethodRepository->findOneBy([]);
  69 
  70         $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
  71 
  72         $content = $this->responseChecker->getResponseContent($this->client->getLastResponse());
  73 
  75             uri: sprintf(
  76                 'orders/%s/shipments/%s',
  77                 $this->sharedStorage->get('cart_token'),
  78                 $content['shipments'][0]['id'],
  79             ),
  80             body: ['shippingMethod' => $this->iriConverter->getIriFromResource($shippingMethod)],
 106     public function iShouldSeeThatThereIsNoAssignedShippingMethod(): void
 107     {
 108         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 109 
 110         Assert::isEmpty($this->responseChecker->getValue($response, 'shipments'));
 111     }
 140                 sprintf(
 141                     'The shipping method %s is not available for this order. Please reselect your shipping method.',
 142                     $this->sharedStorage->get('shipping_method'),
 143                 ),
 144             ),
 145             sprintf(
 146                 'Expected to see message that shipping method "%s" is not available. Got message: "%s".',
 147                 $this->sharedStorage->get('shipping_method'),
 148                 $this->responseChecker->getError($this->client->getLastResponse()),
 149             ),
 150         );
 162     public function chooseShippingMethod(?ShippingMethodInterface $shippingMethod = null): void
 163     {
 164         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 165 
 166         // Lack of authorization
 167         if (!$this->responseChecker->isShowSuccessful($response)) {
 174             uri: sprintf(
 175                 'orders/%s/shipments/%s',
 176                 $this->sharedStorage->get('cart_token'),
 177                 $content['shipments'][0]['id'],
 178             ),
 179             body: ['shippingMethod' => $this->iriConverter->getIriFromResource(
 185     private function getCheckoutState(): string
 186     {
 187         $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 188 
 189         $response = $this->client->getLastResponse();
 190 
```

[CheckoutContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/CheckoutContext.php)


```text
  25 use Sylius\Behat\Service\Converter\IriConverterInterface;
  26 use Sylius\Behat\Service\Factory\AddressFactoryInterface;
  27 use Sylius\Behat\Service\SharedStorageInterface;
  28 use Sylius\Component\Addressing\Model\CountryInterface;
  29 use Sylius\Component\Addressing\Model\ProvinceInterface;
  30 use Sylius\Component\Core\Formatter\StringInflector;
  69         private readonly ProductVariantResolverInterface $productVariantResolver,
  70         private readonly IriConverterInterface $iriConverter,
  71         private readonly SharedStorageInterface $sharedStorage,
  72         private readonly RequestFactoryInterface $requestFactory,
  73         private readonly AddressFactoryInterface $addressFactory,
  74         private readonly string $shippingMethodClass,
  93     public function iTryToCompleteTheShippingStep(): void
  94     {
  95         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
  96         $content = $this->responseChecker->getResponseContent($response);
  97 
  98         $this->client->requestPatch(
  99             uri: sprintf(
 100                 'orders/%s/shipments/%s',
 101                 $this->sharedStorage->get('cart_token'),
 102                 $content['shipments'][0]['id'],
 103             ),
 104             body: ['shippingMethod' => $content['shipments'][0]['method']],
 116     public function iTryToCompleteTheShippingStepWithShippingMethod(ShippingMethodInterface $shippingMethod): void
 117     {
 118         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 119         $content = $this->responseChecker->getResponseContent($response);
 120 
 121         $this->sharedStorage->set('shipping_method', $shippingMethod);
 122 
 123         $this->client->requestPatch(
 124             uri: sprintf(
 125                 'orders/%s/shipments/%s',
 126                 $this->sharedStorage->get('cart_token'),
 127                 $content['shipments'][0]['id'],
 128             ),
 129             body: ['shippingMethod' => $this->iriConverter->getIriFromResource($shippingMethod)],
 162     public function iShouldSeeThatThereIsNoShipmentAssigned(): void
 163     {
 164         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 165 
 166         Assert::isEmpty($this->responseChecker->getValue($response, 'shipments'));
 167     }
 170     public function iShouldSeeThatNoPaymentMethodIsAssigned(): void
 171     {
 172         $response = $this->client->requestGet(sprintf('orders/%s', $this->sharedStorage->get('cart_token')));
 173 
 174         Assert::isEmpty($this->responseChecker->getValue($response, 'payments'));
 175     }
 356         $this->content['additionalNote'] = $notes;
 357 
 358         $this->sharedStorage->set('additional_note', $notes);
 359     }
 360 
 361     #[When('I want to complete checkout')]
 362     public function iWantToCompleteCheckout(): void
 363     {
 364         $response = $this->completeOrder();
 365 
 366         Assert::notSame($response->getStatusCode(), 200);
 367 
 368         $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token'));
 369     }
 370 
 371     #[When('I confirm my order')]
 375     public function iConfirmMyOrder(): void
 376     {
 377         $response = $this->completeOrder();
 378 
 379         if ($response->getStatusCode() > 299) {
 380             return;
 381         }
 382 
 383         $this->sharedStorage->set('response', $response);
 384         $this->sharedStorage->set(
 385             'order_number',
 386             $this->responseChecker->getValue($response, 'number'),
 387         );
 388         $this->sharedStorage->set('order', $this->orderRepository->findOneByNumber($this->sharedStorage->get('order_number')));
 389     }
 390 
 391     #[Given('I have tried to confirm my order')]
 393     public function iTryToConfirmMyOrder(): void
 394     {
 395         $response = $this->completeOrder();
 396 
 397         $this->sharedStorage->set('response', $response);
 398     }
 399 
 400     #[When('I decide to change shipping method')]
 411             'shop',
 412             Resources::ORDERS,
 413             $this->sharedStorage->get('cart_token'),
 414             HTTPRequest::METHOD_PATCH,
 415             sprintf('shipments/%s', $this->getCart()['shipments'][0]['id']),
 416         );
 432             'shop',
 433             Resources::ORDERS,
 434             $this->sharedStorage->get('cart_token'),
 435             HTTPRequest::METHOD_PATCH,
 436             sprintf('payments/%s', $cart['payments'][0]['id']),
 437         );
 489             'shop',
 490             Resources::ORDERS,
 491             $this->sharedStorage->get('cart_token'),
 492             HTTPRequest::METHOD_PATCH,
 493             \sprintf('payments/%s', $this->getCart()['payments'][0]['id']),
 494         );
 859     public function myTotalDiscountShouldBe(int $discount = 0): void
 860     {
 861         if ($this->sharedStorage->has('cart_token')) {
 862             $discountTotal = $this->responseChecker->getValue(
 863                 $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token')),
 864                 'orderPromotionTotal',
 865             );
 866 
 876     public function myDiscountShouldBe(int $discount): void
 877     {
 878         if ($this->sharedStorage->has('cart_token')) {
 879             $discountTotal = $this->responseChecker->getValue(
 880                 $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token')),
 881                 'orderAndItemPromotionTotal',
 882             );
 883 
 893     public function thereShouldBeNoTaxesCharged(): void
 894     {
 895         $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token'));
 896 
 897         Assert::same($this->responseChecker->getValue($this->client->getLastResponse(), 'taxTotal'), 0);
 898     }
1029     public function iTryToAddProductToCart(ProductInterface $product): void
1030     {
1031         $this->putProductToCart($product, $this->sharedStorage->get('cart_token'));
1032     }
1033 
1034     #[When('/^I try to add ("([^"]+)" product variant)$/')]
1062         ]);
1063 
1064         $this->sharedStorage->set('response', $this->client->executeCustomRequest($request));
1065     }
1066 
1067     #[When('/^I try to remove (product "[^"]+") from the cart$/')]
1068     public function iTryToRemoveProductFromTheCart(ProductInterface $product): void
1069     {
1070         $this->removeOrderItemFromCart($product->getId(), $this->sharedStorage->get('cart_token'));
1071     }
1072 
1073     #[When('/^I try to change quantity to (\d+) of (product "[^"]+") from the (cart)$/')]
1210     private function getCartTokenValue(): ?string
1211     {
1212         if ($this->sharedStorage->has('cart_token')) {
1213             return $this->sharedStorage->get('cart_token');
1214         }
1215 
1216         if ($this->sharedStorage->has('previous_cart_token')) {
1217             return $this->sharedStorage->get('previous_cart_token');
1218         }
1219 
1220         return null;
1223     private function getCheckoutState(): string
1224     {
1225         $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token'));
1226 
1227         $response = $this->client->getLastResponse();
1228 
1268     {
1269         /** @var OrderInterface|null $order */
1270         $order = $this->orderRepository->findCartByTokenValue($this->sharedStorage->get('cart_token'));
1271         Assert::notNull($order);
1272 
1273         if (!$order->getLastPayment()) {
1325     {
1326         try {
1327             $email = $this->sharedStorage->get('created_as_guest') ? 'rich@sylius.com' : null;
1328         } catch (\InvalidArgumentException) {
1329             $email = null;
1330         }
1403         ]);
1404 
1405         $this->sharedStorage->set('response', $this->client->executeCustomRequest($request));
1406     }
1407 
1408     private function removeOrderItemFromCart(int $orderItemId, ?string $tokenValue): void
1416         );
1417 
1418         $this->sharedStorage->set('response', $this->client->executeCustomRequest($request));
1419     }
1420 
1421     private function getAddressByFieldValue(array $addressBook, string $fieldName, string $fieldValue): array
1453     private function addressShouldBeFilledAs(AddressInterface $address, string $addressType): void
1454     {
1455         $response = $this->client->show(Resources::ORDERS, $this->sharedStorage->get('cart_token'));
1456 
1457         $addressFromResponse = $this->responseChecker->getValue($response, $addressType . 'Address');
1458 
1460     }
1461 
1462     private function completeOrder(): Response
1463     {
1464         $notes = $this->content['additionalNote'] ?? null;
1465 
1467             'shop',
1468             Resources::ORDERS,
1469             $this->sharedStorage->get('cart_token'),
1470             HTTPRequest::METHOD_PATCH,
1471             'complete',
1472         );
1481             'shop',
1482             Resources::ORDERS,
1483             $this->sharedStorage->get('cart_token'),
1484             HTTPRequest::METHOD_PATCH,
1485             sprintf('shipments/%s', $this->getCart()['shipments'][0]['id']),
1486         );
```

[OrderContext.php](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/OrderContext.php)


```text
  23 use Sylius\Behat\Context\Api\Resources;
  24 use Sylius\Behat\Service\SecurityServiceInterface;
  25 use Sylius\Behat\Service\SharedStorageInterface;
  26 use Sylius\Component\Addressing\Model\CountryInterface;
  27 use Sylius\Component\Core\Formatter\StringInflector;
  28 use Sylius\Component\Core\Model\AdminUserInterface;
  41     public function __construct(
  42         private ApiClientInterface $shopClient,
  43         private ApiClientInterface $adminClient,
  44         private ResponseCheckerInterface $responseChecker,
  45         private SharedStorageInterface $sharedStorage,
  46         private IriConverterInterface $iriConverter,
  47         private SecurityServiceInterface $securityService,
  48         private RequestFactoryInterface $requestFactory,
  56     {
  57         /** @var OrderInterface $order */
  58         $order = $this->sharedStorage->get('order');
  59 
  60         $request = $this->requestFactory->custom(
  61             sprintf(
  79         $this->shopClient->show(Resources::ORDERS, $order->getTokenValue());
  80 
  81         $this->sharedStorage->set('order', $order);
  82         $this->sharedStorage->set('cart_token', $order->getTokenValue());
  83     }
  84 
  85     #[When('I try to see the order placed by a customer :customer')]
  87     {
  88         /** @var OrderInterface $order */
  89         $order = $this->sharedStorage->get('order');
  90         Assert::eq($order->getCustomer(), $customer);
  91 
  92         $this->iViewTheSummaryOfMyOrder($order);
  96     public function iShouldBeAbleToAccessThisOrderDetails(): void
  97     {
  98         $response = $this->shopClient->show(Resources::ORDERS, $this->sharedStorage->get('cart_token'));
  99 
 100         Assert::same($response->getStatusCode(), Response::HTTP_OK);
 101         Assert::same(
 104         );
 105         Assert::same(
 106             $this->sharedStorage->get('order_number'),
 107             $this->responseChecker->getValue($this->shopClient->getLastResponse(), 'number'),
 108         );
 109     }
 232     {
 233         $discount = 0;
 234         $itemId = $this->geOrderItemIdForProductInCart($product, $this->sharedStorage->get('cart_token'));
 235         $adjustments = $this->getAdjustmentsForOrderItem($itemId);
 236         foreach ($adjustments as $adjustment) {
 237             $discount += $adjustment['amount'];
 258         $payment = $this
 259             ->responseChecker
 260             ->getValue($this->shopClient->show(Resources::ORDERS, $this->sharedStorage->get('cart_token')), 'payments')[0]
 261         ;
 262 
 263         Assert::same($this->iriConverter->getIriFromResource($paymentMethod), $payment['method']);
 287     }
 288 
 289     #[Then('/^(the administrator) should know about (this additional note) for (this order made by "[^"]+")$/')]
 290     public function theCustomerServiceShouldKnowAboutThisAdditionalNotes(
 291         AdminUserInterface $user,
 292         string $notes,
 297         Assert::same(
 298             $notes,
 299             $this->responseChecker->getValue($this->adminClient->show(Resources::ORDERS, $order->getTokenValue()), 'notes'),
 300         );
 301     }
 302 
 303     #[Then('/^(the administrator) should see that (order placed by "[^"]+") has "([^"]+)" currency$/')]
 304     public function theAdministratorShouldSeeThatThisOrderHasBeenPlacedIn(
 305         AdminUserInterface $user,
 306         OrderInterface $order,
 307         string $currency,
 308     ): void {
 309         $this->securityService->logIn($user);
 310 
 311         Assert::same(
 312             $currency,
 313             $this->responseChecker->getValue($this->adminClient->show(Resources::ORDERS, $order->getTokenValue()), 'currencyCode'),
 314         );
 315     }
 316 
 317     private function getAdjustmentsForOrder(): array
 318     {
 319         $response = $this->shopClient->subResourceIndex(Resources::ORDERS, 'adjustments', $this->sharedStorage->get('cart_token'));
 320 
 321         return $this->responseChecker->getCollection($response);
 322     }
 325     {
 326         $response = $this->shopClient->customAction(
 327             sprintf('%s/shop/orders/%s/items/%s/adjustments', $this->apiUrlPrefix, $this->sharedStorage->get('cart_token'), $itemId),
 328             HttpRequest::METHOD_GET,
 329         );
 330 
 379     private function hasCorrectAmountsDistributedOnAdjustments(array $amounts, ProductInterface $product): bool
 380     {
 381         $itemId = $this->geOrderItemIdForProductInCart($product, $this->sharedStorage->get('cart_token'));
 382         $adjustments = $this->getAdjustmentsForOrderItem($itemId);
 383 
 384         /** @var int $index */
```

候选基线direct_calls有1486条，官方参考基线有1942条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/execution.json)；[参考实际基线调用](gold-execution/7627df83491b90a0f0fa.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

### kapua/service/account/test/src/test/resources/features/AccountService.feature:120


主分类与兼类 `C`，证据状态 `CONFIRMED_GAP`。原实现 `passed`，杀死 22/43，存活 21。

```gherkin
  The User Account Service is responsible for CRUD operations for user accounts in the Kapua
  database.
  Scenario: Delete nonexisting account
  Try to delete an account with a a random Id. The operation should fail and an exception
  should be thrown.

    Given I expect the exception "KapuaEntityNotFoundException" with the text "The entity of type account with id/name"
    When I delete a random account
    Then An exception was thrown
```

动态记录确认真实AccountServiceImpl.delete执行。候选以随机scope和随机ID删除，捕获任意KapuaException并只断言ExceptionCaught。需求明确规定KapuaEntityNotFoundException和消息片段，参考primeException/verifyException检查具体异常。消息格式返回null的变异存活。record_count_anomaly=true保留，按唯一变异ID核对，不清洗掉异常。

#### 实际调用、状态读取与断言位置


[DeleteNonexistingAccountSteps.java](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/generated/service/account/test/src/test/java/org/eclipse/kapua/service/account/test/r2t/generated/DeleteNonexistingAccountSteps.java)


```text
   3 import javax.inject.Inject;
   4 
   5 import org.eclipse.kapua.KapuaException;
   6 import org.eclipse.kapua.commons.model.id.IdGenerator;
   7 import org.eclipse.kapua.commons.model.id.KapuaEid;
   8 import org.eclipse.kapua.locator.KapuaLocator;
  13 
  14 public class DeleteNonexistingAccountSteps {
  15     private static final String EXCEPTION_CAUGHT = "ExceptionCaught";
  16 
  17     private final StepData stepData;
  18 
  23 
  24     @When("I delete a random account")
  25     public void deleteRandomAccount() {
  26         try {
  27             KapuaLocator.getInstance().getService(AccountService.class)
  28                     .delete(new KapuaEid(IdGenerator.generate()), new KapuaEid(IdGenerator.generate()));
  29         } catch (KapuaException e) {
  30             stepData.put(EXCEPTION_CAUGHT, true);
  31             return;
  32         }
```

#### 开发者路径及执行证据


参考源码入口见 [AccountServiceSteps.java](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/reference/service/account/test-steps/src/main/java/org/eclipse/kapua/service/account/steps/AccountServiceSteps.java)。

[AccountServiceSteps.java](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/reference/service/account/test-steps/src/main/java/org/eclipse/kapua/service/account/steps/AccountServiceSteps.java)


```text
  27 
  28 import org.eclipse.kapua.KapuaEntityNotFoundException;
  29 import org.eclipse.kapua.KapuaException;
  30 import org.eclipse.kapua.KapuaIllegalNullArgumentException;
  31 import org.eclipse.kapua.commons.model.id.IdGenerator;
  32 import org.eclipse.kapua.commons.model.id.KapuaEid;
 140         stepData.remove(LAST_ACCOUNT_ID);
 141         try {
 142             primeException();
 143             Account account = accountService.create(accountCreator);
 144             stepData.put(LAST_ACCOUNT, account);
 145             stepData.put(LAST_ACCOUNT_ID, account.getId());
 146         } catch (KapuaException ex) {
 147             verifyException(ex);
 148         }
 149     }
 150 
 156         stepData.remove(LAST_ACCOUNT_ID);
 157         try {
 158             primeException();
 159             Account account = accountService.create(accountCreator);
 160             stepData.put(LAST_ACCOUNT, account);
 161             stepData.put(LAST_ACCOUNT_ID, account.getId());
 162         } catch (KapuaException ex) {
 163             verifyException(ex);
 164         }
 165     }
 166 
 170             AccountCreator accountCreator = prepareRegularAccountCreator(getCurrentScopeId(), "account" + i);
 171             try {
 172                 primeException();
 173                 Account account = accountService.create(accountCreator);
 174             } catch (KapuaException ex) {
 175                 verifyException(ex);
 176             }
 177         }
 178     }
 187         stepData.remove(LAST_ACCOUNT_ID);
 188         try {
 189             primeException();
 190             Account account = accountService.create(accountCreator);
 191             stepData.put(LAST_ACCOUNT, account);
 192             stepData.put(LAST_ACCOUNT_ID, account.getId());
 193         } catch (KapuaException ex) {
 194             verifyException(ex);
 195         }
 196     }
 197 
 201             AccountCreator accountCreator = prepareRegularAccountCreator(new KapuaEid(BigInteger.valueOf(parentId)), TMP_ACC + String.format("%d", i));
 202             try {
 203                 primeException();
 204                 accountService.create(accountCreator);
 205             } catch (KapuaException ex) {
 206                 verifyException(ex);
 207                 break;
 208             }
 209         }
 216             AccountCreator accountCreator = prepareRegularAccountCreator(tmpAcc.getId(), TMP_ACC + String.format("%d", i));
 217             try {
 218                 primeException();
 219                 accountService.create(accountCreator);
 220             } catch (KapuaException ex) {
 221                 verifyException(ex);
 222                 break;
 223             }
 224         }
 233             accountCreator.setExpirationDate(expirationDate);
 234             try {
 235                 primeException();
 236                 accountService.create(accountCreator);
 237             } catch (KapuaException ex) {
 238                 verifyException(ex);
 239                 break;
 240             }
 241         }
 248             accountCreator.setOrganizationName(name);
 249             try {
 250                 primeException();
 251                 accountService.create(accountCreator);
 252             } catch (KapuaException ex) {
 253                 verifyException(ex);
 254                 break;
 255             }
 256         }
 261         AccountCreator accountCreator = prepareRegularAccountCreator(SYS_SCOPE_ID, null);
 262         try {
 263             primeException();
 264             accountService.create(accountCreator);
 265         } catch (KapuaIllegalNullArgumentException ex) {
 266             verifyException(ex);
 267         }
 268     }
 269 
 271     public void changeAccountDetails(String name) throws Exception {
 272         try {
 273             primeException();
 274 
 275             Account account = accountService.findByName(name);
 276             Organization tmpOrg = account.getOrganization();
 283 
 284             accountService.update(account);
 285         } catch (KapuaException ex) {
 286             verifyException(ex);
 287         }
 288     }
 289 
 293 
 294         try {
 295             primeException();
 296             accountService.update(account);
 297         } catch (KapuaEntityNotFoundException ex) {
 298             verifyException(ex);
 299         }
 300     }
 301 
 311         tmpAcc.setExpirationDate(expirationDate);
 312         try {
 313             primeException();
 314             accountService.update(tmpAcc);
 315         } catch (KapuaException ex) {
 316             verifyException(ex);
 317         }
 318     }
 319 
 324 
 325         try {
 326             primeException();
 327             accountService.update(tmpAcc);
 328         } catch (KapuaException ex) {
 329             verifyException(ex);
 330         }
 331     }
 332 
 338 
 339         try {
 340             primeException();
 341             accountService.update(tmpAcc);
 342         } catch (KapuaException ex) {
 343             verifyException(ex);
 344         }
 345     }
 346 
 356                 stepData.remove(LAST_ACCOUNT);
 357             }
 358         } catch (KapuaException e) {
 359             verifyException(e);
 360         }
 361     }
 362 
 367 
 368         try {
 369             primeException();
 370             currAcc.setExpirationDate(newDate);
 371             Account tmpAcc = accountService.update(currAcc);
 372             stepData.put(LAST_ACCOUNT, tmpAcc);
 373         } catch (KapuaException e) {
 374             verifyException(e);
 375         }
 376     }
 377 
 379     public void deleteAccountWithName(String name) throws Exception {
 380         try {
 381             primeException();
 382             Account tmpAcc = accountService.findByName(name);
 383             accountService.delete(tmpAcc.getScopeId(), tmpAcc.getId());
 384         } catch (KapuaException ex) {
 385             verifyException(ex);
 386         }
 387     }
 388 
 396 
 397         try {
 398             primeException();
 399             accountService.delete(KapuaId.ANY, adminAccount.getId());
 400         } catch (KapuaException ex) {
 401             verifyException(ex);
 402         }
 403     }
 404 
 405     @When("I delete a random account")
 406     public void deleteRandomAccount() throws Exception {
 407         try {
 408             primeException();
 409             accountService.delete(SYS_SCOPE_ID, new KapuaEid(IdGenerator.generate()));
 410         } catch (KapuaException ex) {
 411             verifyException(ex);
 412         }
 413     }
 414 
 416     public void findAccountByName(String name) throws Exception {
 417         try {
 418             primeException();
 419             stepData.remove(LAST_ACCOUNT);
 420             Account account = accountService.findByName(name);
 421             stepData.put(LAST_ACCOUNT, account);
 422         } catch (KapuaException ex) {
 423             verifyException(ex);
 424         }
 425     }
 426 
 428     public void findAccountByStoredId() throws Exception {
 429         try {
 430             primeException();
 431             stepData.remove(LAST_ACCOUNT);
 432             KapuaId accountId = (KapuaId) stepData.get(LAST_ACCOUNT_ID);
 433             Account account = accountService.find(accountId);
 434             stepData.put(LAST_ACCOUNT, account);
 435         } catch (KapuaException ex) {
 436             verifyException(ex);
 437         }
 438     }
 439 
 441     public void findAccountByStoredScopeAndAccountIds() throws Exception {
 442         try {
 443             primeException();
 444             stepData.remove(LAST_ACCOUNT);
 445             KapuaId accountId = (KapuaId) stepData.get(LAST_ACCOUNT_ID);
 446             Account account = accountService.find(SYS_SCOPE_ID, accountId);
 447             stepData.put(LAST_ACCOUNT, account);
 448         } catch (KapuaException ex) {
 449             verifyException(ex);
 450         }
 451     }
 452 
 454     public void findRandomAccountId() throws Exception {
 455         try {
 456             primeException();
 457             stepData.remove(LAST_ACCOUNT);
 458             Account account = accountService.find(SYS_SCOPE_ID, new KapuaEid(IdGenerator.generate()));
 459             stepData.put(LAST_ACCOUNT, account);
 460         } catch (KapuaException ex) {
 461             verifyException(ex);
 462         }
 463     }
 464 
 475 
 476         try {
 477             primeException();
 478             account = accountService.update(account);
 479             stepData.put(LAST_ACCOUNT, account);
 480         } catch (KapuaException ex) {
 481             verifyException(ex);
 482         }
 483     }
 484 
 502 
 503         try {
 504             primeException();
 505             accountService.setConfigValues(account.getId(), account.getScopeId(), valueMap);
 506         } catch (KapuaException ex) {
 507             verifyException(ex);
 508         }
 509     }
 510 
 513         Account account = (Account) stepData.get(LAST_ACCOUNT);
 514         try {
 515             primeException();
 516             Map<String, Object> valuesRead = accountService.getConfigValues(account.getId());
 517             valuesRead.put(name, value);
 518             accountService.setConfigValues(account.getId(), account.getScopeId(), valuesRead);
 519         } catch (KapuaException ex) {
 520             verifyException(ex);
 521         }
 522     }
 523 
 527         stepData.remove(INT_VALUE);
 528         try {
 529             primeException();
 530             AccountListResult accList = accountService.query(query);
 531             stepData.put(INT_VALUE, accList.getSize());
 532         } catch (KapuaException ex) {
 533             verifyException(ex);
 534         }
 535     }
 536 
 540         stepData.remove(LAST_ACCOUNT);
 541         try {
 542             primeException();
 543             Date expirationDate = new SimpleDateFormat(DATE_FORMAT).parse(expirationDateStr);
 544             account.setExpirationDate(expirationDate);
 545             account = accountService.update(account);
 546             stepData.put(LAST_ACCOUNT, account);
 547         } catch (KapuaException | ParseException ex) {
 548             verifyException(ex);
 549         }
 550     }
 551 
 578 
 579     @Then("Account {string} exists")
 580     public void checkWhetherAccountExists(String name) throws KapuaException {
 581         Account tmpAcc = accountService.findByName(name);
 582         Assert.assertNotNull(tmpAcc);
 583     }
 584 
 585     @Then("Account {string} is correctly modified")
 586     public void checkForAccountModifications(String name) throws KapuaException {
 587         Account account = (Account) stepData.get(LAST_ACCOUNT);
 588         Account tmpAcc = accountService.findByName(name);
 589 
 593 
 594     @Then("The account with name {string} has {int} subaccount(s)")
 595     public void checkNumberOfAccounts(String accountName, int num) throws KapuaException {
 596         KapuaQuery query = accountFactory.newQuery(getCurrentScopeId());
 597         Account account = accountService.find(getCurrentScopeId());
 598         Assert.assertEquals(accountName, account.getName());
 605     public void checkNumberOfChildrenForNamedAccount(String name, int num) throws Exception {
 606         try {
 607             primeException();
 608             Account tmpAcc = accountService.findByName(name);
 609             KapuaQuery query = accountFactory.newQuery(tmpAcc.getId());
 610             long accountCnt = accountService.count(query);
 611 
 612             Assert.assertEquals(num, accountCnt);
 613         } catch (KapuaException ke) {
 614             verifyException(ke);
 615         }
 616     }
 617 
 623 
 624     @Then("The System account exists")
 625     public void findSystemAccount() throws KapuaException {
 626         String adminUserName = SystemSetting.getInstance().getString(SystemSettingKey.SYS_ADMIN_USERNAME);
 627         Account tmpAcc = accountService.findByName(adminUserName);
 628         Assert.assertNotNull(tmpAcc);
 630 
 631     @Then("The account has the following parameters")
 632     public void checkAccountParameters(DataTable dataTable) throws KapuaException {
 633         Assert.assertEquals("Wrong test setup. Bad parameters size!", 2, dataTable.width());
 634         Account account = (Account) stepData.get(LAST_ACCOUNT);
 635         Properties accProps = account.getEntityProperties();
 641 
 642     @Then("The account has metadata")
 643     public void checkMetadataExistence() throws KapuaException {
 644         KapuaId accountId = (KapuaId) stepData.get(LAST_ACCOUNT_ID);
 645         KapuaTocd metaData = accountService.getConfigMetadata(accountId);
 646         Assert.assertNotNull(metaData);
 648 
 649     @Then("The default configuration for the account is set")
 650     public void checkDefaultAccountConfiguration() throws KapuaException {
 651         Account account = (Account) stepData.get(LAST_ACCOUNT);
 652         Map<String, Object> valuesRead = accountService.getConfigValues(account.getId());
 653         Assert.assertTrue(valuesRead.containsKey("maxNumberChildEntities"));
 656 
 657     @Then("The config item {string} is set to {string}")
 658     public void checkConfigValue(String name, String value) throws KapuaException {
 659         Account account = (Account) stepData.get(LAST_ACCOUNT);
 660         Map<String, Object> valuesRead = accountService.getConfigValues(account.getId());
 661         Assert.assertTrue(valuesRead.containsKey(name));
 664 
 665     @Then("The config item {string} is missing")
 666     public void checkMissingConfigItem(String name) throws KapuaException {
 667         Account account = (Account) stepData.get(LAST_ACCOUNT);
 668         Map<String, Object> valuesRead = accountService.getConfigValues(account.getId());
 669         Assert.assertFalse(valuesRead.containsKey(name));
 686         }
 687 
 688         primeException();
 689         try {
 690             Account tmpAccount = (Account) stepData.get(LAST_ACCOUNT);
 691             if (tmpAccount != null) {
 697             }
 698             accountService.setConfigValues(accId, scopeId, valueMap);
 699         } catch (KapuaException ex) {
 700             verifyException(ex);
 701         }
 702     }
 703 
 744         List<Account> accountList = new ArrayList<>();
 745         KapuaSecurityUtils.doPrivileged(() -> {
 746             primeException();
 747             try {
 748                 Account account = accountService.create(accountCreatorCreator(cucAccount.getName(),
 749                         cucAccount.getScopeId(), cucAccount.getExpirationDate()));
 750                 accountList.add(account);
 751             } catch (KapuaException ke) {
 752                 verifyException(ke);
 753             }
 754 
 755             return null;
 796 
 797         try {
 798             primeException();
 799             accountService.update(account);
 800         } catch (KapuaException ex) {
 801             verifyException(ex);
 802         }
 803     }
 804 
 811 
 812         try {
 813             primeException();
 814             stepData.remove(LAST_ACCOUNT);
 815             stepData.remove(LAST_ACCOUNT);
 816             Account account = accountService.create(accountCreator);
 817             stepData.put(LAST_ACCOUNT, account);
 818             stepData.put(LAST_ACCOUNT, account);
 819         } catch (KapuaException ex) {
 820             verifyException(ex);
 821         }
 822     }
 823 
 858 
 859         try {
 860             primeException();
 861             stepData.remove(LAST_ACCOUNT);
 862             Account account = accountService.create(accountCreator);
 863             stepData.put(LAST_ACCOUNT, account);
 864         } catch (KapuaException ex) {
 865             verifyException(ex);
 866         }
 867     }
 868 
 872         AccountQuery query = accountFactory.newQuery(tmpAccount.getId());
 873         try {
 874             primeException();
 875             AccountListResult accList = accountService.query(query);
 876             stepData.put("NumberOfFoundAccounts", accList.getSize());
 877         } catch (KapuaException ex) {
 878             verifyException(ex);
 879         }
 880     }
 881 
```

候选基线direct_calls有337条，官方参考基线有339条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/execution.json)；[参考实际基线调用](gold-execution/93eac4b8da28527c6348.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/93eac4b8da28527c6348/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

### python-docx/features/doc-add-section.feature:16


主分类与兼类 `A_setup`，证据状态 `CONFIRMED_GAP`。原实现 `passed`，杀死 112/113，存活 1。

```gherkin
  In order to change page layout mid-document
  As a developer using python-docx
  I need a way to add a new section to a document
  Scenario: Document.add_section() adds a section that inherits headers and footers
    Given a single-section Document object with headers and footers as document
     When I execute section = document.add_section()
     Then section.header.is_linked_to_previous is True
      And section.even_page_header.is_linked_to_previous is True
      And section.first_page_header.is_linked_to_previous is True
      And section.footer.is_linked_to_previous is True
      And section.even_page_footer.is_linked_to_previous is True
      And section.first_page_footer.is_linked_to_previous is True
```

候选真实调用Document.add_section；六个linked=True断言也存在。Given只getattr六种header/footer代理，没有建立实际定义。参考载入带定义的文档。删除sentinel_sectPr.remove(hdrftr_ref)后候选通过、参考杀死，参考基线覆盖69行，候选基线未覆盖该行。缺口位于必要前置状态；修正上一轮C标签。

#### 实际调用、状态读取与断言位置


[doc_add_section.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/generated/features/steps/doc_add_section.py)


```text
  21         "first_page_footer",
  22     ):
  23         getattr(original_section, name)
  24 
  25     context.document = document
  26 
  27 
  28 @when("I execute section = document.add_section()")
  29 def when_add_section(context):
  30     context.section = context.document.add_section()
  31 
  32 
  33 @then("section.header.is_linked_to_previous is True")
  34 def then_header_linked_to_previous(context):
  35     assert context.section.header.is_linked_to_previous is True
  36 
  37 
  38 @then("section.even_page_header.is_linked_to_previous is True")
  39 def then_even_page_header_linked_to_previous(context):
  40     assert context.section.even_page_header.is_linked_to_previous is True
  41 
  42 
  43 @then("section.first_page_header.is_linked_to_previous is True")
  44 def then_first_page_header_linked_to_previous(context):
  45     assert context.section.first_page_header.is_linked_to_previous is True
  46 
  47 
  48 @then("section.footer.is_linked_to_previous is True")
  49 def then_footer_linked_to_previous(context):
  50     assert context.section.footer.is_linked_to_previous is True
  51 
  52 
  53 @then("section.even_page_footer.is_linked_to_previous is True")
  54 def then_even_page_footer_linked_to_previous(context):
  55     assert context.section.even_page_footer.is_linked_to_previous is True
  56 
  57 
  58 @then("section.first_page_footer.is_linked_to_previous is True")
  59 def then_first_page_footer_linked_to_previous(context):
  60     assert context.section.first_page_footer.is_linked_to_previous is True
```

#### 开发者路径及执行证据


参考源码入口见 [document.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/document.py)、[helpers.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/helpers.py)、[section.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/section.py)。

[document.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/document.py)


```text
  48 
  49 @given("a single-section document having portrait layout")
  50 def given_a_single_section_document_having_portrait_layout(context):
  51     context.document = Document(test_docx("doc-add-section"))
  52     section = context.document.sections[-1]
  53     context.original_dimensions = (section.page_width, section.page_height)
  54 
  55 
  56 @given("a single-section Document object with headers and footers as document")
  57 def given_a_single_section_Document_object_with_headers_and_footers(context):
  58     context.document = Document(test_docx("doc-add-section"))
  59 
  60 
  61 # when ====================================================
 144 @when("I add an even-page section to the document")
 145 def when_I_add_an_even_page_section_to_the_document(context):
 146     context.section = context.document.add_section(WD_SECTION.EVEN_PAGE)
 147 
 148 
 149 @when("I change the new section layout to landscape")
 156 
 157 
 158 @when("I execute section = document.add_section()")
 159 def when_I_execute_section_eq_document_add_section(context):
 160     context.section = context.document.add_section()
 161 
 162 
 163 # then ====================================================
```

[helpers.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/helpers.py)


```text

```

[section.py](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/section.py)


```text
 209 
 210 
 211 @then("section.{propname}.is_linked_to_previous is True")
 212 def then_section_hdrftr_prop_is_linked_to_previous_is_True(context: Context, propname: str):
 213     actual = getattr(context.section, propname).is_linked_to_previous
 214     expected = True
 215     assert actual == expected, "section.%s.is_linked_to_previous is %s" % (
 216         propname,
 217         actual,
 218     )
 231     }[margin_side]
 232     expected_value = Inches(float(inches))
 233     actual_value = getattr(context.section, prop_name)
 234     assert actual_value == expected_value
 235 
 236 
```

候选基线direct_calls有194条，官方参考基线有178条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/execution.json)；[参考实际基线调用](gold-execution/676d56c1c72dc4237805.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/676d56c1c72dc4237805/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

### e-petitions/features/charlie_creates_a_petition.feature:6


主分类与兼类 `C`，证据状态 `GAP_CONFIRMED_CAUSE_UNRESOLVED`。原实现 `passed`，杀死 172/183，存活 11。

```gherkin
  In order to have an issue discussed in parliament
  I want to be able to create a petition and verify my email address.
Scenario: Charlie has to search for a petition before creating one
  Given the following petitions exist:
    | action                         | state    | signature_count | open_at    |
    | Rioters should loose benefits  | open     |             835 | 2011-08-11 |
    | Rioters must loose benefits    | rejected |               5 |            |
    | Do not remove rioters benefits | open     |            1023 | 2011-08-21 |
  And I am on the home page
  When I follow "Start a petition" within ".//main"
  Then I should see "Start a petition"
  When I follow "Start your petition"
  Then I should be asked to confirm my eligibility
  When I confirm that I am UK citizen or resident
  Then I should see "Petition title"
  When I fill in "Petition title" with "Rioters benefits"
  And I press "Continue"
  Then I should see the following similar petitions:
    | Do not remove rioters benefits | Total signatures 1,023 |
    | Rioters should loose benefits  | Total signatures 835   |
  When I press "Continue with my petition"
  Then I should see "Say what you want the UK Government or Parliament to do"
```

真实网页创建和相似请愿搜索被执行。候选在全页分别检查标题与签名数；参考在带索引petition-item-existing内绑定同一行。需求表的对象—值对应关系未验证。11个存活没有足够证据归因于这一缺口，保留因果未定。

#### 实际调用、状态读取与断言位置


[charlie_creates_a_petition_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/generated/features/step_definitions/charlie_creates_a_petition_steps.rb)


```text
  20 
  21 Then(/^I should see "([^"]*)"$/) do |text|
  22   expect(page).to have_content(text)
  23 end
  24 
  25 When(/^I fill in "([^"]*)" with "([^"]*)"$/) do |field, value|
  32 
  33 Then("I should be asked to confirm my eligibility") do
  34   expect(page).to have_content("Are you a British citizen or UK resident?")
  35 end
  36 
  37 When("I confirm that I am UK citizen or resident") do
  40 end
  41 
  42 Then("I should see the following similar petitions:") do |table|
  43   table.raw.each do |action, signatures|
  44     expect(page).to have_content(action)
  45     expect(page).to have_content(signatures)
  46   end
  47 end
```

#### 开发者路径及执行证据


参考源码入口见 [petition_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/petition_steps.rb)、[pickle_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/pickle_steps.rb)、[search_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/search_steps.rb)、[web_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/web_steps.rb)。

[petition_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/petition_steps.rb)


```text
 204 
 205 Then(/^I should see the petition details$/) do
 206   expect(page).to have_content(@petition.action)
 207   expect(page).to have_content(@petition.background) if @petition.background?
 208 
 209   if @petition.additional_details?
 210     expect(page).to have_content(@petition.additional_details)
 211   end
 212 end
 213 
 252 Then(/^I should see the reason for rejection$/) do
 253   @petition.reload
 254   expect(page).to have_content(@petition.rejection.details)
 255 end
 256 
 257 Then(/^I should see my search query already filled in as the action of the petition$/) do
 282     When I fill in "Petition title" with "The wombats of wimbledon rock."
 283     And I press "Continue"
 284     Then I should see "We checked for similar petitions"
 285     And I press "Continue with my petition"
 286     Then I should see "Say what you want the UK Government or Parliament to do"
 287     When I fill in "Say what you want the UK Government or Parliament to do" with "Give half of Wimbledon rock to wombats!"
 295 
 296 Then(/^I should see my constituency "([^"]*)"/) do |constituency|
 297   expect(page).to have_text(constituency)
 298 end
 299 
 300 Then(/^I should see my MP/) do
 301   expect(page).to have_text("Emily Thornberry MP")
 302 end
 303 
 304 Then(/^I can click on a link to visit my MP$/) do
 307 
 308 Then(/^I should not see the text "([^"]*)"/) do |text|
 309   expect(page).to_not have_text(text)
 310 end
 311 
 312 Then(/^my petition should be validated$/) do
 353 Then(/^I should see the response "([^"]*)"$/) do |response|
 354   within :xpath, "//details[summary/.='Read the response in full']/div", visible: true do
 355     expect(page).to have_content(response)
 356   end
 357 end
 358 
```

[pickle_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/pickle_steps.rb)


```text

```

[search_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/search_steps.rb)


```text
  46 end
  47 
  48 Then(/^I should see the following similar petitions:$/) do |table|
  49   table.raw.each_with_index do |row, index|
  50     within :xpath, "(.//*[contains(@class, 'petition-item-existing')])[#{index + 1}]" do
  51       row.each do |column|
  52         expect(page).to have_content(column)
  53       end
  54     end
  55   end
```

[web_steps.rb](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/web_steps.rb)


```text
  74 Then /^(?:|I )should see "([^"]*)"(?: within "([^"]*)")?$/ do |text, selector|
  75   with_scope(selector) do
  76     expect(page).to have_content(text)
  77   end
  78 end
  79 
```

候选基线direct_calls有919条，官方参考基线有933条。调用条数只用于溯源，不作为行为质量指标。

[候选逐步执行与调用](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/execution.json)；[参考实际基线调用](gold-execution/b8a41623500427f1c983.json)；[逐变异参考kill标签](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference-kills.json)；[具体修改位置](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/surviving-mutants.json)；[候选变异执行结果](../pass-nonkill-20261116/evidence/b8a41623500427f1c983/mutation-results.json)

全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。

## 833对记录审计


833条均为唯一(task,mutant)对，对应783个唯一(project,mutant)，原始mutant_id也有783个。33个变异体在多个任务中出现，造成50条跨任务重复计入。每个任务的存活数量如下。


|项目|任务|存活对数|
|---|---|---|
|algorand-sdk|algorand-sdk/features/unit/v2indexerclient_responses.feature:15|6|
|coddy-agent|coddy-agent/features/ask_mode_http.feature:22|250|
|coddy-agent|coddy-agent/features/reasoning_levels_fetch.feature:10|105|
|coddy-agent|coddy-agent/features/subagents_catalog.feature:14|1|
|coddy-agent|coddy-agent/features/subagents_http.feature:32|4|
|coreshop|coreshop/features/domain/order/create_order_with_discount.feature:23|200|
|e-petitions|e-petitions/features/charlie_creates_a_petition.feature:6|11|
|e-petitions|e-petitions/features/suzie_views_all_petitions.feature:76|1|
|kapua|kapua/service/account/test/src/test/resources/features/AccountService.feature:120|21|
|kapua|kapua/service/tag/test/src/test/resources/features/TagService.feature:297|5|
|prestashop|prestashop/tests/Integration/Behaviour/Features/Scenario/Product/delete_product.feature:17|1|
|python-docx|python-docx/features/blk-add-paragraph.feature:6|2|
|python-docx|python-docx/features/blk-iter-inner-content.feature:17|1|
|python-docx|python-docx/features/cmt-props.feature:12|11|
|python-docx|python-docx/features/doc-add-section.feature:16|1|
|python-docx|python-docx/features/run-access-inner-content.feature:7|7|
|python-docx|python-docx/features/sty-latent-add-del.feature:14|5|
|python-docx|python-docx/features/tbl-cell-props.feature:52|2|
|python-docx|python-docx/features/tbl-row-props.feature:29|2|
|python-docx|python-docx/features/txt-font-props.feature:30|18|
|python-docx|python-docx/features/txt-font-props.feature:40|17|
|python-docx|python-docx/features/txt-font-props.feature:74|4|
|python-docx|python-docx/features/txt-parfmt-props.feature:136|16|
|sylius|sylius/features/hybrid/checkout/placing_order_on_multi_channel/placing_an_order_on_a_single_channel_store.feature:20|142|


全部833对均为gold killed、candidate passed。参考基线覆盖全部833个变异起始行；候选基线覆盖84个，另749个未覆盖。该统计按任务—变异对计算，同一源行和变异体可重复出现。行未覆盖与需求范围差异、fixture差异和真实漏执行均可能有关。

逐变异表保存原始修改、位置、每任务存活数、跨任务出现次数、生成与参考结果、参考基线实际同文件调用和证据路径。3个已逐对对照的旧代表变异标记EXPLICIT_REQUIREMENT_SUPPORTED，其余830对需求相关性保留INSUFFICIENT_EVIDENCE。旧任务级判断不会被自动传播到所有变异。这些记录缺少足以完成逐对语义归因的证据，不能把833对作为833个已确认需求缺陷。

## 研究结论的适用范围

操作未真正执行在CoreShop订单与coddy工具调用中有直接证据，覆盖PHP/Behat与Go/Godog。必要准备缺失在python-docx/behave与CoreShop/Behat出现。观察边界缺失涉及Sylius管理员订单读回与e-petitions管理员页面条件，两者保留各自业务含义。结果断言约束缺失涉及Kapua/Java异常约束与e-petitions/Ruby对象—值关系。跨项目的共同点是明确需求义务在测试链中失去对应约束；这些具体机制尚不能合并为同一因果解释。

本轮沿用原始评测和生成产物，全部新增工作为读取、静态对照及统计。没有针对缺口重新执行反事实实验。两条e-petitions新代表变异有源码与已有kill/pass支持，但其实际DOM和逐变异参考失败位置未保存，传播细节仍属有证据的推断。

