# 阶段性案例证据

本批复核 4 个已有案例，复用原始执行证据。56 个固定案例的语义复核仍待完成。

## 案例 33 · 替代业务对象上的断言

任务 `coreshop/features/domain/order/create_order_with_discount.feature:23`。证据等级为已证实。

```gherkin
  Scenario: Create a new order and add a product
    Given I add the product "T-Shirt" to my cart
    And I apply the voucher code "asdf" to my cart
    And the cart ships to customer "some-customer@something.com" address with postcode "4600"
    And the cart invoices to customer "some-customer@something.com" address with postcode "4600"
    And I create an order from my cart
    Then there should be one product in my order
```

文件 `src/CoreShop/Behat/Context/Domain/Order/CreateOrderContext.php`，完整生成文件已保存至 `semantic_batches/batch-001/33/generated/`。

106         $this->items[] = $product;
127         $this->order = new class($this->items) {
142         Assert::notNull($this->order, 'No order was created from the cart.');
143         Assert::count($this->order->getItems(), 1);

需求要求从真实购物车创建订单。生成代码用本地 items 数组和匿名类构造订单，优惠券、地址及多项准备步骤为空函数，最后仅对匿名对象 getItems() 的数量断言。唯一生成文件中不存在生产订单创建调用。执行通过，API F1 和 Coverage J 均为 0，200 个已计分变异体全部存活。可证实该测试验证了自建对象，具体每个变异体的因果影响仍需差分确认。

需求中的 cart、voucher、create an order 指向业务操作。正确业务调用的具体接线是否可由可见视图唯一确定仍需核对。

已检查该预测的全部 1 个生成文件。原执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/33/exec.jsonl`，变异执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/33/mutation-records.jsonl`。存活变异体示例为 e3c58ab5d7c33b39, 2b50ed06e1ed7595, 17eedcf6d45d4e99, 7360cc04d6d10378, ca4988497994b476, 4220e5752426b344。源码级因果解释待复核。

## 案例 35 · 准备路径与行为义务的对应关系

任务 `python-docx/features/tbl-row-props.feature:29`。证据等级为有线索。

```gherkin
  Scenario Outline: Get Row.height_rule
    Given a table row having height rule <state>
     Then row.height_rule is <value>
```

文件 `features/steps/tbl_row_props.py`，完整生成文件已保存至 `semantic_batches/batch-001/35/generated/`。

007 def given_row_with_height_rule(context, state):
013         context.row.height_rule = WD_ROW_HEIGHT_RULE.AUTO
015         context.row.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
020 @then("row.height_rule is {value}")
021 def then_row_height_rule_is(context, value):
023     actual = context.row.height_rule
024     assert actual == expected, "expected %r, got %r" % (expected, actual)

测试使用 Document 创建真实表格，先通过 height_rule setter 准备状态，再读取 getter 并与枚举或 None 比较。103 个变异体中杀死 101 个，2 个存活。真实调用和具体结果断言均存在。存活原因需要对照变异体差分，不能归因为缺少断言。

可见需求明确 getter 返回值，准备路径是否必须独立于 setter 尚无法判断。

已检查该预测的全部 1 个生成文件。原执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/35/exec.jsonl`，变异执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/35/mutation-records.jsonl`。存活变异体示例为 90cba801ac9a1512, a2b898d153fc1be6。源码级因果解释待复核。

## 案例 37 · 已覆盖显式断言后的剩余漏检

任务 `algorand-sdk/features/unit/v2indexerclient_responses.feature:15`。证据等级为有线索。

```gherkin
  Scenario Outline: LookupAssetTransactions response
    Given mock http responses in "<jsonfiles>" loaded from "<directory>"
    When we make any LookupAssetTransactions call
    Then expect error string to contain "<err>"
    And the parsed LookupAssetTransactions response should be valid on round <roundNum>, and contain an array of len <len> and element number <idx> should have sender "<sender>"
    Examples:
      | jsonfiles                      | directory                     | err | roundNum | len | idx | sender                                                     |
      | lookupAssetTransactions_0.json | v2indexerclient_responsejsons |     | 6222957  | 39  | 0   | ARCC3TMGVD7KXY7GYTE7U5XXUJXFRD2SXLAWRV57XJ6HWHRR37GNGNMPSY |
```

文件 `src/test/java/com/algorand/algosdk/unit/LookupAssetTransactionsSteps.java`，完整生成文件已保存至 `semantic_batches/batch-001/37/generated/`。

015 import static org.assertj.core.api.Assertions.assertThat;
030     public void lookupAssetTransactions() throws Exception {
031         response = client.lookupAssetTransactions(163650L).execute();
036         assertThat(response).isNotNull();
038             assertThat(response.isSuccessful()).isTrue();
040             assertThat(response.message()).contains(error);
047         assertThat(body.currentRound).isEqualTo(round);
048         assertThat(body.transactions).hasSize(length);
049         assertThat(body.transactions.get(index).sender).isEqualTo(sender);

测试真实调用 lookupAssetTransactions(...).execute()，检查响应成功、currentRound、交易数量及指定 sender，覆盖了场景中显式列出的结果检查。27 个变异体杀死 21 个、6 个存活。它构成对“存活必然表示漏掉显式断言”的反例，具体缺失义务仍待变异体差分确认。

round、length、index 和 sender 在 Examples 中明确给出。其余隐含义务能否推导尚无法判断。

已检查该预测的全部 1 个生成文件。原执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/37/exec.jsonl`，变异执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/37/mutation-records.jsonl`。存活变异体示例为 3ab3886db95d08d9, 0f4db1a21b4da121, 289f4d413f3ff19a, f085dc1f27fc17ff, 413fe58fcbb59b7f, 0c3591313a15c555。源码级因果解释待复核。

## 案例 40 · 成功对照

任务 `python-docx/features/sty-latent-props.feature:21`。证据等级为已证实。

```gherkin
  Scenario Outline: Set default latent style properties
    Given a latent styles object with known defaults
     When I assign <new-value> to latent_styles.<prop-name>
     Then latent_styles.<prop-name> is <value>
```

文件 `features/steps/sty_latent_props.py`，完整生成文件已保存至 `semantic_batches/batch-001/40/generated/`。

020     setattr(context.latent_styles, prop_name, _value_for(prop_name, new_value))
025     actual = getattr(context.latent_styles, prop_name)
027     assert actual == expected, (

真实 Document 对象上的 latent_styles 经 setattr 写入指定属性，再用 getattr 读取，并按类型转换后的期望值断言。113 个已计分变异体全部杀死。该对照支持真实对象、写入和读取关系可由生成测试实现。

Given/When/Then 明确写入和读取关系。默认值准备的完整性仍受单个场景范围限制。

已检查该预测的全部 1 个生成文件。原执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/40/exec.jsonl`，变异执行记录位于 `/root/Baxxhy/work2/diagnostics/failure-mechanisms-20261115/cases/40/mutation-records.jsonl`。存活变异体示例为 无。源码级因果解释待复核。
