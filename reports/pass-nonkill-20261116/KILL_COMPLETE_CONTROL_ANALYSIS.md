# KillComplete 对照分析

固定选择10条，来自20条KillComplete候选。先按instance_id SHA256排序，在每个有可用成功任务的项目选1条，再依同一排序补足10条。覆盖6个项目。CoreShop和Kapua在这20条中没有KillComplete可配对。选择已冻结于manifest.json。优先保留同项目对照，需求类型相近度在逐项描述中明确。算法补足导致Algorand有4条，未达到每条失败均有相同需求类型对照的理想匹配。

代码行数包含注释和装配代码。assertion_site_proxy只是跨语言词法计数，Go的错误返回也可能是准备错误，不等同语义断言数。需求步骤数来自Gherkin关键字，outline的数据行数独立记录。未构造主观“复杂度分数”，未作显著性检验。

## 01 python-docx/features/blk-iter-inner-content.feature:7

与Footer.iter_inner_content最接近。读取已有fixture并验证块类型次序及段落文本，93/93。对象由Document变为Footer，gold pool也不同，无法将成绩差异完全归因于加载fixture。

实测passed，KillComplete=true，93/93，drop=0。语言 Python，框架 behave，Gherkin步骤 2，示例数据行 0，代码 43 行。

```gherkin
  Scenario: Document.iter_inner_content()
    Given a Document object with paragraphs and tables
     Then document.iter_inner_content() produces the block-items in document order
```

原始执行 [execution.json](evidence/0af839eba15d14e2da1b/execution.json)，逐变异结果 [mutation-results.json](evidence/0af839eba15d14e2da1b/mutation-results.json)。

变异修改类型 {'ArithmeticOperator': 3, 'ConditionalBoundary': 1, 'MethodCallRemoval': 9, 'NegateConditional': 16, 'ReturnValue': 64}。对应原始修改 [control-mutants.json](evidence/0af839eba15d14e2da1b/control-mutants.json)。

[blk_iter_inner_content.py](evidence/0af839eba15d14e2da1b/generated/features/steps/blk_iter_inner_content.py)

## 02 algorand-sdk/features/unit/v2indexerclient_paths.feature:150

六行查询参数示例，真实构造SearchForAssets并对观测路径做精确相等比较。与response场景同项目但输出类型不同，21个pool较小。

实测passed，KillComplete=true，21/21，drop=0。语言 Java，框架 Cucumber，Gherkin步骤 3，示例数据行 6，代码 43 行。

```gherkin
  Scenario Outline: SearchForAssets path
    When we make a SearchForAssets call with limit <limit> creator "<creator>" name "<name>" unit "<unit>" index <index>
    Then expect the path used to be "<path>"
    Examples:
      | path                                                                          | limit | index | creator                                                    | name      | unit     |
      | /v2/assets                                                                    | 0     | 0     |                                                            |           |          |
      | /v2/assets?asset-id=22                                                        | 0     | 22    |                                                            |           |          |
      | /v2/assets?creator=PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI | 0     | 0     | PNWOET7LLOWMBMLE4KOCELCX6X3D3Q4H2Q4QJASYIEOF7YIPPQBG3YQ5YI |           |          |
      | /v2/assets?limit=30                                                           | 30    | 0     |                                                            |           |          |
      | /v2/assets?name=assetname                                                     | 0     | 0     |                                                            | assetname |          |
      | /v2/assets?unit=unitname                                                      | 0     | 0     |                                                            |           | unitname |
```

原始执行 [execution.json](evidence/1181f3b3a11032dde790/execution.json)，逐变异结果 [mutation-results.json](evidence/1181f3b3a11032dde790/mutation-results.json)。

变异修改类型 {'ConstantReplacement': 1, 'MethodCallRemoval': 14, 'NegateConditional': 2, 'ReturnValue': 4}。对应原始修改 [control-mutants.json](evidence/1181f3b3a11032dde790/control-mutants.json)。

[IndexerClientV2PathsSteps.java](evidence/1181f3b3a11032dde790/generated/src/test/java/com/algorand/algosdk/unit/IndexerClientV2PathsSteps.java)

## 03 sylius/features/admin/promotion/managing_coupons/generating_coupon.feature:26

通过admin API生成coupon并查询collection数量，实际跨过管理员观测边界。与下单currency场景同项目，但promotion业务和107个变异集合不同。

实测passed，KillComplete=true，107/107，drop=0。语言 PHP，框架 Behat，Gherkin步骤 11，示例数据行 0，代码 91 行。

```gherkin
    Scenario: Generating new coupons without expiration date
        When I want to generate new coupons for this promotion
        And I choose the amount of 5 coupons to be generated
        And I specify their code length as 6
        And I limit generated coupons usage to 25 times
        And I generate these coupons
        Then I should be notified that they have been successfully generated
        And there should be 5 coupons related to this promotion
```

原始执行 [execution.json](evidence/3ed4dd6333d45d5c438e/execution.json)，逐变异结果 [mutation-results.json](evidence/3ed4dd6333d45d5c438e/mutation-results.json)。

变异修改类型 {'ConditionalBoundary': 1, 'ConstantReplacement': 3, 'FalseValue': 4, 'LogicalConnector': 13, 'MethodCallRemoval': 19, 'NegateConditional': 19, 'RemoveNegation': 29, 'ReturnValue': 17, 'TrueValue': 2}。对应原始修改 [control-mutants.json](evidence/3ed4dd6333d45d5c438e/control-mutants.json)。

[behat_services.yml](evidence/3ed4dd6333d45d5c438e/generated/behat_services.yml)

[PromotionCouponGenerationContext.php](evidence/3ed4dd6333d45d5c438e/generated/src/Sylius/Behat/Context/Api/Admin/PromotionCouponGenerationContext.php)

## 04 prestashop/tests/Integration/Behaviour/Features/Scenario/Meta/meta_management.feature:10

AddMeta命令后重新读取Meta，逐项比较page/title/description/url_rewrite。可与bulk-delete的命令及结果检查对照，业务类型不同。

实测passed，KillComplete=true，36/36，drop=0。语言 PHP，框架 Behat，Gherkin步骤 6，示例数据行 0，代码 77 行。

```gherkin
  Scenario: Create new metadata
    When I add meta "meta1" with specified properties
      | pageName                       | pdf-order-return                      |
      | localisedPageTitle             | page title in default language        |
      | localisedMetaDescription      | meta description in default language  |
      | localisedRewriteUrls           | rewrite-url-default                   |
    Then meta "meta1" page should be "pdf-order-return"
    And meta "meta1" field "title" for default language should be "page title in default language"
    And meta "meta1" field "description" for default language should be "meta description in default language"
    And meta "meta1" field "url_rewrite" for default language should be "rewrite-url-default"
```

原始执行 [execution.json](evidence/5b6d2a356463dcb5ec19/execution.json)，逐变异结果 [mutation-results.json](evidence/5b6d2a356463dcb5ec19/mutation-results.json)。

变异修改类型 {'ConstantReplacement': 1, 'MethodCallRemoval': 1, 'NegateConditional': 5, 'RemoveNegation': 13, 'ReturnValue': 16}。对应原始修改 [control-mutants.json](evidence/5b6d2a356463dcb5ec19/control-mutants.json)。

[MetaFeatureContext.php](evidence/5b6d2a356463dcb5ec19/generated/tests/Integration/Behaviour/Features/Context/MetaFeatureContext.php)

## 05 e-petitions/features/charlie_creates_a_petition.feature:56

同一feature的XSS场景，真实走创建页面并断言不存在onmouseover属性，98/98。HTML检查仍不是完整标准校验，KillComplete不能证明所有需求维度充分。

实测passed，KillComplete=true，98/98，drop=0。语言 Ruby，框架 Cucumber，Gherkin步骤 8，示例数据行 0，代码 36 行。

```gherkin
Scenario: Charlie cannot craft an xss attack when searching for petitions
  Given I am on the start a new petition page
  When I follow "Start your petition"
  Then I should be asked to confirm my eligibility
  When I confirm that I am UK citizen or resident
  Then I should see "Petition title"
  When I fill in "Petition title" with "'onmouseover='alert(1)'"
  When I press "Continue"
  Then the markup should be valid
```

原始执行 [execution.json](evidence/e06a3c2e2fe0c51cee1a/execution.json)，逐变异结果 [mutation-results.json](evidence/e06a3c2e2fe0c51cee1a/mutation-results.json)。

变异修改类型 {'ArithmeticOperator': 1, 'ConstantReplacement': 1, 'FalseValue': 1, 'LogicalConnector': 2, 'MethodCallRemoval': 87, 'NegateConditional': 5, 'RemoveNegation': 1}。对应原始修改 [control-mutants.json](evidence/e06a3c2e2fe0c51cee1a/control-mutants.json)。

[petition_creation_steps.rb](evidence/e06a3c2e2fe0c51cee1a/generated/features/step_definitions/petition_creation_steps.rb)

## 06 coddy-agent/features/config_tools.feature:58

registry.Execute执行config_set与config_changes，再检查返回列表包含命令。与ask-mode相比，检查值来自真实工具调用。业务路径与205个变异池不同。

实测passed，KillComplete=true，205/205，drop=0。语言 Go，框架 Godog，Gherkin步骤 5，示例数据行 0，代码 86 行。

```gherkin
  Scenario: Review pending commands before asking the user to save
    When the agent stages config commands:
      """
      set agent.max_turns=20
      """
    And the agent lists config changes
    Then the change list shows "set agent.max_turns=20"
```

原始执行 [execution.json](evidence/ffee1edff496f2038c9e/execution.json)，逐变异结果 [mutation-results.json](evidence/ffee1edff496f2038c9e/mutation-results.json)。

变异修改类型 {'ArithmeticOperator': 6, 'ConditionalBoundary': 9, 'ConstantReplacement': 27, 'FalseValue': 1, 'Increment': 3, 'LogicalConnector': 21, 'MethodCallRemoval': 6, 'NegateConditional': 114, 'RemoveNegation': 4, 'ReturnValue': 12, 'TrueValue': 2}。对应原始修改 [control-mutants.json](evidence/ffee1edff496f2038c9e/control-mutants.json)。

[bdd_config_tools_test.go](evidence/ffee1edff496f2038c9e/generated/internal/tools/bdd_config_tools_test.go)

## 07 python-docx/features/sty-latent-props.feature:21

属性读写同类对照，六个示例，直接Document()取得latent_styles后setattr/getattr精确比较，113/113。这是“程序化构造必然较差”的反例。

实测passed，KillComplete=true，113/113，drop=0。语言 Python，框架 behave，Gherkin步骤 3，示例数据行 6，代码 29 行。

```gherkin
  Scenario Outline: Set default latent style properties
    Given a latent styles object with known defaults
     When I assign <new-value> to latent_styles.<prop-name>
     Then latent_styles.<prop-name> is <value>

    Examples: known latent_styles property values
      | prop-name                   | new-value | value |
      | default_priority            |   42      | 42    |
      | load_count                  |   240     | 240   |
      | default_to_hidden           |   False   | False |
      | default_to_locked           |   True    | True  |
      | default_to_quick_style      |   True    | True  |
      | default_to_unhide_when_used |   False   | False |
```

原始执行 [execution.json](evidence/2247fcf10bc1e9313ee6/execution.json)，逐变异结果 [mutation-results.json](evidence/2247fcf10bc1e9313ee6/mutation-results.json)。

变异修改类型 {'ArithmeticOperator': 3, 'ConditionalBoundary': 1, 'MethodCallRemoval': 10, 'NegateConditional': 22, 'ReturnValue': 77}。对应原始修改 [control-mutants.json](evidence/2247fcf10bc1e9313ee6/control-mutants.json)。

[sty_latent_props.py](evidence/2247fcf10bc1e9313ee6/generated/features/steps/sty_latent_props.py)

## 08 algorand-sdk/features/unit/atomic_transaction_composer.feature:175

真实空composer.buildGroup必须抛异常并保留BUILDING状态，76/76。不过catch仅验证异常非空，没有比较需求给出的错误文本，是KillComplete仍可能有oracle缺口的反例。

实测passed，KillComplete=true，76/76，drop=0。语言 Java，框架 Cucumber，Gherkin步骤 4，示例数据行 0，代码 42 行。

```gherkin
  Scenario: Build with 0 transactions fails
    Given a new AtomicTransactionComposer
    When I build the transaction group with the composer. If there is an error it is "zero group size error".
    Then The composer should have a status of "BUILDING".
```

原始执行 [execution.json](evidence/3b028264ab4a34f36c37/execution.json)，逐变异结果 [mutation-results.json](evidence/3b028264ab4a34f36c37/mutation-results.json)。

变异修改类型 {'ArithmeticOperator': 10, 'ConditionalBoundary': 6, 'ConstantReplacement': 25, 'Increment': 8, 'MethodCallRemoval': 2, 'NegateConditional': 16, 'RemoveNegation': 2, 'ReturnValue': 7}。对应原始修改 [control-mutants.json](evidence/3b028264ab4a34f36c37/control-mutants.json)。

[AtomicTransactionComposerSteps.java](evidence/3b028264ab4a34f36c37/generated/src/test/java/com/algorand/algosdk/unit/AtomicTransactionComposerSteps.java)

## 09 algorand-sdk/features/unit/v2algodclient_paths.feature:16

两行pending参数示例，调用实际SDK后用verifyPathUrls检查观察到的请求路径，19/19。与响应内容检查的任务复杂度和pool不同。

实测passed，KillComplete=true，19/19，drop=0。语言 Java，框架 Cucumber，Gherkin步骤 3，示例数据行 2，代码 44 行。

```gherkin
  Scenario Outline: Pending Transaction Information2
    When we make a Pending Transaction Information with max <max> and format "<format>"
    Then expect the path used to be "<path>"
    Examples:
      | path                                          | max | format  |
      | /v2/transactions/pending?format=msgpack       | 0   | msgpack |
      | /v2/transactions/pending?format=msgpack&max=1 | 1   | msgpack |
```

原始执行 [execution.json](evidence/3c372d074b10efc34dca/execution.json)，逐变异结果 [mutation-results.json](evidence/3c372d074b10efc34dca/mutation-results.json)。

变异修改类型 {'ConstantReplacement': 1, 'MethodCallRemoval': 12, 'NegateConditional': 2, 'ReturnValue': 4}。对应原始修改 [control-mutants.json](evidence/3c372d074b10efc34dca/control-mutants.json)。

[PendingTransactionsPathSteps.java](evidence/3c372d074b10efc34dca/generated/src/test/java/com/algorand/algosdk/unit/PendingTransactionsPathSteps.java)

## 10 algorand-sdk/features/unit/v2indexerclient_paths.feature:304

三行exclude组合，真实SDK调用后读取lastRequest，精确比较URI路径及编码查询，19/19。直接检查最终外部输出，当前仅构成同项目类型较远对照。

实测passed，KillComplete=true，19/19，drop=0。语言 Java，框架 Cucumber，Gherkin步骤 3，示例数据行 3，代码 45 行。

```gherkin
  Scenario Outline: SearchAccounts path
    When we make a Search Accounts call with exclude "<exclude>"
    Then expect the path used to be "<path>"
    Examples:
      | path                                                                           | exclude                                             |
      | /v2/accounts?exclude=assets                                                    | assets                                              |
      | /v2/accounts?exclude=assets%2Ccreated-assets                                   | assets,created-assets                               |
      | /v2/accounts?exclude=assets%2Ccreated-assets%2Capps-local-state%2Ccreated-apps | assets,created-assets,apps-local-state,created-apps |
```

原始执行 [execution.json](evidence/4bb1ed2b5f9a7c045cef/execution.json)，逐变异结果 [mutation-results.json](evidence/4bb1ed2b5f9a7c045cef/mutation-results.json)。

变异修改类型 {'ConstantReplacement': 1, 'MethodCallRemoval': 10, 'NegateConditional': 2, 'ReturnValue': 6}。对应原始修改 [control-mutants.json](evidence/4bb1ed2b5f9a7c045cef/control-mutants.json)。

[IndexerClientV2PathsSteps.java](evidence/4bb1ed2b5f9a7c045cef/generated/src/test/java/com/algorand/algosdk/unit/IndexerClientV2PathsSteps.java)

## 描述性比较

|分组|任务数|代码行数中位数|步骤数中位数|scored变异数中位数|
|---|---|---|---|---|

|pass_nonkill|24|46.5|4.0|113.5|

|killcomplete_control|10|43.5|3.5|84.5|


成功对照同时包含读取fixture和直接构造对象。明确边界输出、真实调用和充分准备值得继续检查，但这些观察没有控制任务、pool规模、项目及需求类型。尤其空composer错误文本和XSS标记校验反例说明KillComplete不能替代需求审查。

对照侧的787个变异记录已提取对应修改，按任务/操作符分布保存在mutation_operator_counts.csv。成功侧统计全部被杀死项，非Kill侧统计存活项，条件不同，不能直接解释为操作符导致成绩差异。
