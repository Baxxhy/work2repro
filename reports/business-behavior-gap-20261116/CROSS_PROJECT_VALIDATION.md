# 新增跨项目验证


## 固定选择规则

从已完成780条快照中，按项目分别筛选原实现通过、有非空计分变异且非KillComplete的任务。排除上一轮24例、10条控制以及此前60例语义清单中的ID。四个有合格新增候选的项目各取SHA256稳定排序前5条，共20条。该规则保留了参考范围差异、缺口和未定案例。

控制按项目轮转，从未分析的KillComplete任务中优先同feature，再同scenario kind，再标题token Jaccard，最后SHA256打破平局，共15条。每条控制独立使用一次。自动匹配只能提供候选，下面另记语义匹配强弱。因已完成数据分布限制，尚未补充新的Sylius、coddy、Kapua或PrestaShop项目样本。


[可复核选择脚本](select.py)；[固定清单和全部配对](manifest.json)

## 新增20例汇总

|项目|确认缺口|证据不足|未确认缺口|总计|
|---|---|---|---|---|
|algorand-sdk|0|0|5|5|
|coreshop|3|2|0|5|
|e-petitions|2|0|3|5|
|python-docx|0|0|5|5|


该比例仅描述按项目定额选取的20例。主分类A_setup 3、B 1、C 1、E 2、N 13。与旧6例合计观察到缺口的11例跨6项目，其中多个例子可能共享背景模板；任务独立性不足以支持因果或总体频率估计。

## 新增逐任务分析


### algorand-sdk/features/unit/program_sanity_check.feature:3


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死25/26，存活1，drop 0。

```gherkin
  Scenario Outline: Read a slice of bytes and heuristically decide if it look like program bytes
    Given a base64 encoded program bytes for heuristic sanity check "<bytes>"
    When I start heuristic sanity check over the bytes
    Then if the heuristic sanity check throws an error, the error contains "<error>"

    Examples:
      | bytes                                                                            | error                          |
      |                                                                                  | empty program                  |
      | RE43TUJNQ0w1SlEzUEZVUVM3VE1YNUFINEVFS09CSlZEVUY0VENWNldFUkFUS0ZMUUY0TVFVUFpUQQ== | get Algorand address           |
      | U0dPMUdLU3p5RTdJRVBJdFR4Q0J5dzl4OEZtbnJDRGV4aTkvY09VSk9pST0=                     | should not be b64 encoded      |
      | Q2FzdCBhIGNvbGQgZXllCm9uIGxpZmUsIG9uIGRlYXRoLgpIb3JzZW1hbiwgcGFzcyBieQ==         | all ASCII printable characters |
      | ASABASI=                                                                         |                                |
```

真实LogicsigSignature检查程序，错误断言对应Examples。候选用Java Base64，参考用SDK Encoder.decodeFromBase64；唯一存活为后者返回null。可解释准备路径不同，未发现明确需求义务缺失。

生成代码见 [ProgramSanityCheckSteps.java](evidence/1fcd1f9b3387214ac0f8/generated/src/test/java/com/algorand/algosdk/unit/ProgramSanityCheckSteps.java)。

[实际逐步执行和调用](evidence/1fcd1f9b3387214ac0f8/execution.json)；[参考基线调用](gold-execution/1fcd1f9b3387214ac0f8.json)；[候选全部变异结果](evidence/1fcd1f9b3387214ac0f8/mutation-results.json)；[存活修改](evidence/1fcd1f9b3387214ac0f8/surviving-mutants.json)；[参考杀死标签](evidence/1fcd1f9b3387214ac0f8/reference-kills.json)

参考测试见 [ProgramSanityCheck.java](evidence/1fcd1f9b3387214ac0f8/reference/src/test/java/com/algorand/algosdk/unit/ProgramSanityCheck.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/v2indexerclient_responses.feature:55


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死21/23，存活2，drop 0。

```gherkin
  Scenario Outline: LookupAssetByID response
    Given mock http responses in "<jsonfiles>" loaded from "<directory>"
    When we make any LookupAssetByID call
    Then expect error string to contain "<err>"
    And the parsed LookupAssetByID response should have index <index>
    Examples:
      | jsonfiles              | directory                     | err | index  |
      | lookupAssetByID_0.json | v2indexerclient_responsejsons |     | 163650 |
```

真实lookupAssetByID.execute及asset.index精确断言。参考verifyResponse比对更广响应；存活为Response.getContentType/toString返回null。需求指定asset编号已检查。

生成代码见 [IndexerClientV2ResponseSteps.java](evidence/31e31c5b5fcc07f10802/generated/src/test/java/com/algorand/algosdk/unit/IndexerClientV2ResponseSteps.java)。

[实际逐步执行和调用](evidence/31e31c5b5fcc07f10802/execution.json)；[参考基线调用](gold-execution/31e31c5b5fcc07f10802.json)；[候选全部变异结果](evidence/31e31c5b5fcc07f10802/mutation-results.json)；[存活修改](evidence/31e31c5b5fcc07f10802/surviving-mutants.json)；[参考杀死标签](evidence/31e31c5b5fcc07f10802/reference-kills.json)

参考测试见 [IndexerResponses.java](evidence/31e31c5b5fcc07f10802/reference/src/test/java/com/algorand/algosdk/unit/IndexerResponses.java)、[ResponsesShared.java](evidence/31e31c5b5fcc07f10802/reference/src/test/java/com/algorand/algosdk/unit/ResponsesShared.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/offline.feature:4


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死25/111，存活86，drop 0。

```gherkin
  Scenario: Encode and decode addresses
    When I generate a key
    And I decode the address
    And I encode the address
    Then the address should still be the same
```

真实生成账户、地址字符串及解码往返验证。参考Stepdefs.genKey额外执行Mnemonic.toKey(account.toMnemonic())；86个存活主要属于助记词路径。地址需求和助记词准备应分别解释。

生成代码见 [OfflineSteps.java](evidence/877b243d5a42b255b243/generated/src/test/java/com/algorand/algosdk/unit/OfflineSteps.java)。

[实际逐步执行和调用](evidence/877b243d5a42b255b243/execution.json)；[参考基线调用](gold-execution/877b243d5a42b255b243.json)；[候选全部变异结果](evidence/877b243d5a42b255b243/mutation-results.json)；[存活修改](evidence/877b243d5a42b255b243/surviving-mutants.json)；[参考杀死标签](evidence/877b243d5a42b255b243/reference-kills.json)

参考测试见 [Stepdefs.java](evidence/877b243d5a42b255b243/reference/src/test/java/com/algorand/algosdk/integration/Stepdefs.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/v2algodclient_paths.feature:83


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死17/22，存活5，drop 0。

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

生成代码见 [AlgodRestApiV2PathsSteps.java](evidence/87e517283a3a24f40b73/generated/src/test/java/com/algorand/algosdk/unit/AlgodRestApiV2PathsSteps.java)。

[实际逐步执行和调用](evidence/87e517283a3a24f40b73/execution.json)；[参考基线调用](gold-execution/87e517283a3a24f40b73.json)；[候选全部变异结果](evidence/87e517283a3a24f40b73/mutation-results.json)；[存活修改](evidence/87e517283a3a24f40b73/surviving-mutants.json)；[参考杀死标签](evidence/87e517283a3a24f40b73/reference-kills.json)

参考测试见 [AlgodPaths.java](evidence/87e517283a3a24f40b73/reference/src/test/java/com/algorand/algosdk/unit/AlgodPaths.java)、[PathsShared.java](evidence/87e517283a3a24f40b73/reference/src/test/java/com/algorand/algosdk/unit/PathsShared.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/v2algodclient_responses.feature:75


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死36/41，存活5，drop 0。

```gherkin
  Scenario Outline: Account Information response
    Given mock http responses in "<jsonfiles>" loaded from "<directory>"
    When we make any Account Information call
    Then expect error string to contain "<err>"
    And the parsed Account Information response should have address "<address>"
    Examples:
      | jsonfiles               | directory                   | err | address                                                    |
      | accountInformation.json | v2algodclient_responsejsons |     | ALGORANDAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIN5DNAU |
```

实际AccountInformation.execute，检查返回address字符串。参考比较更广JSON；五个存活含contentType/toString及额外字段路径。未确认明确场景要求遗漏。

生成代码见 [AlgodResponseSteps.java](evidence/8d089ce97868b988d5d0/generated/src/test/java/com/algorand/algosdk/unit/AlgodResponseSteps.java)。

[实际逐步执行和调用](evidence/8d089ce97868b988d5d0/execution.json)；[参考基线调用](gold-execution/8d089ce97868b988d5d0.json)；[候选全部变异结果](evidence/8d089ce97868b988d5d0/mutation-results.json)；[存活修改](evidence/8d089ce97868b988d5d0/surviving-mutants.json)；[参考杀死标签](evidence/8d089ce97868b988d5d0/reference-kills.json)

参考测试见 [AlgodResponses.java](evidence/8d089ce97868b988d5d0/reference/src/test/java/com/algorand/algosdk/unit/AlgodResponses.java)、[IndexerResponses.java](evidence/8d089ce97868b988d5d0/reference/src/test/java/com/algorand/algosdk/unit/IndexerResponses.java)、[ResponsesShared.java](evidence/8d089ce97868b988d5d0/reference/src/test/java/com/algorand/algosdk/unit/ResponsesShared.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/seo/seo.feature:15


`E` / `INSUFFICIENT_EVIDENCE`。原实现 `passed`，杀死29/37，存活8，drop 0。

```gherkin
  In order to make my catalog more findable
  I want to create a new product and add SEO Informations
  Scenario: Create a new product with a name and a meta title
    Given the site has a product "Shoe"
    And the products meta title is "Blue Shoe"
    Then the product should have meta title "Blue Shoe"
```

真实保存Product并调用updateSeoMetadata，但只读product.getMetaTitle。参考同时检查headTitle渲染字符串。需求只写product should have meta title，是否必须检查页面head不能仅由参考扩展推出。保留观察边界候选，暂不计入确认缺口。

生成代码见 [ProductSeoContext.php](evidence/0dad2d887ac70eb70971/generated/src/CoreShop/Behat/Context/Domain/Seo/ProductSeoContext.php)。

[实际逐步执行和调用](evidence/0dad2d887ac70eb70971/execution.json)；[参考基线调用](gold-execution/0dad2d887ac70eb70971.json)；[候选全部变异结果](evidence/0dad2d887ac70eb70971/mutation-results.json)；[存活修改](evidence/0dad2d887ac70eb70971/surviving-mutants.json)；[参考杀死标签](evidence/0dad2d887ac70eb70971/reference-kills.json)

参考测试见 [SEOContext.php](evidence/0dad2d887ac70eb70971/reference/src/CoreShop/Behat/Context/Domain/SEOContext.php)、[ProductContext.php](evidence/0dad2d887ac70eb70971/reference/src/CoreShop/Behat/Context/Setup/ProductContext.php)、[ProductContext.php](evidence/0dad2d887ac70eb70971/reference/src/CoreShop/Behat/Context/Transform/ProductContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/currency/money_formatter.feature:12


`A_setup` / `CONFIRMED_GAP`。原实现 `passed`，杀死3/15，存活12，drop 0。

```gherkin
  In order to displays currencies right, we need to format them properly
  Background:
    Given the site operates on a store in "Austria"
  Scenario: Format currency in USD for language de and en
    Given the site has a currency "USD" with iso "USD"
    And the site has a country "USA" with currency "USD"
    Then the amount "100" of currency "USD" in language "de" should be formatted "1,00 $"
    And the amount "100" of currency "USD" in language "en" should be formatted "$1.00"
```

Austria商店、USA国家背景步骤只检查输入或为空，未建立要求的实体状态。实际formatter.format及两个locale精确输出断言存在。确认背景准备缺失，但12个存活中的哪些影响格式化语义仍待定。 背景步骤未建立或核验所列状态；缺少初始数据库快照，不能断言环境中这些实体实际不存在。

生成代码见 [MoneyFormatterContext.php](evidence/16ee2db43ad5dc134696/generated/src/CoreShop/Behat/Context/Domain/Currency/MoneyFormatterContext.php)。

[实际逐步执行和调用](evidence/16ee2db43ad5dc134696/execution.json)；[参考基线调用](gold-execution/16ee2db43ad5dc134696.json)；[候选全部变异结果](evidence/16ee2db43ad5dc134696/mutation-results.json)；[存活修改](evidence/16ee2db43ad5dc134696/surviving-mutants.json)；[参考杀死标签](evidence/16ee2db43ad5dc134696/reference-kills.json)

参考测试见 [CurrencyContext.php](evidence/16ee2db43ad5dc134696/reference/src/CoreShop/Behat/Context/Domain/CurrencyContext.php)、[CountryContext.php](evidence/16ee2db43ad5dc134696/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)、[CurrencyContext.php](evidence/16ee2db43ad5dc134696/reference/src/CoreShop/Behat/Context/Setup/CurrencyContext.php)、[StoreContext.php](evidence/16ee2db43ad5dc134696/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)、[CurrencyContext.php](evidence/16ee2db43ad5dc134696/reference/src/CoreShop/Behat/Context/Transform/CurrencyContext.php)。

#### 对应生成代码位置


[MoneyFormatterContext.php](evidence/16ee2db43ad5dc134696/generated/src/CoreShop/Behat/Context/Domain/Currency/MoneyFormatterContext.php)


```text
   1 <?php
   2 
   3 declare(strict_types=1);
   4 
   5 namespace CoreShop\Behat\Context\Domain\Currency;
   6 
   7 use Behat\Behat\Context\Context;
   8 use CoreShop\Bundle\MoneyBundle\Formatter\MoneyFormatter;
   9 use CoreShop\Component\Currency\Model\Currency;
  10 use Webmozart\Assert\Assert;
  11 
  12 final class MoneyFormatterContext implements Context
  13 {
  14     public function __construct(private MoneyFormatter $formatter)
  15     {
  16     }
  17 
  18     /** @Given /^the site operates on a store in "([^"]+)"$/ */
  19     public function siteOperatesOnStoreIn(string $country): void
  20     {
  21         // Formatting is determined by the explicit locale and currency passed
  22         // to MoneyFormatter; store context does not participate.
  23         Assert::same($country, 'Austria');
  24     }
  25 
  26     /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
  27     public function siteHasCurrencyWithIso(string $code, string $iso): void
  28     {
  29         $currency = new Currency();
  30         $currency->setIsoCode($iso);
  31         Assert::same($currency->getIsoCode(), $code);
  32     }
  33 
  34     /** @Given /^the site has a country "([^"]+)" with currency "([^"]+)"$/ */
  35     public function siteHasCountryWithCurrency(string $country, string $currency): void
  36     {
  37         Assert::same($country, 'USA');
  38         Assert::same($currency, 'USD');
  39     }
  40 
  41     /** @Then /^the amount "([^"]+)" of currency "([^"]+)" in language "([^"]+)" should be formatted "([^"]+)"$/ */
  42     public function amountShouldBeFormatted(string $amount, string $currency, string $language, string $expected): void
  43     {
  44         Assert::same($this->formatter->format((int) $amount, $currency, $language), $expected);
  45     }
  46 }
```

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/filter/create_filter.feature:10


`A_setup` / `CONFIRMED_GAP`。原实现 `passed`，杀死2/56，存活54，drop 0。

```gherkin
  In order to make my catalog searchable
  I want to create a new index with an filter and add conditions
  Background:
    Given the site operates on a store in "Austria"
    And the site has a product "Shoe" priced at 100
  Scenario: Create a new filter
    Given the site has a index "myindex" for class "CoreShopProduct" with type "mysql"
    And the site has a filter "myfilter" for index "myindex"
    Then there should be a filter with name "myfilter"
```

商店、商品背景步骤为空。实际Index/Filter持久化并按名字重新查询存在。参考saveIndex还调用worker.createOrUpdateIndexStructures。确认背景义务缺失；物理索引是否构成本场景必要义务及54个存活逐项归因仍待定。 背景步骤未建立或核验所列状态；缺少初始数据库快照，不能断言环境中这些实体实际不存在。

生成代码见 [behat_services.yml](evidence/69bf8ff92073d12c569a/generated/behat_services.yml)、[CreateFilterContext.php](evidence/69bf8ff92073d12c569a/generated/src/CoreShop/Behat/Context/Domain/Filter/CreateFilterContext.php)。

[实际逐步执行和调用](evidence/69bf8ff92073d12c569a/execution.json)；[参考基线调用](gold-execution/69bf8ff92073d12c569a.json)；[候选全部变异结果](evidence/69bf8ff92073d12c569a/mutation-results.json)；[存活修改](evidence/69bf8ff92073d12c569a/surviving-mutants.json)；[参考杀死标签](evidence/69bf8ff92073d12c569a/reference-kills.json)

参考测试见 [FilterContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Domain/FilterContext.php)、[FilterContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Setup/FilterContext.php)、[IndexContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Setup/IndexContext.php)、[ProductContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Setup/ProductContext.php)、[StoreContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)、[IndexContext.php](evidence/69bf8ff92073d12c569a/reference/src/CoreShop/Behat/Context/Transform/IndexContext.php)。

#### 对应生成代码位置


[behat_services.yml](evidence/69bf8ff92073d12c569a/generated/behat_services.yml)


```text
   1 services:
   2   CoreShop\Behat\Context\Domain\Filter\CreateFilterContext:
   3     arguments:
   4       $indexRepository: '@coreshop.repository.index'
   5       $filterRepository: '@coreshop.repository.filter'
   6       $sharedStorage: '@coreshop.behat.shared_storage'
```

[CreateFilterContext.php](evidence/69bf8ff92073d12c569a/generated/src/CoreShop/Behat/Context/Domain/Filter/CreateFilterContext.php)


```text
   1 <?php
   2 
   3 declare(strict_types=1);
   4 
   5 namespace CoreShop\Behat\Context\Domain\Filter;
   6 
   7 use Behat\Behat\Context\Context;
   8 use CoreShop\Component\Index\Model\Filter;
   9 use CoreShop\Component\Index\Model\Index;
  10 use CoreShop\Component\Resource\Repository\RepositoryInterface;
  11 use CoreShop\Bundle\TestBundle\Service\SharedStorageInterface;
  12 use Webmozart\Assert\Assert;
  13 
  14 final class CreateFilterContext implements Context
  15 {
  16     public function __construct(
  17         private RepositoryInterface $indexRepository,
  18         private RepositoryInterface $filterRepository,
  19         private SharedStorageInterface $sharedStorage,
  20     ) {
  21     }
  22 
  23     /** @Given /^the site operates on a store in "([^"]+)"$/ */
  24     public function siteOperatesOnStore(string $country): void
  25     {
  26         // Index/filter creation in this scenario is independent of store setup.
  27     }
  28 
  29     /** @Given /^the site has a product "([^"]+)" priced at (\d+)$/ */
  30     public function siteHasProduct(string $name, int $price): void
  31     {
  32         // No product is consumed by this scenario's index/filter operations.
  33     }
  34 
  35     /** @Given /^the site has a index "([^"]+)" for class "([^"]+)" with type "([^"]+)"$/ */
  36     public function siteHasIndex(string $name, string $class, string $type): void
  37     {
  38         $index = new Index();
  39         $index->setName($name);
  40         $index->setClass($class);
  41         $index->setWorker($type);
  42         $this->indexRepository->add($index);
  43         $this->sharedStorage->set('index', $index);
  44     }
  45 
  46     /** @Given /^the site has a filter "([^"]+)" for index "([^"]+)"$/ */
  47     public function siteHasFilter(string $name, string $indexName): void
  48     {
  49         $index = $this->indexRepository->findOneBy(['name' => $indexName]);
  50         Assert::notNull($index, sprintf('Index "%s" was not found.', $indexName));
  51 
  52         $filter = new Filter();
  53         $filter->setName($name);
  54         $filter->setIndex($index);
  55         $this->filterRepository->add($filter);
  56         $this->sharedStorage->set('filter', $filter);
  57     }
  58 
  59     /** @Then /^there should be a filter with name "([^"]+)"$/ */
  60     public function filterShouldExist(string $name): void
  61     {
  62         $filter = $this->filterRepository->findOneBy(['name' => $name]);
  63         Assert::notNull($filter, sprintf('Filter "%s" was not found.', $name));
  64         Assert::same($name, $filter->getName());
  65     }
  66 }
```

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/cli/install_demo_data_command.feature:7


`E` / `INSUFFICIENT_EVIDENCE`。原实现 `passed`，杀死240/243，存活3，drop 0。

```gherkin
    In order to have sample data in CoreShop
    As a Developer
    I want to run a command that loads sample data
    Scenario: Running install sample data command
        When I run CoreShop Install Fixtures Data command
        And I confirm loading Fixtures Data command
        And I run CoreShop Install Demo Data command
        And I confirm loading Demo Data command
        Then the command should finish successfully
```

真实执行fixtures/demo命令，但使用--no-interaction，确认步骤只检查前次退出码。参考setInputs(['y'])后execute。存活包括--append true→false及configure删除。确认交互路径不同；无逐变异交互记录，不能将三项存活统称业务操作未执行。

生成代码见 [InstallDemoDataCommandContext.php](evidence/8280bb01841ddb55b184/generated/src/CoreShop/Behat/Context/Domain/Cli/InstallDemoDataCommandContext.php)。

[实际逐步执行和调用](evidence/8280bb01841ddb55b184/execution.json)；[参考基线调用](gold-execution/8280bb01841ddb55b184.json)；[候选全部变异结果](evidence/8280bb01841ddb55b184/mutation-results.json)；[存活修改](evidence/8280bb01841ddb55b184/surviving-mutants.json)；[参考杀死标签](evidence/8280bb01841ddb55b184/reference-kills.json)

参考测试见 [InstallerContext.php](evidence/8280bb01841ddb55b184/reference/src/CoreShop/Behat/Context/Cli/InstallerContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/cart/rules/voucher_code_generation.feature:9


`A_setup` / `CONFIRMED_GAP`。原实现 `passed`，杀死5/21，存活16，drop 0。

```gherkin
  Background:
    Given the site operates on a store in "Austria"
    And the site has a currency "Euro" with iso "EUR"
    And I am in country "Austria"
  Scenario: Add a new voucher rule with generated codes
    Given adding a cart price rule named "codes"
    When I want to generate 100 codes with a length of 1 in alphanumeric characters for the cart rule
    Then the generation of the codes failed
```

商店、国家、币种背景为空。真实CartPriceRule/Generator设置及isGenerationPossible(false)检查存在。参考同样通过checker核验不可能生成，故不要求额外调用实际generate。确认背景准备缺口，主要目标行为已被实际检查。 背景步骤未建立或核验所列状态；缺少初始数据库快照，不能断言环境中这些实体实际不存在。

生成代码见 [VoucherCodeGenerationContext.php](evidence/9bbc86b22783a2681bce/generated/src/CoreShop/Behat/Context/Domain/Cart/Rule/VoucherCodeGenerationContext.php)。

[实际逐步执行和调用](evidence/9bbc86b22783a2681bce/execution.json)；[参考基线调用](gold-execution/9bbc86b22783a2681bce.json)；[候选全部变异结果](evidence/9bbc86b22783a2681bce/mutation-results.json)；[存活修改](evidence/9bbc86b22783a2681bce/surviving-mutants.json)；[参考杀死标签](evidence/9bbc86b22783a2681bce/reference-kills.json)

参考测试见 [CartPriceRuleVoucherCodeContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Domain/CartPriceRuleVoucherCodeContext.php)、[ActionFormTrait.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/ActionFormTrait.php)、[CartPriceRuleContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/CartPriceRuleContext.php)、[CartPriceRuleVoucherCodeContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/CartPriceRuleVoucherCodeContext.php)、[ConditionFormTrait.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/ConditionFormTrait.php)、[CountryContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)、[CurrencyContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/CurrencyContext.php)、[StoreContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)、[CartPriceRuleContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Transform/CartPriceRuleContext.php)、[CountryContext.php](evidence/9bbc86b22783a2681bce/reference/src/CoreShop/Behat/Context/Transform/CountryContext.php)。

#### 对应生成代码位置


[VoucherCodeGenerationContext.php](evidence/9bbc86b22783a2681bce/generated/src/CoreShop/Behat/Context/Domain/Cart/Rule/VoucherCodeGenerationContext.php)


```text
   1 <?php
   2 
   3 declare(strict_types=1);
   4 
   5 namespace CoreShop\Behat\Context\Domain\Cart\Rule;
   6 
   7 use Behat\Behat\Context\Context;
   8 use CoreShop\Component\Order\Generator\CodeGeneratorCheckerInterface;
   9 use CoreShop\Component\Order\Model\CartPriceRule;
  10 use CoreShop\Component\Order\Model\CartPriceRuleVoucherGenerator;
  11 use Webmozart\Assert\Assert;
  12 
  13 final class VoucherCodeGenerationContext implements Context
  14 {
  15     private ?CartPriceRule $rule = null;
  16     private ?CartPriceRuleVoucherGenerator $generator = null;
  17 
  18     public function __construct(private CodeGeneratorCheckerInterface $checker)
  19     {
  20     }
  21 
  22     /** @Given /^the site operates on a store in "([^"]+)"$/ */
  23     public function storeInCountry(string $country): void
  24     {
  25     }
  26 
  27     /** @Given /^the site has a currency "([^"]+)" with iso "([^"]+)"$/ */
  28     public function currency(string $name, string $iso): void
  29     {
  30     }
  31 
  32     /** @Given /^I am in country "([^"]+)"$/ */
  33     public function inCountry(string $country): void
  34     {
  35     }
  36 
  37     /** @Given /^adding a cart price rule named "([^"]+)"$/ */
  38     public function addingCartPriceRule(string $name): void
  39     {
  40         $this->rule = new CartPriceRule();
  41         $this->rule->setName($name);
  42     }
  43 
  44     /** @When /^I want to generate (\d+) codes with a length of (\d+) in ([a-z]+) characters for the cart rule$/ */
  45     public function configureGeneration(int $amount, int $length, string $format): void
  46     {
  47         Assert::notNull($this->rule, 'A cart price rule must be created first.');
  48 
  49         $this->generator = new CartPriceRuleVoucherGenerator();
  50         $this->generator->setAmount($amount);
  51         $this->generator->setLength($length);
  52         $this->generator->setFormat($format);
  53         $this->generator->setPrefix('');
  54         $this->generator->setCartPriceRule($this->rule);
  55     }
  56 
  57     /** @Then /^the generation of the codes failed$/ */
  58     public function generationFailed(): void
  59     {
  60         Assert::notNull($this->generator, 'Generation parameters must be configured first.');
  61         Assert::false($this->checker->isGenerationPossible($this->generator));
  62     }
  63 }
```

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/admin/anonymize_petitions.feature:18


`B` / `CONFIRMED_GAP`。原实现 `passed`，杀死95/110，存活15，drop 0。

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

生成代码见 [admin_anonymize_petitions_steps.rb](evidence/03cfd691e00da6e9f8a9/generated/features/step_definitions/admin_anonymize_petitions_steps.rb)。

[实际逐步执行和调用](evidence/03cfd691e00da6e9f8a9/execution.json)；[参考基线调用](gold-execution/03cfd691e00da6e9f8a9.json)；[候选全部变异结果](evidence/03cfd691e00da6e9f8a9/mutation-results.json)；[存活修改](evidence/03cfd691e00da6e9f8a9/surviving-mutants.json)；[参考杀死标签](evidence/03cfd691e00da6e9f8a9/reference-kills.json)

参考测试见 [authentication_steps.rb](evidence/03cfd691e00da6e9f8a9/reference/features/step_definitions/authentication_steps.rb)、[web_steps.rb](evidence/03cfd691e00da6e9f8a9/reference/features/step_definitions/web_steps.rb)。

#### 对应生成代码位置


[admin_anonymize_petitions_steps.rb](evidence/03cfd691e00da6e9f8a9/generated/features/step_definitions/admin_anonymize_petitions_steps.rb)


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

代表变异 `e9639a04a50dc1ac`，`app/models/admin_user.rb` 第46行。

```diff
- find_or_initialize_by(email: email).tap do |user|
          user.first_name = auth_data.info.fetch(:first_name)
          user.last_name = auth_data.info.fetch(:last_name)

          if (groups & provider.sysadmin).any?
            user.role = SYSADMIN_ROLE
          elsif (groups & provider.moderator).any?
            user.role = MODERATOR_ROLE
          elsif (groups & provider.reviewer).any?
            user.role = REVIEWER_ROLE
          end

          user.save!
        end
+ nil
```

相关生产源码 [admin_controller.rb](source-context/e-petitions/app/controllers/admin/admin_controller.rb)、[omniauth_callbacks_controller.rb](source-context/e-petitions/app/controllers/admin/omniauth_callbacks_controller.rb)、[admin_user.rb](source-context/e-petitions/app/models/admin_user.rb)、[browseable.rb](source-context/e-petitions/app/models/concerns/browseable.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/admin/admin_hub.feature:52


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死212/215，存活3，drop 0。

```gherkin
  In order to help administrators see the next actions they need to take
  As any moderator user
  I want to view a page which lists totals for actionable list and links to them
  Background:
    Given I am logged in as a moderator
  Scenario: I can click through to see lists of matching petitions
    Given 12 petitions exist with state: "sponsored"
    When I go to the Admin home page
    And I follow "12 Moderation queue"
    Then I should be on the Admin all petitions page
```

真实moderator表单登录、建立12条sponsored petitions、点击链接并核验当前路径。三项存活主要是登录layout/flash/defaultURL差异。目标导航已执行并观察。

生成代码见 [admin_hub_steps.rb](evidence/3bcfc97a0c899ca20799/generated/features/step_definitions/admin_hub_steps.rb)。

[实际逐步执行和调用](evidence/3bcfc97a0c899ca20799/execution.json)；[参考基线调用](gold-execution/3bcfc97a0c899ca20799.json)；[候选全部变异结果](evidence/3bcfc97a0c899ca20799/mutation-results.json)；[存活修改](evidence/3bcfc97a0c899ca20799/surviving-mutants.json)；[参考杀死标签](evidence/3bcfc97a0c899ca20799/reference-kills.json)

参考测试见 [authentication_steps.rb](evidence/3bcfc97a0c899ca20799/reference/features/step_definitions/authentication_steps.rb)、[pickle_steps.rb](evidence/3bcfc97a0c899ca20799/reference/features/step_definitions/pickle_steps.rb)、[web_steps.rb](evidence/3bcfc97a0c899ca20799/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/admin/all_petitions.feature:109


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死209/217，存活8，drop 0。

```gherkin
  In order to see a full list of all the petitions
  As any moderator user
  I want to view a paginated list of Open, Rejected and Closed petitions, sorted by signature count (descending), then most recent. I want to be able to filter this list by state and follow links to change petition details.
  Background:
    Given I am logged in as a moderator
  Scenario: A sysadmin can view all petitions
    Given I log out and login back in as a sysadmin
    And an open petition exists with action: "Simply the best"
    When I view all petitions
    Then I should see "Simply the best"
```

实际切换moderator/sysadmin并创建及访问列表，检查正向内容。八项存活在认证准备路径；缺少逐变异状态证据，不能从存活推出权限验证失败。

生成代码见 [all_petitions_steps.rb](evidence/5c58a6af84cff1f407ef/generated/features/step_definitions/all_petitions_steps.rb)。

[实际逐步执行和调用](evidence/5c58a6af84cff1f407ef/execution.json)；[参考基线调用](gold-execution/5c58a6af84cff1f407ef.json)；[候选全部变异结果](evidence/5c58a6af84cff1f407ef/mutation-results.json)；[存活修改](evidence/5c58a6af84cff1f407ef/surviving-mutants.json)；[参考杀死标签](evidence/5c58a6af84cff1f407ef/reference-kills.json)

参考测试见 [authentication_steps.rb](evidence/5c58a6af84cff1f407ef/reference/features/step_definitions/authentication_steps.rb)、[moderation_steps.rb](evidence/5c58a6af84cff1f407ef/reference/features/step_definitions/moderation_steps.rb)、[pickle_steps.rb](evidence/5c58a6af84cff1f407ef/reference/features/step_definitions/pickle_steps.rb)、[web_steps.rb](evidence/5c58a6af84cff1f407ef/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/arnold_searches_from_home_page.feature:39


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死174/178，存活4，drop 0。

```gherkin
  In order to reduce the likelihood of a duplicate petition being made
  As a petition moderator
  I want to prominently show a petition search for the current parliament from the home page
Background:
    Given a pending petition exists with action: "Wombles are great"
    And a validated petition exists with action: "The Wombles of Wimbledon"
    And an open petition exists with action: "Uncle Bulgaria", additional_details: "The Wombles are here", closed_at: "1 minute from now", signature_count: 23
    And an open petition exists with action: "Common People", background: "The Wombles belong to us all", closed_at: "11 days from now", signature_count: 19
    And an open petition exists with action: "Overthrow the Wombles", closed_at: "3 months from now", signature_count: 17
    And a closed petition exists with action: "The Wombles will rock Glasto", closed_at: "1 minute ago", signature_count: 9
    And a rejected petition exists with action: "Eavis vs the Wombles"
    And a hidden petition exists with action: "The Wombles are profane"
    And an open petition exists with action: "Wombles", closed_at: "10 days from now", signature_count: 13
    And the following archived petitions exist:
      | action                   | state    | signature_count | opened_at  | closed_at  | created_at |
      | Rivers are great         | closed   | 835             | 2012-01-01 | 2013-01-01 | 2012-01-01 |
      | More rivers please       | closed   | 243             | 2011-04-01 | 2012-04-01 | 2011-04-01 |
      | Cry me a river           | closed   | 639             | 2014-10-01 | 2015-03-31 | 2014-10-01 |
      | Also Rivers              | rejected | 6               |            |            | 2011-01-01 |
      | River Island             | hidden   |                 |            |            | 2011-01-01 |
Scenario: Arnold searches for petitions by id
  Given I am on the home page
  When I search all petitions using the id of the petition "Uncle Bulgaria"
  Then I should be on the petition page for "Uncle Bulgaria"
```

真实建立场景数据并搜索ID，精确核验对应petition路径。四项存活在邮箱规范化与日期比较，尚无明确核心搜索需求缺口。

生成代码见 [arnold_searches_from_home_page_steps.rb](evidence/65b8816a3476e2107994/generated/features/step_definitions/arnold_searches_from_home_page_steps.rb)。

[实际逐步执行和调用](evidence/65b8816a3476e2107994/execution.json)；[参考基线调用](gold-execution/65b8816a3476e2107994.json)；[候选全部变异结果](evidence/65b8816a3476e2107994/mutation-results.json)；[存活修改](evidence/65b8816a3476e2107994/surviving-mutants.json)；[参考杀死标签](evidence/65b8816a3476e2107994/reference-kills.json)

参考测试见 [petition_steps.rb](evidence/65b8816a3476e2107994/reference/features/step_definitions/petition_steps.rb)、[pickle_steps.rb](evidence/65b8816a3476e2107994/reference/features/step_definitions/pickle_steps.rb)、[web_steps.rb](evidence/65b8816a3476e2107994/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/joe_searches_for_an_archived_petition.feature:15


`C` / `CONFIRMED_GAP`。原实现 `passed`，杀死100/101，存活1，drop 0。

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

生成代码见 [archived_petition_search_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/generated/features/step_definitions/archived_petition_search_steps.rb)。

[实际逐步执行和调用](evidence/6cfa5ed7b21c9e5ebb77/execution.json)；[参考基线调用](gold-execution/6cfa5ed7b21c9e5ebb77.json)；[候选全部变异结果](evidence/6cfa5ed7b21c9e5ebb77/mutation-results.json)；[存活修改](evidence/6cfa5ed7b21c9e5ebb77/surviving-mutants.json)；[参考杀死标签](evidence/6cfa5ed7b21c9e5ebb77/reference-kills.json)

参考测试见 [inspection_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/inspection_steps.rb)、[pickle_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/pickle_steps.rb)、[validation_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/validation_steps.rb)、[web_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/reference/features/step_definitions/web_steps.rb)。

#### 对应生成代码位置


[archived_petition_search_steps.rb](evidence/6cfa5ed7b21c9e5ebb77/generated/features/step_definitions/archived_petition_search_steps.rb)


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

代表变异 `4639544fe90a683c`，`app/models/concerns/browseable.rb` 第204行。

```diff
- query.present?
+ nil
```

相关生产源码 [admin_controller.rb](source-context/e-petitions/app/controllers/admin/admin_controller.rb)、[omniauth_callbacks_controller.rb](source-context/e-petitions/app/controllers/admin/omniauth_callbacks_controller.rb)、[admin_user.rb](source-context/e-petitions/app/models/admin_user.rb)、[browseable.rb](source-context/e-petitions/app/models/concerns/browseable.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/sty-latent-props.feature:41


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死104/112，存活8，drop 0。

```gherkin
  In order to adjust latent style properties to suit my needs
  As a developer using python-docx
  I need a set of read/write latent style properties
  Scenario Outline: Get latent style display sort order
    Given a latent style having priority of <setting>
     Then latent_style.priority is <value>

    Examples: latent_style.priority values
      | setting    | value |
      | no setting | None  |
      | 42         | 42    |
```

构建latent style，设置priority 42或None并精确读取。参考从已有文档检索样式；八项存活在检索/包读取路径。未确认语义义务缺失。

生成代码见 [sty_latent_props.py](evidence/04a93f7670880967619a/generated/features/steps/sty_latent_props.py)。

[实际逐步执行和调用](evidence/04a93f7670880967619a/execution.json)；[参考基线调用](gold-execution/04a93f7670880967619a.json)；[候选全部变异结果](evidence/04a93f7670880967619a/mutation-results.json)；[存活修改](evidence/04a93f7670880967619a/surviving-mutants.json)；[参考杀死标签](evidence/04a93f7670880967619a/reference-kills.json)

参考测试见 [helpers.py](evidence/04a93f7670880967619a/reference/features/steps/helpers.py)、[styles.py](evidence/04a93f7670880967619a/reference/features/steps/styles.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/hdr-header-footer.feature:72


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死120/121，存活1，drop 0。

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

生成代码见 [footer_inherits_content.py](evidence/056dd0dc42a69a6e107b/generated/features/steps/footer_inherits_content.py)。

[实际逐步执行和调用](evidence/056dd0dc42a69a6e107b/execution.json)；[参考基线调用](gold-execution/056dd0dc42a69a6e107b.json)；[候选全部变异结果](evidence/056dd0dc42a69a6e107b/mutation-results.json)；[存活修改](evidence/056dd0dc42a69a6e107b/surviving-mutants.json)；[参考杀死标签](evidence/056dd0dc42a69a6e107b/reference-kills.json)

参考测试见 [hdrftr.py](evidence/056dd0dc42a69a6e107b/reference/features/steps/hdrftr.py)、[helpers.py](evidence/056dd0dc42a69a6e107b/reference/features/steps/helpers.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/cmt-props.feature:22


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死104/115，存活11，drop 0。

```gherkin
  In order to characterize comments by their metadata
  As a developer using python-docx
  I need methods to access comment metadata properties
  Scenario: Comment.timestamp
    Given a Comment object
     Then comment.timestamp is the date and time the comment was authored
```

实际add_comment，设置已知XML日期并读取timestamp精确比较。参考加载含更多内容的文档。11项存活的附加图像/检索路径不自动成为时间戳需求遗漏。

生成代码见 [cmt_props.py](evidence/067bc7e12bcd4644fab3/generated/features/steps/cmt_props.py)。

[实际逐步执行和调用](evidence/067bc7e12bcd4644fab3/execution.json)；[参考基线调用](gold-execution/067bc7e12bcd4644fab3.json)；[候选全部变异结果](evidence/067bc7e12bcd4644fab3/mutation-results.json)；[存活修改](evidence/067bc7e12bcd4644fab3/surviving-mutants.json)；[参考杀死标签](evidence/067bc7e12bcd4644fab3/reference-kills.json)

参考测试见 [comments.py](evidence/067bc7e12bcd4644fab3/reference/features/steps/comments.py)、[helpers.py](evidence/067bc7e12bcd4644fab3/reference/features/steps/helpers.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/cmt-props.feature:33


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死132/192，存活60，drop 0。

```gherkin
  In order to characterize comments by their metadata
  As a developer using python-docx
  I need methods to access comment metadata properties
  Scenario: Retrieve embedded image from a comment
    Given a Comment object containing an embedded image
     Then I can extract the image from the comment
```

真实添加PNG、遍历drawing/image，检查has_picture、PNG类型、filename和sha1形状。参考为JPEG和更复杂文档，60项存活含JPEG解码及包加载。完整字节保真可能值得另查，但当前需求没有指定字节级比较，暂不确认缺口。

生成代码见 [cmt_props.py](evidence/084ecf53bb3c8fdfe96e/generated/features/steps/cmt_props.py)。

[实际逐步执行和调用](evidence/084ecf53bb3c8fdfe96e/execution.json)；[参考基线调用](gold-execution/084ecf53bb3c8fdfe96e.json)；[候选全部变异结果](evidence/084ecf53bb3c8fdfe96e/mutation-results.json)；[存活修改](evidence/084ecf53bb3c8fdfe96e/surviving-mutants.json)；[参考杀死标签](evidence/084ecf53bb3c8fdfe96e/reference-kills.json)

参考测试见 [comments.py](evidence/084ecf53bb3c8fdfe96e/reference/features/steps/comments.py)、[helpers.py](evidence/084ecf53bb3c8fdfe96e/reference/features/steps/helpers.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/tab-access-tabs.feature:7


`N` / `NO_CONFIRMED_GAP`。原实现 `passed`，杀死105/107，存活2，drop 0。

```gherkin
  In order to interact with an individual tab stop for a paragraph or style
  As a developer using python-docx
  I need methods to create, access, and remove a tab stop
  Scenario Outline: TabStops.__len__
    Given a tab_stops having <count> tab stops
     Then len(tab_stops) is <count>

    Examples: tab_stop counts
      | count |
      |   0   |
      |   3   |
```

实际添加0/3个tab后精确检查长度。两个存活属于其他段落集合读取路径，当前义务已有对应断言。

生成代码见 [tabstops_steps.py](evidence/09cb007b6ad7f3eede22/generated/features/steps/tabstops_steps.py)。

[实际逐步执行和调用](evidence/09cb007b6ad7f3eede22/execution.json)；[参考基线调用](gold-execution/09cb007b6ad7f3eede22.json)；[候选全部变异结果](evidence/09cb007b6ad7f3eede22/mutation-results.json)；[存活修改](evidence/09cb007b6ad7f3eede22/surviving-mutants.json)；[参考杀死标签](evidence/09cb007b6ad7f3eede22/reference-kills.json)

参考测试见 [helpers.py](evidence/09cb007b6ad7f3eede22/reference/features/steps/helpers.py)、[tabstops.py](evidence/09cb007b6ad7f3eede22/reference/features/steps/tabstops.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

## 15条KillComplete对照


自动配对中同feature为4/15，同scenario kind为13/15。后者只表示场景语法形式相同。全部同项目，但不能据此视为需求难度匹配。

### algorand-sdk/features/unit/tealsign.feature:15


`N` / `CONTROL`。原实现 `passed`，杀死111/111，存活0，drop 0。

```gherkin
  Scenario Outline: Tealsign data using program bytes and mnemonic
    Given base64 encoded data to sign "<data>"
    And base64 encoded program "<program>"
    And mnemonic for private key "<mn>"
    When I perform tealsign
    Then the signature should be equal to "<golden>"

    Examples:
      | data                 | program  | mn                                                                                                                                                             | golden                                                                                   |
      | Ux8jntyBJQarjKGF8A== | ASABASI= | wish used round alert sock survey mind dilemma giraffe usage hockey thing rifle trim swim fault sort denial phrase century hundred shoulder chat absent nation | lKvoxpnatNLbjJs5iGWwXK144AYlIpEVe+S7A8VcKVDMktGlhxJD2M0kz2cFTeN9xnna4DsSCPCS5hHmV2qXDA== |
```

真实账户/tealsign及精确签名字节比较。与程序sanity同属加密SDK操作，义务类型匹配弱。

配对任务 `algorand-sdk/features/unit/program_sanity_check.feature:3`。同feature=False，同scenario kind=True，标题Jaccard=0.176。匹配限制见上面的语义说明。

生成代码见 [TealsignSteps.java](evidence/fdc12e8888edc5e37221/generated/src/test/java/com/algorand/algosdk/unit/TealsignSteps.java)。

[实际逐步执行和调用](evidence/fdc12e8888edc5e37221/execution.json)；[参考基线调用](gold-execution/fdc12e8888edc5e37221.json)；[候选全部变异结果](evidence/fdc12e8888edc5e37221/mutation-results.json)；[存活修改](evidence/fdc12e8888edc5e37221/surviving-mutants.json)；[参考杀死标签](evidence/fdc12e8888edc5e37221/reference-kills.json)

参考测试见 [Rekeying.java](evidence/fdc12e8888edc5e37221/reference/src/test/java/com/algorand/algosdk/unit/Rekeying.java)、[TealSign.java](evidence/fdc12e8888edc5e37221/reference/src/test/java/com/algorand/algosdk/unit/TealSign.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/taxation/adding_tax.feature:10


`N` / `CONTROL`。原实现 `passed`，杀死15/15，存活0，drop 0。

```gherkin
  In Order to tax my products
  I want to create a new tax rate
  Scenario: Create a new tax rate and set it active
    Given the site has a tax rate "AT" with "20%" rate
    And the tax rate "AT" is active
    Then there should be a tax rate "AT" with "20%" rate
```

真实TaxRate实体保存、按名称重查、rate精确断言。与SEO只有实体属性设置相近，不能作为同一渲染边界控制。

配对任务 `coreshop/features/domain/seo/seo.feature:15`。同feature=False，同scenario kind=True，标题Jaccard=0.286。匹配限制见上面的语义说明。

生成代码见 [behat_services.yml](evidence/d7253388ffec908a8a46/generated/behat_services.yml)、[AddingTaxContext.php](evidence/d7253388ffec908a8a46/generated/src/CoreShop/Behat/Context/Domain/Taxation/AddingTaxContext.php)。

[实际逐步执行和调用](evidence/d7253388ffec908a8a46/execution.json)；[参考基线调用](gold-execution/d7253388ffec908a8a46.json)；[候选全部变异结果](evidence/d7253388ffec908a8a46/mutation-results.json)；[存活修改](evidence/d7253388ffec908a8a46/surviving-mutants.json)；[参考杀死标签](evidence/d7253388ffec908a8a46/reference-kills.json)

参考测试见 [TaxRateContext.php](evidence/d7253388ffec908a8a46/reference/src/CoreShop/Behat/Context/Domain/TaxRateContext.php)、[TaxRateContext.php](evidence/d7253388ffec908a8a46/reference/src/CoreShop/Behat/Context/Setup/TaxRateContext.php)、[TaxRateContext.php](evidence/d7253388ffec908a8a46/reference/src/CoreShop/Behat/Context/Transform/TaxRateContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/suzie_sees_trending_petitions.feature:6


`N` / `CONTROL`。原实现 `passed`，杀死49/49，存活0，drop 0。

```gherkin
  In order to make the site more engaging for browsing
  As Suzie the signer
  I want to see the most active petitions on the front page
  Scenario: There are no trending petitions
    Given I am on the home page
    Then I should not see the trending petitions section
```

真实访问首页后否定trending文本。与admin案例同属否定UI检查，缺少登录条件；KillComplete不能证明负向预言能区分错误页面。

配对任务 `e-petitions/features/admin/anonymize_petitions.feature:18`。同feature=False，同scenario kind=True，标题Jaccard=0.250。匹配限制见上面的语义说明。

生成代码见 [suzie_sees_trending_petitions_steps.rb](evidence/fe9e2546002a1ead06c8/generated/features/step_definitions/suzie_sees_trending_petitions_steps.rb)。

[实际逐步执行和调用](evidence/fe9e2546002a1ead06c8/execution.json)；[参考基线调用](gold-execution/fe9e2546002a1ead06c8.json)；[候选全部变异结果](evidence/fe9e2546002a1ead06c8/mutation-results.json)；[存活修改](evidence/fe9e2546002a1ead06c8/surviving-mutants.json)；[参考杀死标签](evidence/fe9e2546002a1ead06c8/reference-kills.json)

参考测试见 [trending_steps.rb](evidence/fe9e2546002a1ead06c8/reference/features/step_definitions/trending_steps.rb)、[web_steps.rb](evidence/fe9e2546002a1ead06c8/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/sty-latent-props.feature:7


`N` / `CONTROL`。原实现 `passed`，杀死107/107，存活0，drop 0。

```gherkin
  In order to adjust latent style properties to suit my needs
  As a developer using python-docx
  I need a set of read/write latent style properties
  Scenario Outline: Get default latent style properties
    Given a latent styles object with known defaults
     Then latent_styles.<prop-name> is <value>

    Examples: known latent_styles property values
      | prop-name                   | value |
      | default_priority            | 99    |
      | load_count                  | 276   |
      | default_to_hidden           | True  |
      | default_to_locked           | False |
      | default_to_quick_style      | False |
      | default_to_unhide_when_used | True  |
```

实际Document默认latent style读取六个具体属性。同feature属性义务匹配较强，默认状态与可选优先级有所不同。

配对任务 `python-docx/features/sty-latent-props.feature:41`。同feature=True，同scenario kind=True，标题Jaccard=0.375。匹配限制见上面的语义说明。

生成代码见 [latent_style_props.py](evidence/9192f0d5efbedd02f926/generated/features/steps/latent_style_props.py)。

[实际逐步执行和调用](evidence/9192f0d5efbedd02f926/execution.json)；[参考基线调用](gold-execution/9192f0d5efbedd02f926.json)；[候选全部变异结果](evidence/9192f0d5efbedd02f926/mutation-results.json)；[存活修改](evidence/9192f0d5efbedd02f926/surviving-mutants.json)；[参考杀死标签](evidence/9192f0d5efbedd02f926/reference-kills.json)

参考测试见 [helpers.py](evidence/9192f0d5efbedd02f926/reference/features/steps/helpers.py)、[styles.py](evidence/9192f0d5efbedd02f926/reference/features/steps/styles.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/tealsign.feature:37


`N` / `CONTROL`。原实现 `passed`，杀死37/37，存活0，drop 0。

```gherkin
  Scenario Outline: Tealsign data using contract address and private key bytes
    Given base64 encoded data to sign "<data>"
    And program hash "<hash>"
    And base64 encoded private key "<key>"
    When I perform tealsign
    Then the signature should be equal to "<golden>"

    Examples:
      | data                 | hash                                                       | key                                          | golden                                                                                   |
      | Ux8jntyBJQarjKGF8A== | 6Z3C3LDVWGMX23BMSYMANACQOSINPFIRF77H7N3AWJZYV6OH6GWTJKVMXY | 5Pf7eGMA52qfMT4R4/vYCt7con/7U3yejkdXkrcb26Q= | lKvoxpnatNLbjJs5iGWwXK144AYlIpEVe+S7A8VcKVDMktGlhxJD2M0kz2cFTeN9xnna4DsSCPCS5hHmV2qXDA== |
```

真实私钥/合约地址和tealsign，精确签名检查。与indexer响应类型匹配弱。

配对任务 `algorand-sdk/features/unit/v2indexerclient_responses.feature:55`。同feature=False，同scenario kind=True，标题Jaccard=-0.000。匹配限制见上面的语义说明。

生成代码见 [TealSignSteps.java](evidence/00dde303da73b0b7d185/generated/src/test/java/com/algorand/algosdk/unit/TealSignSteps.java)。

[实际逐步执行和调用](evidence/00dde303da73b0b7d185/execution.json)；[参考基线调用](gold-execution/00dde303da73b0b7d185.json)；[候选全部变异结果](evidence/00dde303da73b0b7d185/mutation-results.json)；[存活修改](evidence/00dde303da73b0b7d185/surviving-mutants.json)；[参考杀死标签](evidence/00dde303da73b0b7d185/reference-kills.json)

参考测试见 [Rekeying.java](evidence/00dde303da73b0b7d185/reference/src/test/java/com/algorand/algosdk/unit/Rekeying.java)、[TealSign.java](evidence/00dde303da73b0b7d185/reference/src/test/java/com/algorand/algosdk/unit/TealSign.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/currency/exchange_rate.feature:9


`N` / `CONTROL`。原实现 `passed`，杀死25/25，存活0，drop 0。

```gherkin
  In Order to increase my sales
  I want to add a new currency with an exchange-rate
  Background:
    Given the site operates on a store in "Austria"
  Scenario: Create a new currency for country US
    Given the site has a currency "USD" with iso "USD"
    And the site has a country "USA" with currency "USD"
    And the currency has a exchange-rate to currency "EUR" of "1.1"
    Then price "100" of currency "USD" should exchange to price "110" in currency "EUR"
    Then price "100" of currency "EUR" should exchange to price "91" in currency "USD"
```

真实国家、商店、币种与汇率持久化，converter输出100→110及100→91。与money formatter同币种域，业务操作不同；提供准备状态有效建立的对照。

配对任务 `coreshop/features/domain/currency/money_formatter.feature:12`。同feature=False，同scenario kind=True，标题Jaccard=0.143。匹配限制见上面的语义说明。

生成代码见 [behat_services.yml](evidence/a78015ec5ff24fc9de78/generated/behat_services.yml)、[ExchangeRateContext.php](evidence/a78015ec5ff24fc9de78/generated/src/CoreShop/Behat/Context/Domain/Currency/ExchangeRateContext.php)。

[实际逐步执行和调用](evidence/a78015ec5ff24fc9de78/execution.json)；[参考基线调用](gold-execution/a78015ec5ff24fc9de78.json)；[候选全部变异结果](evidence/a78015ec5ff24fc9de78/mutation-results.json)；[存活修改](evidence/a78015ec5ff24fc9de78/surviving-mutants.json)；[参考杀死标签](evidence/a78015ec5ff24fc9de78/reference-kills.json)

参考测试见 [ExchangeRateContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Domain/ExchangeRateContext.php)、[CountryContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Setup/CountryContext.php)、[CurrencyContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Setup/CurrencyContext.php)、[ExchangeRateContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Setup/ExchangeRateContext.php)、[StoreContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Setup/StoreContext.php)、[CurrencyContext.php](evidence/a78015ec5ff24fc9de78/reference/src/CoreShop/Behat/Context/Transform/CurrencyContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/suzie_views_the_home_page.feature:6


`N` / `CONTROL`。原实现 `passed`，杀死49/49，存活0，drop 0。

```gherkin
  In order to explore the Petitions website
  As Suzy the signer
  I visit the home page
  Scenario: I navigate to the home page when petitions are collecting signatures
    Given petitions are collecting signatures
    When I go to the home page
    Then I should not see "Petitions have stopped collecting signatures"
```

真实首页访问和负向文本检查。与admin hub导航需求匹配弱。

配对任务 `e-petitions/features/admin/admin_hub.feature:52`。同feature=False，同scenario kind=True，标题Jaccard=0.167。匹配限制见上面的语义说明。

生成代码见 [home_page_steps.rb](evidence/34685f171763ee1cd820/generated/features/step_definitions/home_page_steps.rb)。

[实际逐步执行和调用](evidence/34685f171763ee1cd820/execution.json)；[参考基线调用](gold-execution/34685f171763ee1cd820.json)；[候选全部变异结果](evidence/34685f171763ee1cd820/mutation-results.json)；[存活修改](evidence/34685f171763ee1cd820/surviving-mutants.json)；[参考杀死标签](evidence/34685f171763ee1cd820/reference-kills.json)

参考测试见 [site_steps.rb](evidence/34685f171763ee1cd820/reference/features/step_definitions/site_steps.rb)、[web_steps.rb](evidence/34685f171763ee1cd820/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/hdr-header-footer.feature:49


`N` / `CONTROL`。原实现 `passed`，杀死95/95，存活0，drop 0。

```gherkin
  In order to control the appearance of page headers and footers
  As a developer using python-docx
  I need properties and methods on _Header and _Footer objects
  Scenario Outline: _Footer.is_linked_to_previous getter
    Given a _Footer object <with-or-no> footer definition as footer
     Then footer.is_linked_to_previous is <value>

    Examples: _Footer.is_linked_to_previous states
      | with-or-no | value |
      | with a     | False |
      | with no    | True  |
```

with a footer definition分支设置is_linked_to_previous=False形成定义，再精确读取布尔值。与页脚继承同feature，创建/查询和继承操作不同。

配对任务 `python-docx/features/hdr-header-footer.feature:72`。同feature=True，同scenario kind=False，标题Jaccard=0.125。匹配限制见上面的语义说明。

生成代码见 [hdr_footer.py](evidence/d5b689224c61c42ba2a9/generated/features/steps/hdr_footer.py)。

[实际逐步执行和调用](evidence/d5b689224c61c42ba2a9/execution.json)；[参考基线调用](gold-execution/d5b689224c61c42ba2a9.json)；[候选全部变异结果](evidence/d5b689224c61c42ba2a9/mutation-results.json)；[存活修改](evidence/d5b689224c61c42ba2a9/surviving-mutants.json)；[参考杀死标签](evidence/d5b689224c61c42ba2a9/reference-kills.json)

参考测试见 [hdrftr.py](evidence/d5b689224c61c42ba2a9/reference/features/steps/hdrftr.py)、[helpers.py](evidence/d5b689224c61c42ba2a9/reference/features/steps/helpers.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/offline.feature:10


`N` / `CONTROL`。原实现 `passed`，杀死104/104，存活0，drop 0。

```gherkin
  Scenario Outline: Mnemonic to and from private key
    Given mnemonic for private key "<mn>"
    When I convert the private key back to a mnemonic
    Then the mnemonic should still be the same as "<mn>"

    Examples:
      | mn                                                                                                                                                                   |
      | advice pudding treat near rule blouse same whisper inner electric quit surface sunny dismiss leader blood seat clown cost exist hospital century reform able sponsor |
```

真实助记词往返。与地址roundtrip同feature，但助记词在本控制中是明确目标，在对应nonkill中是参考额外准备。

配对任务 `algorand-sdk/features/unit/offline.feature:4`。同feature=True，同scenario kind=False，标题Jaccard=0.111。匹配限制见上面的语义说明。

生成代码见 [OfflineSteps.java](evidence/51363211341a39559766/generated/src/test/java/com/algorand/algosdk/unit/OfflineSteps.java)。

[实际逐步执行和调用](evidence/51363211341a39559766/execution.json)；[参考基线调用](gold-execution/51363211341a39559766.json)；[候选全部变异结果](evidence/51363211341a39559766/mutation-results.json)；[存活修改](evidence/51363211341a39559766/surviving-mutants.json)；[参考杀死标签](evidence/51363211341a39559766/reference-kills.json)

参考测试见 [Stepdefs.java](evidence/51363211341a39559766/reference/src/test/java/com/algorand/algosdk/integration/Stepdefs.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/menu/menu.feature:5


`N` / `CONTROL`。原实现 `passed`，杀死24/24，存活0，drop 0。

```gherkin
  we build the menu for CoreShop in PHP Services
  Scenario: Default Menu structure
    Then the menu "coreshop.main" should have a child with ID "coreshop_order_by_number"
    And the menu "coreshop.main" should have a child with ID "coreshop_quote_by_number"
    And the menu "coreshop.main" should have a child with ID "coreshop_settings"
    And the menu "coreshop.main" should have a child with ID "coreshop_pricerules"
    And the menu "coreshop.main" child with id "coreshop_pricerules" should have a child with ID "coreshop_cart_pricerules"
    And the menu "coreshop.main" child with id "coreshop_pricerules" should have a child with ID "coreshop_product_pricerules"
    And the menu "coreshop.main" should have a child with ID "coreshop_localization"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_countries"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_states"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_currencies"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_exchange_rates"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_zones"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_taxes"
    And the menu "coreshop.main" child with id "coreshop_localization" should have a child with ID "coreshop_taxrulegroups"
    And the menu "coreshop.main" should have a child with ID "coreshop_order"
    And the menu "coreshop.main" child with id "coreshop_order" should have a child with ID "coreshop_orders"
    And the menu "coreshop.main" child with id "coreshop_order" should have a child with ID "coreshop_order_create"
    And the menu "coreshop.main" child with id "coreshop_order" should have a child with ID "coreshop_quotes"
    And the menu "coreshop.main" child with id "coreshop_order" should have a child with ID "coreshop_quotes"
    And the menu "coreshop.main" should have a child with ID "coreshop_shipping"
    And the menu "coreshop.main" child with id "coreshop_shipping" should have a child with ID "coreshop_carriers"
    And the menu "coreshop.main" child with id "coreshop_shipping" should have a child with ID "coreshop_carriers_shipping_rules"
    And the menu "coreshop.main" should have a child with ID "coreshop_product"
    And the menu "coreshop.main" child with id "coreshop_product" should have a child with ID "coreshop_indexes"
    And the menu "coreshop.main" child with id "coreshop_product" should have a child with ID "coreshop_filters"
    And the menu "coreshop.main" child with id "coreshop_product" should have a child with ID "coreshop_product_units"
    And the menu "coreshop.main" should have a child with ID "coreshop_notification_rules"
    And the menu "coreshop.main" should have a child with ID "coreshop_payment_providers"
    And the menu "coreshop.main" should have a child with ID "coreshop_stores"
    And the menu "coreshop.main" should have a child with ID "coreshop_about"
```

真实menuBuilder与约30个嵌套节点ID断言。与filter持久化需求匹配弱。

配对任务 `coreshop/features/domain/filter/create_filter.feature:10`。同feature=False，同scenario kind=True，标题Jaccard=-0.000。匹配限制见上面的语义说明。

生成代码见 [behat_services.yml](evidence/2df76e5b1b5fae49181c/generated/behat_services.yml)、[MenuContext.php](evidence/2df76e5b1b5fae49181c/generated/src/CoreShop/Behat/Context/Domain/Menu/MenuContext.php)。

[实际逐步执行和调用](evidence/2df76e5b1b5fae49181c/execution.json)；[参考基线调用](gold-execution/2df76e5b1b5fae49181c.json)；[候选全部变异结果](evidence/2df76e5b1b5fae49181c/mutation-results.json)；[存活修改](evidence/2df76e5b1b5fae49181c/surviving-mutants.json)；[参考杀死标签](evidence/2df76e5b1b5fae49181c/reference-kills.json)

参考测试见 [MenuContext.php](evidence/2df76e5b1b5fae49181c/reference/src/CoreShop/Behat/Context/Domain/MenuContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/joe_views_all_archived_petitions.feature:73


`C` / `CONTROL_GAP`。原实现 `passed`，杀死95/95，存活0，drop 0。

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

配对任务 `e-petitions/features/admin/all_petitions.feature:109`。同feature=False，同scenario kind=True，标题Jaccard=0.083。匹配限制见上面的语义说明。

生成代码见 [archived_petitions_steps.rb](evidence/51402702ed0f9175add9/generated/features/step_definitions/archived_petitions_steps.rb)。

[实际逐步执行和调用](evidence/51402702ed0f9175add9/execution.json)；[参考基线调用](gold-execution/51402702ed0f9175add9.json)；[候选全部变异结果](evidence/51402702ed0f9175add9/mutation-results.json)；[存活修改](evidence/51402702ed0f9175add9/surviving-mutants.json)；[参考杀死标签](evidence/51402702ed0f9175add9/reference-kills.json)

参考测试见 [constituency_search_steps.rb](evidence/51402702ed0f9175add9/reference/features/step_definitions/constituency_search_steps.rb)、[inspection_steps.rb](evidence/51402702ed0f9175add9/reference/features/step_definitions/inspection_steps.rb)、[petition_steps.rb](evidence/51402702ed0f9175add9/reference/features/step_definitions/petition_steps.rb)、[validation_steps.rb](evidence/51402702ed0f9175add9/reference/features/step_definitions/validation_steps.rb)、[web_steps.rb](evidence/51402702ed0f9175add9/reference/features/step_definitions/web_steps.rb)。

#### 对应生成代码位置


[archived_petitions_steps.rb](evidence/51402702ed0f9175add9/generated/features/step_definitions/archived_petitions_steps.rb)


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

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### python-docx/features/cmt-mutations.feature:17


`N` / `CONTROL`。原实现 `passed`，杀死126/126，存活0，drop 0。

```gherkin
  In order to add and modify the content of a comment
  As a developer using python-docx
  I need mutation methods on Comment objects
  Scenario: Comments.add_comment() specifying author and initials
    Given a Comments object with 0 comments
     When I assign comment = comments.add_comment(author="John Doe", initials="JD")
     Then comment.author == "John Doe"
      And comment.initials == "JD"
```

真实创建comment并精确核验作者、initials、计数。与comment timestamp同域，属性不同。

配对任务 `python-docx/features/cmt-props.feature:22`。同feature=False，同scenario kind=True，标题Jaccard=0.125。匹配限制见上面的语义说明。

生成代码见 [cmt_mutations.py](evidence/8a6054d6ffd781460395/generated/features/steps/cmt_mutations.py)。

[实际逐步执行和调用](evidence/8a6054d6ffd781460395/execution.json)；[参考基线调用](gold-execution/8a6054d6ffd781460395.json)；[候选全部变异结果](evidence/8a6054d6ffd781460395/mutation-results.json)；[存活修改](evidence/8a6054d6ffd781460395/surviving-mutants.json)；[参考杀死标签](evidence/8a6054d6ffd781460395/reference-kills.json)

参考测试见 [comments.py](evidence/8a6054d6ffd781460395/reference/features/steps/comments.py)、[helpers.py](evidence/8a6054d6ffd781460395/reference/features/steps/helpers.py)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### algorand-sdk/features/unit/v2algodclient_paths.feature:120


`N` / `CONTROL`。原实现 `passed`，杀死33/33，存活0，drop 0。

```gherkin
  Background:
    Given mock server recording request paths
  Scenario Outline: Account Application Information
    When we make an Account Application Information call against account "<account>" applicationID <application-id>
    Then expect the path used to be "<path>"
    Examples:
      | path                              | account | application-id |
      | /v2/accounts/47YPQTIGQEO7T4Y4RWDYWEKV6RTR2UNBQXBABEEGM72ESWDQNCQ52OPASU/applications/123 | 47YPQTIGQEO7T4Y4RWDYWEKV6RTR2UNBQXBABEEGM72ESWDQNCQ52OPASU     | 123            |
```

真实HTTP请求并捕获URI精确核验。与另一个algod paths场景同feature且同边界，匹配强。

配对任务 `algorand-sdk/features/unit/v2algodclient_paths.feature:83`。同feature=True，同scenario kind=True，标题Jaccard=-0.000。匹配限制见上面的语义说明。

生成代码见 [AlgodRestApiV2PathsSteps.java](evidence/033445cbe698bf66e4e9/generated/src/test/java/com/algorand/algosdk/unit/AlgodRestApiV2PathsSteps.java)。

[实际逐步执行和调用](evidence/033445cbe698bf66e4e9/execution.json)；[参考基线调用](gold-execution/033445cbe698bf66e4e9.json)；[候选全部变异结果](evidence/033445cbe698bf66e4e9/mutation-results.json)；[存活修改](evidence/033445cbe698bf66e4e9/surviving-mutants.json)；[参考杀死标签](evidence/033445cbe698bf66e4e9/reference-kills.json)

参考测试见 [AlgodPaths.java](evidence/033445cbe698bf66e4e9/reference/src/test/java/com/algorand/algosdk/unit/AlgodPaths.java)、[PathsShared.java](evidence/033445cbe698bf66e4e9/reference/src/test/java/com/algorand/algosdk/unit/PathsShared.java)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### coreshop/features/domain/optimistic_entity_lock/lock.feature:22


`N` / `CONTROL`。原实现 `passed`，杀死8/8，存活0，drop 0。

```gherkin
  Background:
    Given there is a pimcore class "Locking"
    And the definition has a input field "name"
    And the definition has a numeric integer field "optimisticLockVersion"
    And the definitions parent class is set to "\CoreShop\Behat\Model\Lock\OptimisticLock"
    And there is an instance of behat-class "Locking" with key "test1"
    And the object-instance has following values:
      | key               | value                                                             | type   |
      | name              | test                                                              | input  |
  Scenario:
    Given I successfully lock the object-instance with the current version
    And I reload the object-instance into object-instance-2
    And I change the object-instance-2 values:
      | key               | value                                                             | type   |
      | name              | test                                                              | input  |
    Then I successfully save versioned object-instance-2
    Then I unsuccessfully save versioned object-instance
```

真实entity lock、重新加载、鲜状态save成功及旧状态save抛异常。具有跨对象状态验证；与安装命令匹配弱。

配对任务 `coreshop/features/domain/cli/install_demo_data_command.feature:7`。同feature=False，同scenario kind=True，标题Jaccard=-0.000。匹配限制见上面的语义说明。

生成代码见 [LockContext.php](evidence/ce595d4ef543fec8c41f/generated/src/CoreShop/Behat/Context/Domain/OptimisticEntityLock/LockContext.php)。

[实际逐步执行和调用](evidence/ce595d4ef543fec8c41f/execution.json)；[参考基线调用](gold-execution/ce595d4ef543fec8c41f.json)；[候选全部变异结果](evidence/ce595d4ef543fec8c41f/mutation-results.json)；[存活修改](evidence/ce595d4ef543fec8c41f/surviving-mutants.json)；[参考杀死标签](evidence/ce595d4ef543fec8c41f/reference-kills.json)

参考测试见 [OptimisticEntityLockContext.php](evidence/ce595d4ef543fec8c41f/reference/src/CoreShop/Behat/Context/Setup/OptimisticEntityLockContext.php)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

### e-petitions/features/joe_searches_for_an_archived_petition.feature:38


`N` / `CONTROL`。原实现 `passed`，杀死118/118，存活0，drop 0。

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
  Scenario: Searching for petition by id
    When I go to the archived petitions page
    And I fill in "search" with the id of the archived petition "Wombles are great"
    And I press "Search"
    Then I should be on the archived petition page for "Wombles are great"
```

真实归档搜索ID后精确匹配目标路径。与Wombles结果列表同feature但唯一ID跳转和多结果关系义务不同；自动匹配表的target是首页ID搜索。

配对任务 `e-petitions/features/arnold_searches_from_home_page.feature:39`。同feature=False，同scenario kind=True，标题Jaccard=0.375。匹配限制见上面的语义说明。

生成代码见 [archived_petition_search_steps.rb](evidence/7b39d0b8ffab2eca2d13/generated/features/step_definitions/archived_petition_search_steps.rb)。

[实际逐步执行和调用](evidence/7b39d0b8ffab2eca2d13/execution.json)；[参考基线调用](gold-execution/7b39d0b8ffab2eca2d13.json)；[候选全部变异结果](evidence/7b39d0b8ffab2eca2d13/mutation-results.json)；[存活修改](evidence/7b39d0b8ffab2eca2d13/surviving-mutants.json)；[参考杀死标签](evidence/7b39d0b8ffab2eca2d13/reference-kills.json)

参考测试见 [petition_steps.rb](evidence/7b39d0b8ffab2eca2d13/reference/features/step_definitions/petition_steps.rb)、[pickle_steps.rb](evidence/7b39d0b8ffab2eca2d13/reference/features/step_definitions/pickle_steps.rb)、[web_steps.rb](evidence/7b39d0b8ffab2eca2d13/reference/features/step_definitions/web_steps.rb)。

本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。

## 跨项目判断与反例


主要操作完全被替代在旧CoreShop和coddy中重复；本轮20例没有新增这种A主操作案例。A_setup在CoreShop三个新场景重复，与旧python-docx具有准备义务相似性，但商店背景和页眉实际定义对目标结果的重要性不同。

新e-petitions管理员场景支持B观察缺口，与Sylius共同涉及需求指定角色可见状态。两者一个漏核验登录/页面，另一个读取了操作中的共享对象，不能声称完全相同机制。e-petitions列表关系缺失在新搜索场景、旧创建场景及一条KillComplete控制重复，当前属于单项目内稳定现象。Kapua异常类型/文本属于另一种C约束，尚无同类型跨项目复现。

Algorand真实HTTP URI核验、python-docx真实footer内容准备、CoreShop汇率持久化及实体锁跨对象检查提供正向反例。15条控制中1条关系缺口和20条nonkill中13条未确认缺口说明，KillComplete和该现象之间没有一一对应关系。本轮样本不适合估计因果效应，也不构成对所有需求义务的穷尽审计。

