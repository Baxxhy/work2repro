# 真实案例证据册

证据分三级分别报告。L1为需求—代码缺口确认，L2为对应变异存活和参考kill标签确认，L3为完整因果传播确认。本轮没有新增执行，L3均不作确认。详细步骤、源码与结果链接指向既有冻结证据。

## coreshop/features/domain/order/create_order_with_discount.feature:23

项目 coreshop，类别 A，状态 CONFIRMED_GAP。

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

原始杀死数 0/200。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 CreateOrderContext.php

[原文件](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/generated/src/CoreShop/Behat/Context/Domain/Order/CreateOrderContext.php)

```text
1 <?php
2 
3 declare(strict_types=1);
4 
5 namespace CoreShop\Behat\Context\Domain\Order;
6 
7 use Behat\Behat\Context\Context;
8 use Webmozart\Assert\Assert;
9 
10 /**
11  * Steps for the focused order-creation scenario.
12  *
13  * The background vocabulary is deliberately accepted here because this
14  * context is used in the isolated scenario harness, where the data fixtures
15  * are supplied by the surrounding CoreShop test environment.
16  */
17 final class CreateOrderContext implements Context
18 {
19     private array $items = [];
20 
21     private mixed $order = null;
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
38     /** @Given /^the site operates on locale "([^"]+)"$/ */
39     public function siteOperatesOnLocale(string $locale): void
40     {
41     }
42 
43     /** @Given /^the site has a tax rate "([^"]+)" with "([^"]+)" rate$/ */
44     public function siteHasTaxRate(string $name, string $rate): void
45     {
46     }
47 
48     /** @Given /^the site has a tax rule group "([^"]+)"$/ */
49     public function siteHasTaxRuleGroup(string $name): void
50     {
51     }
52 
53     /** @Given /^the tax rule group has a tax rule for country "([^"]+)" with tax rate "([^"]+)"$/ */
54     public function taxRuleGroupHasTaxRule(string $country, string $rate): void
55     {
56     }
57 
58     /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
59     public function siteHasProduct(string $name, int $price): void
60     {
61     }
62 
63     /** @Given /^the product has the tax rule group "([^"]+)"$/ */
64     public function productHasTaxRuleGroup(string $name): void
65     {
66     }
67 
68     /** @Given /^the site has a customer "([^"]+)"$/ */
69     public function siteHasCustomer(string $email): void
70     {
71     }
72 
73     /** @Given /^the customer "([^"]+)" has an address with country "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)", "([^"]+)"$/ */
74     public function customerHasAddress(string $email, string $country, string $postcode, string $city, string $street, string $number): void
75     {
76     }
77 
78     /** @Given /^the cart belongs to customer "([^"]+)"$/ */
79     public function cartBelongsToCustomer(string $email): void
80     {
81     }
82 
83     /** @Given /^adding a cart price rule named "([^"]+)"$/ */
84     public function addingCartPriceRule(string $name): void
85     {
86     }
87 
88     /** @Given /^the cart rule is active$/ */
89     public function cartRuleIsActive(): void
90     {
91     }
92 
93     /** @Given /^the cart rule is a voucher rule with code "([^"]+)"$/ */
94     public function cartRuleIsVoucher(string $code): void
95     {
96     }
97 
98     /** @Given /^the cart rule has a action discount with (\d+) in currency "([^"]+)" off$/ */
99     public function cartRuleHasDiscount(int $amount, string $currency): void
100     {
101     }
102 
103     /** @Given /^I add the product "([^"]+)" to my cart$/ */
104     public function addProductToCart(string $product): void
105     {
106         $this->items[] = $product;
107     }
108 
109     /** @Given /^I apply the voucher code "([^"]+)" to my cart$/ */
110     public function applyVoucher(string $code): void
111     {
112     }
113 
114     /** @Given /^the cart ships to customer "([^"]+)" address with postcode "([^"]+)"$/ */
115     public function cartShipsToAddress(string $email, string $postcode): void
116     {
117     }
118 
119     /** @Given /^the cart invoices to customer "([^"]+)" address with postcode "([^"]+)"$/ */
120     public function cartInvoicesToAddress(string $email, string $postcode): void
121     {
122     }
123 
124     /** @When /^I create an order from my cart$/ */
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
136         };
137     }
138 
139     /** @Then /^there should be one product in my order$/ */
140     public function orderHasOneProduct(): void
141     {
142         Assert::notNull($this->order, 'No order was created from the cart.');
143         Assert::count($this->order->getItems(), 1);
144     }
145 }
```

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/mutation-results.json)

- [参考 OrderContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Domain/OrderContext.php)

- [参考 ActionFormTrait.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ActionFormTrait.php)

- [参考 CartContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartContext.php)

- [参考 CartPriceRuleContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CartPriceRuleContext.php)

- [参考 ConditionFormTrait.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ConditionFormTrait.php)

- [参考 CountryContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)

- [参考 CustomerContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/CustomerContext.php)

- [参考 LocaleContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/LocaleContext.php)

- [参考 OrderContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/OrderContext.php)

- [参考 ProductContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/ProductContext.php)

- [参考 StoreContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)

- [参考 TaxRateContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRateContext.php)

- [参考 TaxRuleGroupContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Setup/TaxRuleGroupContext.php)

- [参考 CartContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartContext.php)

- [参考 CartPriceRuleContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CartPriceRuleContext.php)

- [参考 CountryContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CountryContext.php)

- [参考 CurrencyContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CurrencyContext.php)

- [参考 CustomerContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/CustomerContext.php)

- [参考 OrderContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/OrderContext.php)

- [参考 ProductContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/ProductContext.php)

- [参考 TaxRateContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRateContext.php)

- [参考 TaxRuleGroupContext.php](../../reports/pass-nonkill-20261116/evidence/f54d3444bfce11f4c30f/reference/src/CoreShop/Behat/Context/Transform/TaxRuleGroupContext.php)

## coddy-agent/features/ask_mode_http.feature:22

项目 coddy-agent，类别 A;B;C，状态 CONFIRMED_GAP。

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

原始杀死数 138/388。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 bdd_ask_mode_e2e_test.go

[原文件](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/generated/external/httpserver/bdd_ask_mode_e2e_test.go)

```text
1 //go:build http
2 
3 package httpserver
4 
5 import (
6 	"context"
7 	"fmt"
8 	"log/slog"
9 	"net/http"
10 	"net/http/httptest"
11 	"os"
12 	"path/filepath"
13 	"strings"
14 	"testing"
15 
16 	"github.com/cucumber/godog"
17 	"github.com/EvilFreelancer/coddy-agent/internal/acp"
18 	"github.com/EvilFreelancer/coddy-agent/internal/config"
19 	"github.com/EvilFreelancer/coddy-agent/internal/llm"
20 	"github.com/EvilFreelancer/coddy-agent/internal/session"
21 )
22 
23 type askModeHTTPWorld struct {
24 	t *testing.T
25 	ts *httptest.Server
26 	workspace, file string
27 	toolNames []string
28 	transcript string
29 }
30 
31 func TestAskModeHTTPE2E(t *testing.T) {
32 	suite := godog.TestSuite{
33 		Name: "ask-mode-http",
34 		ScenarioInitializer: func(sc *godog.ScenarioContext) {
35 			w := &askModeHTTPWorld{t:t}
36 			sc.Before(func(ctx context.Context, _ *godog.Scenario) (context.Context,error) { *w=askModeHTTPWorld{t:t}; return ctx,nil })
37 			sc.After(func(ctx context.Context, _ *godog.Scenario, _ error) (context.Context,error) { if w.ts!=nil { w.ts.Close() }; return ctx,nil })
38 			sc.Step(`^a coddy gateway backed by a streaming stub model that writes a file, then answers$`, w.gateway)
39 			sc.Step(`^a client sends a streaming "([^"]*)" prompt over POST /v1/responses$`, w.send)
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
50 	root,err:=os.MkdirTemp("","coddy-ask-bdd-"); if err!=nil{return err}
51 	w.workspace=root; w.file=filepath.Join(root,"created.txt")
52 	cfg:=&config.Config{Paths:config.Paths{Home:filepath.Join(root,"home"),CWD:root}, Agent:config.Agent{Model:"stub/model"}}
53 	if err=os.MkdirAll(cfg.Paths.Home,0755); err!=nil{return err}
54 	run:=func(_ context.Context, st *session.State, prompt []acp.ContentBlock, _ acp.UpdateSender)(string,error){
55 		for _,b:=range prompt { if b.Type=="text" { st.AddMessage(llm.Message{Role:llm.RoleUser,Content:b.Text}) } }
56 		st.AddMessage(llm.Message{Role:llm.RoleAssistant,Content:"done"})
57 		if err:=os.WriteFile(w.file,[]byte("written"),0644); err!=nil{return "",err}
58 		return string(acp.StopReasonEndTurn),nil
59 	}
60 	mgr:=session.NewManager(cfg,noopSender{},run,slog.Default(),root,nil)
61 	srv:=New(cfg,mgr,slog.Default(),root); w.ts=httptest.NewServer(srv.Handler())
62 	return nil
63 }
64 func(w *askModeHTTPWorld) send(mode string)error{
65 	body:=fmt.Sprintf(`{"model":%q,"input":"write the file","stream":true}`,mode)
66 	req,err:=http.NewRequest(http.MethodPost,w.ts.URL+"/v1/responses",strings.NewReader(body)); if err!=nil{return err}
67 	req.Header.Set("Content-Type","application/json")
68 	res,err:=w.ts.Client().Do(req); if err!=nil{return err}; defer res.Body.Close()
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

### 生成代码 bdd_compaction_http_test.go

[原文件](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/generated/external/httpserver/bdd_compaction_http_test.go)

```text
1 //go:build http
2 
3 package httpserver
```

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/mutation-results.json)

- [参考 bdd_ask_mode_e2e_test.go](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_ask_mode_e2e_test.go)

- [参考 bdd_compaction_http_test.go](../../reports/pass-nonkill-20261116/evidence/af2db3aaa3d3aed0e730/reference/external/httpserver/bdd_compaction_http_test.go)

<a id="sylius"></a>

## sylius/features/hybrid/checkout/placing_order_on_multi_channel/placing_an_order_on_a_single_channel_store.feature:20

项目 sylius，类别 B，状态 CONFIRMED_GAP。

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

原始杀死数 260/402。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 OrderContext.php

[原文件](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/generated/src/Sylius/Behat/Context/Api/Checkout/OrderContext.php)

```text
1 <?php
2 
3 declare(strict_types=1);
4 
5 namespace Sylius\Behat\Context\Api\Checkout;
6 
7 use Behat\Behat\Context\Context;
8 use Behat\Step\Then;
9 use Behat\Step\When;
10 use Sylius\Behat\Context\Setup\Checkout\PaymentContext;
11 use Sylius\Behat\Context\Setup\Checkout\ShippingContext;
12 use Sylius\Behat\Service\SharedStorageInterface;
13 use Sylius\Bundle\ApiBundle\Command\Checkout\CompleteOrder;
14 use Sylius\Component\Core\Model\OrderInterface;
15 use Sylius\Component\Core\Model\PaymentMethodInterface;
16 use Sylius\Component\Core\Model\ShippingMethodInterface;
17 use Symfony\Component\Messenger\MessageBusInterface;
18 use Webmozart\Assert\Assert;
19 
20 final readonly class OrderContext implements Context
21 {
22     public function __construct(
23         private ShippingContext $shippingContext,
24         private PaymentContext $paymentContext,
25         private SharedStorageInterface $sharedStorage,
26         private MessageBusInterface $commandBus,
27     ) {
28     }
29 
30     #[When('I proceed with :shippingMethod shipping method and :paymentMethod payment')]
31     public function iProceedWithShippingAndPayment(ShippingMethodInterface $shippingMethod, PaymentMethodInterface $paymentMethod): void
32     {
33         $this->shippingContext->chooseShippingMethod($shippingMethod);
34         $this->paymentContext->choosePaymentMethod($paymentMethod);
35     }
36 
37     #[When('I confirm my order')]
38     public function iConfirmMyOrder(): void
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

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/mutation-results.json)

- [参考 Resources.php](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Resources.php)

- [参考 CheckoutShippingContext.php](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/Checkout/CheckoutShippingContext.php)

- [参考 CheckoutContext.php](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/CheckoutContext.php)

- [参考 OrderContext.php](../../reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa/reference/src/Sylius/Behat/Context/Api/Shop/OrderContext.php)

## kapua/service/account/test/src/test/resources/features/AccountService.feature:120

项目 kapua，类别 C，状态 CONFIRMED_GAP。

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

原始杀死数 22/43。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 DeleteNonexistingAccountSteps.java

[原文件](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/generated/service/account/test/src/test/java/org/eclipse/kapua/service/account/test/r2t/generated/DeleteNonexistingAccountSteps.java)

```text
1 package org.eclipse.kapua.service.account.test.r2t.generated;
2 
3 import javax.inject.Inject;
4 
5 import org.eclipse.kapua.KapuaException;
6 import org.eclipse.kapua.commons.model.id.IdGenerator;
7 import org.eclipse.kapua.commons.model.id.KapuaEid;
8 import org.eclipse.kapua.locator.KapuaLocator;
9 import org.eclipse.kapua.qa.common.StepData;
10 import org.eclipse.kapua.service.account.AccountService;
11 
12 import io.cucumber.java.en.When;
13 
14 public class DeleteNonexistingAccountSteps {
15     private static final String EXCEPTION_CAUGHT = "ExceptionCaught";
16 
17     private final StepData stepData;
18 
19     @Inject
20     public DeleteNonexistingAccountSteps(StepData stepData) {
21         this.stepData = stepData;
22     }
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
33         stepData.put(EXCEPTION_CAUGHT, false);
34     }
35 }
```

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/mutation-results.json)

- [参考 AccountServiceSteps.java](../../reports/pass-nonkill-20261116/evidence/93eac4b8da28527c6348/reference/service/account/test-steps/src/main/java/org/eclipse/kapua/service/account/steps/AccountServiceSteps.java)

## python-docx/features/doc-add-section.feature:16

项目 python-docx，类别 A_setup，状态 CONFIRMED_GAP。

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

原始杀死数 112/113。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 doc_add_section.py

[原文件](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/generated/features/steps/doc_add_section.py)

```text
1 """Step definitions for adding document sections."""
2 
3 from behave import given, when, then
4 from docx import Document
5 
6 
7 @given("a single-section Document object with headers and footers as document")
8 def given_document_with_headers_and_footers(context):
9     document = Document()
10     assert len(document.sections) == 1, "a new document should have one section"
11 
12     # Materialize the six header/footer variants on the existing section.  This
13     # gives the added section actual prior header/footer definitions to inherit.
14     original_section = document.sections[0]
15     for name in (
16         "header",
17         "even_page_header",
18         "first_page_header",
19         "footer",
20         "even_page_footer",
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

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/mutation-results.json)

- [参考 document.py](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/document.py)

- [参考 helpers.py](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/helpers.py)

- [参考 section.py](../../reports/pass-nonkill-20261116/evidence/676d56c1c72dc4237805/reference/features/steps/section.py)

## e-petitions/features/charlie_creates_a_petition.feature:6

项目 e-petitions，类别 C，状态 GAP_CONFIRMED_CAUSE_UNRESOLVED。

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

原始杀死数 172/183。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 charlie_creates_a_petition_steps.rb

[原文件](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/generated/features/step_definitions/charlie_creates_a_petition_steps.rb)

```text
1 Given("the following petitions exist:") do |table|
2   table.hashes.each do |attributes|
3     attributes["signature_count"] = attributes["signature_count"].to_i
4     attributes["open_at"] = nil if attributes["open_at"].to_s.empty?
5     FactoryBot.create(:petition, **attributes.symbolize_keys, increment: false)
6   end
7 end
8 
9 Given(/^I am on the (.+)$/) do |page_name|
10   visit url_to("the #{page_name}")
11 end
12 
13 When(/^I follow "([^"]*)"(?: within "([^"]*)")?$/) do |link, scope|
14   if scope
15     within(:xpath, scope) { click_link(link) }
16   else
17     click_link(link)
18   end
19 end
20 
21 Then(/^I should see "([^"]*)"$/) do |text|
22   expect(page).to have_content(text)
23 end
24 
25 When(/^I fill in "([^"]*)" with "([^"]*)"$/) do |field, value|
26   fill_in(field, with: value)
27 end
28 
29 When(/^I press "([^"]*)"$/) do |button|
30   click_button(button)
31 end
32 
33 Then("I should be asked to confirm my eligibility") do
34   expect(page).to have_content("Are you a British citizen or UK resident?")
35 end
36 
37 When("I confirm that I am UK citizen or resident") do
38   choose("Yes")
39   click_button("Continue")
40 end
41 
42 Then("I should see the following similar petitions:") do |table|
43   table.raw.each do |action, signatures|
44     expect(page).to have_content(action)
45     expect(page).to have_content(signatures)
46   end
47 end
```

### 参考行为与执行证据

- [execution.json](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/execution.json)

- [surviving-mutants.json](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/surviving-mutants.json)

- [reference-kills.json](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference-kills.json)

- [mutation-results.json](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/mutation-results.json)

- [参考 petition_steps.rb](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/petition_steps.rb)

- [参考 pickle_steps.rb](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/pickle_steps.rb)

- [参考 search_steps.rb](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/search_steps.rb)

- [参考 web_steps.rb](../../reports/pass-nonkill-20261116/evidence/b8a41623500427f1c983/reference/features/step_definitions/web_steps.rb)

## e-petitions/features/admin/anonymize_petitions.feature:18

项目 e-petitions，类别 B，状态 CONFIRMED_GAP。

```gherkin
  As an admin user
  I want to anonymize all petitions 6 months after parliament closes in accordance with our privacy policy
  Background:
    Given I am logged in as a sysadmin with the email "muddy@example.com", first_name "Sys", last_name "Admin"
  Scenario: An admin cannot anonymize petitions if there are none to anonymize
    When I go to the admin parliament page
    Then I should not see "Anonymize petitions"
```

候选走真实SSO callback和访问页面，最终只断言全页没有Anonymize petitions，未核验已登录管理员及实际页面。基线覆盖真实parliaments controller。e9639a04a50dc1ac删除AdminUser.find_or_create_from!的用户构建返回nil，callback源码else跳转login，生成仍通过、参考杀死。参考登录步骤检查目标路径和成功提示。缺失登录/页面状态观察已确认，变异时最终DOM未保存，完整重定向传播仍为有源码支持的推断。

原始杀死数 95/110。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 admin_anonymize_petitions_steps.rb

[原文件](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/generated/features/step_definitions/admin_anonymize_petitions_steps.rb)

```text
1 Given(/^I am logged in as a sysadmin with the email "([^"]+)", first_name "([^"]+)", last_name "([^"]+)"$/) do |email, first_name, last_name|
2   auth = FactoryBot.build(
3     :sysadmin_sso_user,
4     email: email,
5     first_name: first_name,
6     last_name: last_name
7   )
8   OmniAuth.config.mock_auth[:example] = auth
9   visit "/admin/auth/example/callback"
10 end
11 
12 When(/^I go to (.+)$/) do |page_name|
13   visit url_to(page_name)
14 end
15 
16 Then(/^I should not see "([^"]*)"$/) do |text|
17   expect(page).not_to have_text(text)
18 end
```

### 参考行为与执行证据

- [execution.json](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/execution.json)

- [surviving-mutants.json](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/surviving-mutants.json)

- [reference-kills.json](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/reference-kills.json)

- [mutation-results.json](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/mutation-results.json)

- [参考 authentication_steps.rb](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/reference/features/step_definitions/authentication_steps.rb)

- [参考 web_steps.rb](../../reports/business-behavior-gap-20261116/evidence/03cfd691e00da6e9f8a9/reference/features/step_definitions/web_steps.rb)

## e-petitions/features/joe_searches_for_an_archived_petition.feature:15

项目 e-petitions，类别 C，状态 CONFIRMED_GAP。

```gherkin
  In order to see what petitions were created in the past
  As Joe, a member of the general public
  I want to be able to search archived petitions
  And I want to see the results ordered by the oldest petitions
  Background:
    Given the following archived petitions exist:
      | action                   | state    | signature_count | opened_at  | closed_at  | created_at | rejected_at |
      | Wombles are great        | closed   | 835             | 2012-01-01 | 2013-01-01 | 2012-01-01 |             |
      | The Wombles of Wimbledon | closed   | 243             | 2011-04-01 | 2012-04-01 | 2011-04-01 |             |
      | Common People            | closed   | 639             | 2014-10-01 | 2015-03-31 | 2014-10-01 |             |
      | Eavis vs the Wombles     | rejected |                 |            |            | 2011-01-01 | 2011-01-08  |
  Scenario: Searching for petitions
    When I go to the archived petitions page
    And I fill in "search" with "Wombles"
    And I press "Search"
    Then I should be on the archived petitions page
    But I should see the following search results:
      | Wombles are great              | Total signatures 835       |
      | The Wombles of Wimbledon       | Total signatures 243       |
      | Eavis vs the Wombles           | Rejected on 8 January 2011 |
    And the markup should be valid
```

真实搜索Wombles，核验路径；结果表只逐项检查全页title/detail，没有绑定行或排除Common People。需求明确列出搜索结果与排序叙述，参考按nth结果行核验。4639544fe90a683c令search?返回nil；execute_search源码因此跳过查询过滤，生成通过、参考杀死。行关系与过滤判别不足有直接证据，具体变异页面内容没有日志，不能声称已观测实际结果顺序。

原始杀死数 100/101。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 archived_petition_search_steps.rb

[原文件](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/generated/features/step_definitions/archived_petition_search_steps.rb)

```text
1 Given(/^the following archived petitions exist:$/) do |table|
2   table.hashes.each do |attributes|
3     attributes = attributes.transform_values { |value| value == "" ? nil : value }
4     attributes["signature_count"] = attributes["signature_count"].to_i if attributes["signature_count"]
5 
6     %w[opened_at closed_at created_at rejected_at].each do |date_attribute|
7       attributes[date_attribute] = Date.parse(attributes[date_attribute]) if attributes[date_attribute]
8     end
9 
10     traits = attributes["state"] == "rejected" ? [:rejected] : []
11     FactoryBot.create(:archived_petition, *traits, **attributes.symbolize_keys)
12   end
13 end
14 
15 When(/^I go to (.+)$/) do |page_name|
16   visit url_to(page_name)
17 end
18 
19 When(/^I fill in "([^"]*)" with "([^"]*)"$/) do |field, value|
20   fill_in field, with: value
21 end
22 
23 When(/^I press "([^"]*)"$/) do |button|
24   click_button button
25 end
26 
27 Then(/^I should be on (.+)$/) do |page_name|
28   expect(page).to have_current_path(url_to(page_name), ignore_query: true)
29 end
30 
31 Then(/^I should see the following search results:$/) do |table|
32   table.raw.each do |title, detail|
33     expect(page).to have_text(title)
34     expect(page).to have_text(detail)
35   end
36 end
37 
38 Then(/^the markup should be valid$/) do
39   document = Nokogiri::HTML5(page.html)
40   expect(document.at_css("html")).not_to be_nil
41   expect(document.at_css("body")).not_to be_nil
42 end
```

### 参考行为与执行证据

- [execution.json](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/execution.json)

- [surviving-mutants.json](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/surviving-mutants.json)

- [reference-kills.json](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/reference-kills.json)

- [mutation-results.json](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/mutation-results.json)

- [参考 inspection_steps.rb](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/inspection_steps.rb)

- [参考 pickle_steps.rb](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/pickle_steps.rb)

- [参考 validation_steps.rb](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/validation_steps.rb)

- [参考 web_steps.rb](../../reports/business-behavior-gap-20261116/evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/web_steps.rb)

## python-docx/features/hdr-header-footer.feature:72

项目 python-docx，类别 N，状态 NO_CONFIRMED_GAP。

```gherkin
  In order to control the appearance of page headers and footers
  As a developer using python-docx
  I need properties and methods on _Header and _Footer objects
  Scenario: _Footer inherits content
    Given a _Footer object with a footer definition as footer
      And the next _Footer object with no footer definition as footer_2
     Then footer_2.paragraphs[0].text == footer.paragraphs[0].text
      And footer_2.is_linked_to_previous is True
```

先给footer.paragraphs[0].text赋值形成实际定义，再add_section并比较继承文本及linked状态。唯一存活在关系加载路径，参考采用文件fixture。此案例反驳所有header/footer生成都缺必要准备的说法。

原始杀死数 120/121。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 footer_inherits_content.py

[原文件](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/generated/features/steps/footer_inherits_content.py)

```text
1 """Step definitions for footer inheritance behavior."""
2 
3 from behave import given, then
4 from docx import Document
5 
6 
7 @given("a _Footer object with a footer definition as footer")
8 def given_footer_with_definition(context):
9     document = Document()
10     section = document.sections[0]
11     footer = section.footer
12     footer.paragraphs[0].text = "Footer content"
13 
14     context.document = document
15     context.footer = footer
16 
17 
18 @given("the next _Footer object with no footer definition as footer_2")
19 def given_next_footer_without_definition(context):
20     section = context.document.add_section()
21     context.footer_2 = section.footer
22 
23 
24 @then("footer_2.paragraphs[0].text == footer.paragraphs[0].text")
25 def then_footer_content_inherited(context):
26     assert (
27         context.footer_2.paragraphs[0].text == context.footer.paragraphs[0].text
28     ), "next footer did not inherit the previous footer's paragraph text"
29 
30 
31 @then("footer_2.is_linked_to_previous is True")
32 def then_footer_is_linked_to_previous(context):
33     assert context.footer_2.is_linked_to_previous is True, (
34         "next footer should be linked to the previous section"
35     )
```

### 参考行为与执行证据

- [execution.json](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/execution.json)

- [surviving-mutants.json](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/surviving-mutants.json)

- [reference-kills.json](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/reference-kills.json)

- [mutation-results.json](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/mutation-results.json)

- [参考 hdrftr.py](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/reference/features/steps/hdrftr.py)

- [参考 helpers.py](../../reports/business-behavior-gap-20261116/evidence/056dd0dc42a69a6e107b/reference/features/steps/helpers.py)

## algorand-sdk/features/unit/v2algodclient_paths.feature:83

项目 algorand-sdk，类别 N，状态 NO_CONFIRMED_GAP。

```gherkin
  Background:
    Given mock server recording request paths
  Scenario Outline: GetApplicationBoxByName
    When we make a GetApplicationBoxByName call for applicationID <application-id> with encoded box name "<encoded-box-name>"
    Then expect the path used to be "<path>"
    Examples:
      | path                                                | application-id | encoded-box-name     |
      | /v2/applications/1234/box?name=b64%3AaGVsbG8%3D     | 1234           | b64:aGVsbG8=         |
      | /v2/applications/1234/box?name=b64%3A%2Fw%3D%3D     | 1234           | b64:/w==             |
      | /v2/applications/1234/box?name=b64%3A8J%2BSqQ%3D%3D | 1234           | b64:8J+SqQ==         |
      | /v2/applications/1234/box?name=b64%3AYS96           | 1234           | b64:YS96             |
```

启动实际HTTP测试服务器，SDK.execute，捕获请求URI并逐项精确比较。参考使用getRequestUrl辅助路径，五个存活集中于该路径。候选直接观察真实请求提供反例。

原始杀死数 17/22。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 AlgodRestApiV2PathsSteps.java

[原文件](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/generated/src/test/java/com/algorand/algosdk/unit/AlgodRestApiV2PathsSteps.java)

```text
1 package com.algorand.algosdk.unit;
2 
3 import com.algorand.algosdk.v2.client.algod.GetApplicationBoxByName;
4 import com.algorand.algosdk.v2.client.common.AlgodClient;
5 import com.sun.net.httpserver.HttpServer;
6 import io.cucumber.java.en.Given;
7 import io.cucumber.java.en.When;
8 import io.cucumber.java.en.Then;
9 
10 import java.io.IOException;
11 import java.net.InetSocketAddress;
12 import java.nio.charset.StandardCharsets;
13 
14 import static org.assertj.core.api.Assertions.assertThat;
15 
16 public class AlgodRestApiV2PathsSteps {
17     private HttpServer server;
18     private String recordedPath;
19     private AlgodClient client;
20 
21     @Given("mock server recording request paths")
22     public void mockServerRecordingRequestPaths() throws IOException {
23         server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
24         server.createContext("/", exchange -> {
25             recordedPath = exchange.getRequestURI().toASCIIString();
26             byte[] body = "{}".getBytes(StandardCharsets.UTF_8);
27             exchange.sendResponseHeaders(404, body.length);
28             exchange.getResponseBody().write(body);
29             exchange.close();
30         });
31         server.start();
32         client = new AlgodClient("http://127.0.0.1", server.getAddress().getPort(), "");
33     }
34 
35     @When("we make a GetApplicationBoxByName call for applicationID {long} with encoded box name {string}")
36     public void makeGetApplicationBoxByNameCall(long applicationId, String encodedBoxName) throws Exception {
37         GetApplicationBoxByName query = client.GetApplicationBoxByName(applicationId).name(encodedBoxName);
38         try {
39             query.execute();
40         } catch (Exception ignored) {
41             // The test server intentionally returns 404; the request itself is what is under test.
42         }
43     }
44 
45     @Then("expect the path used to be {string}")
46     public void expectPathUsedToBe(String expectedPath) {
47         assertThat(recordedPath).isEqualTo(expectedPath);
48         server.stop(0);
49     }
50 }
```

### 参考行为与执行证据

- [execution.json](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/execution.json)

- [surviving-mutants.json](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/surviving-mutants.json)

- [reference-kills.json](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/reference-kills.json)

- [mutation-results.json](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/mutation-results.json)

- [参考 AlgodPaths.java](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/reference/src/test/java/com/algorand/algosdk/unit/AlgodPaths.java)

- [参考 PathsShared.java](../../reports/business-behavior-gap-20261116/evidence/87e517283a3a24f40b73/reference/src/test/java/com/algorand/algosdk/unit/PathsShared.java)

## e-petitions/features/joe_views_all_archived_petitions.feature:73

项目 e-petitions，类别 C，状态 CONTROL_GAP。

```gherkin
  In order to see what petitions were created in the past
  As Joe, a member of the general public
  I want to be able to view all archived petitions
  Background:
    Given these archived petitions exist:
      | action                   | state    | signature_count | created_at | rejected_at | opened_at  |
      | Wombles are great        | closed   | 835             | 2012-01-01 |             | 2012-01-10 |
      | Common People            | closed   | 639             | 2014-01-01 |             | 2014-01-10 |
      | Save the planet          | closed   | 243             | 2014-01-01 |             | 2014-01-11 |
      | Wombles to Parliament    | closed   | 243             | 2013-01-01 |             | 2013-01-10 |
      | Free gig tickets         | rejected |                 | 2013-01-01 | 2013-01-08  |            |
      | Wombles are &*!%         | hidden   |                 | 2013-02-01 | 2013-02-08  |            |
      | Bring back the Wombles   | stopped  |                 | 2013-03-01 |             | 2013-03-10 |
  Scenario: Downloading the CSV data for archived petitions
    Given I am on the archived petitions page
    Then I should see the following list of archived petitions:
      | Wombles are great         | Total signatures 835       |
      | Common People             | Total signatures 639       |
      | Save the planet           | Total signatures 243       |
      | Wombles to Parliament     | Total signatures 243       |
      | Free gig tickets          | Rejected on 8 January 2013 |
    And the markup should be valid
    When I click the CSV link
    Then I should get a download with the filename "filtered-archived-petitions.csv"
```

真实列表及CSV点击和下载文件名检查；表格同样只全页分别匹配action/detail，缺少同一行绑定。95/95仍KillComplete。确认C关系缺口的反例，说明KillComplete并不证明全部关系义务受检。与admin all_petitions共享列表类型，权限与CSV流程不同。

原始杀死数 95/95。L2仅说明已有变异标签，不能把全部存活归因于L1。L3待验证。

### 生成代码 archived_petitions_steps.rb

[原文件](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/generated/features/step_definitions/archived_petitions_steps.rb)

```text
1 Given(/^these archived petitions exist:$/) do |table|
2   table.hashes.each do |row|
3     attributes = {
4       action: row.fetch("action"),
5       state: row.fetch("state"),
6       signature_count: row["signature_count"].presence&.to_i,
7       created_at: Date.iso8601(row.fetch("created_at")),
8       opened_at: row["opened_at"].presence && Date.iso8601(row["opened_at"]),
9       rejected_at: row["rejected_at"].presence && Date.iso8601(row["rejected_at"])
10     }
11 
12     traits = case row.fetch("state")
13              when "rejected", "hidden" then [row.fetch("state").to_sym]
14              else []
15              end
16     FactoryBot.create(:archived_petition, *traits, **attributes)
17   end
18 end
19 
20 Given(/^I am on the archived petitions page$/) do
21   visit archived_petitions_path
22 end
23 
24 Then(/^I should see the following list of archived petitions:$/) do |table|
25   table.raw.each do |action, detail|
26     expect(page).to have_content(action.strip)
27     expect(page).to have_content(detail.strip)
28   end
29 end
30 
31 Then(/^the markup should be valid$/) do
32   # Ensure the returned document is parseable and has the expected document
33   # structure; Nokogiri's HTML parser recovers from benign HTML5 constructs.
34   document = Nokogiri::HTML(page.html)
35   expect(document.at("html")).not_to be_nil
36   expect(document.at("body")).not_to be_nil
37 end
38 
39 When(/^I click the CSV link$/) do
40   click_link "CSV"
41 end
42 
43 Then(/^I should get a download with the filename "([^"]*)"$/) do |filename|
44   expect(page.response_headers["Content-Disposition"]).to include(filename)
45 end
```

### 参考行为与执行证据

- [execution.json](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/execution.json)

- [surviving-mutants.json](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/surviving-mutants.json)

- [reference-kills.json](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference-kills.json)

- [mutation-results.json](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/mutation-results.json)

- [参考 constituency_search_steps.rb](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference/features/step_definitions/constituency_search_steps.rb)

- [参考 inspection_steps.rb](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference/features/step_definitions/inspection_steps.rb)

- [参考 petition_steps.rb](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference/features/step_definitions/petition_steps.rb)

- [参考 validation_steps.rb](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference/features/step_definitions/validation_steps.rb)

- [参考 web_steps.rb](../../reports/business-behavior-gap-20261116/evidence/51402702ed0f9175add9/reference/features/step_definitions/web_steps.rb)

## 同类案例与对照关系

CoreShop与coddy支持真实操作被替代，但业务路径不同。Sylius与管理员页面案例都涉及指定观察边界，后者变异时DOM未保存。Kapua的异常约束与列表关系属于不同断言义务。python-docx页脚真实赋值构成页眉准备缺失的近邻对照；Algorand真实HTTP URI检查是正确外部观察对照。KC列表仍缺关系断言，证明指标与义务并非一一对应。

## TSB交叉核验

6例原始规格、代码、执行矩阵、24个代表变异及无效测试排除见[完整交叉报告](../../reports/business-behavior-gap-20261116/TSB_CROSS_VALIDATION.md)。Pueue的工作流缺失与帮助文本弱断言分别记载；DuckDB的正确实现失败测试不能算作有效变异杀死。eureka真实检查本地和远程Git状态提供反例。

## 其他已分析任务

全部24条旧nonkill、10条旧控制及35条新增案例的逐条分析分别见[旧案例](../../reports/pass-nonkill-20261116/PASS_NONKILL_CASE_ANALYSIS.md)、[旧控制](../../reports/pass-nonkill-20261116/KILL_COMPLETE_CONTROL_ANALYSIS.md)、[新增35例](../../reports/business-behavior-gap-20261116/CROSS_PROJECT_VALIDATION.md)。本册精读11例，其余复用已有标注，未声称重新逐行复核所有325份生成测试。
