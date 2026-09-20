# 费用、预算与汇率调用指南

本文说明 1.0 已实现的本次费用、明确直达汇率和只读预算投影。金额是每笔 Cost 的逻辑总额；工具不按人数、目标数量、晚数或参与者类别再次相乘，也不创建订单、权益或 Payment。

## 金额语义

新建 Trip 直接使用稳定数据契约 1.0，费用、预算与汇率方法均可直接调用。

一笔往返整车总价即使覆盖两个 Leg，也只建一个 Cost：

```python
{"method": "cost.record", "as": "round_trip_car", "args": {
  "title": "往返整车费",
  "targets": [outbound_leg, return_leg],
  "price_status": "estimate",
  "amount": "12000",
  "currency": "JPY",
  "completeness": "unknown"
}}
```

`targets` 是非空、去重的既有 Item、Leg、Journey、Stay、Activity、ServiceUse、VehicleUse、ServiceBundle、Route、Reservation 或其合法局部对象 handle。raw Ref、Place、成员和 Trip 不是 Cost target。同样 targets 的另一笔附加费仍是另一 Cost；工具不按标题或目标自动合并。

`amount` 与 `currency` 成对提供，组成 exact；或者传完整 `value`：

```python
{"kind": "exact", "money": {"amount": "420", "currency": "USD"}}
{"kind": "range", "min": {"amount": "100", "currency": "JPY"},
                    "max": {"amount": "150", "currency": "JPY"}}
{"kind": "from", "min": {"amount": "20", "currency": "JPY"}}
{"kind": "unknown", "currency": "JPY"}
```

金额接受非负十进制字符串或整数，不接受 float、bool、负数或非有限值。range 两端必须同币种且 min≤max。`price_status=estimate|confirmed` 决定写 estimate 或 confirmed 槽；confirmed 不接受 unknown。`completeness` 缺省 unknown，exact 不自动等于 complete。

可选 `quantity_basis` 只保留来源明确的解释，不参与总额计算：

```python
"quantity_basis": {
  "unit": "person", "quantity": 3,
  "rate": {"amount": "4000", "currency": "JPY"},
  "eligible_members": [adult_a, adult_b],
  "notes": "来源明确为三人整车总额"
}
```

`eligible_members` 使用 Trip member handle，保存为快照 ID；不从年龄或 declared_category 推票价资格。`breakdown=[{"label":...,"money":...,"notes"?:...}]` 只作展示分项，不再次累计。`quote` 可引用一条确实采用的 PriceQuote；参考报价本身不会自动生成 Cost，也不进入预算总额。

## 明确确认

首次以 `price_status=confirmed` 录入，或调用 `cost.confirm`，都须在 operation 上提供 origin：

```python
{
  "method": "cost.confirm",
  "origin": {"basis": "confirmation", "statement": "来源明确酒店总额为420美元"},
  "args": {"target": hotel_cost, "amount": "420", "currency": "USD"}
}
```

confirm 保持同一 Cost、targets 与 estimate，只补 confirmed。首次确认若省略 completeness，当前 completeness 变为 unknown，即使旧 estimate 曾写 complete；回执的 `parts.completeness_change` 明示变化。已有 confirmed 后，同值重提省略 completeness 时保持当前值并返回 no_change；`1`、`1.0`、`1.00` 在同币种、同一种 PriceValue 边界中视为数值相等，保留原存储拼写且不增加 Claim。exact、range、from 之间不互相视为同值，跨币种也不等价。不同已知 confirmed 或不同 completeness 须等待受控修订方法，当前原子拒绝。

不要为“更新”再建第二笔 Cost；先 read 找回原 Cost handle。confirmed 只表示已确认的费用陈述，不表示已经付款，不生成 pending/settled Payment。

## 汇率与采用

先保存来源，再记录不可变汇率快照。`rate` 明确表示 `1 base = rate quote`：

```python
{"method": "source.record", "as": "fx_source", "args": {
  "kind": "synthetic_fixture", "title": "示例预算汇率来源"
}}
{"method": "exchange_rate.record", "as": "usd_jpy", "args": {
  "base_currency": "USD", "quote_currency": "JPY",
  "rate": "150", "as_of": "2027-08-01", "source": {"local": "fx_source"}
}}
{"method": "budget.configure", "args": {
  "reporting_currency": "JPY", "rates": [{"local": "usd_jpy"}],
  "scope": {"status": "partial", "notes": "仅汇总已录费用"}
}}
```

汇率须为正十进制字符串或正整数；base/quote 不同，日期与 Source 必填。`budget.configure` 整体替换本次 reporting_currency 与 rates；rates 可为空。每个 base 只能选一个明确直达 reporting currency 的快照。工具不倒数、不串联、不选择最新、不平均；新快照只有再次 configure 后才生效。采用旧记录时仍检查正数、日期和 Source。

`exchange_rate.record` 只保存不可变汇率快照，不会自动采用它。若来源明确要求为本次预算换算或预算展示“采用/使用 `1 BASE = rate QUOTE`”这条直达映射，且与当前配置不冲突，该换算方向给出本次 `reporting_currency=QUOTE`：记录汇率后，必须用该汇率调用 `budget.configure`，再读取 `budget_projection`，确认需要换算的原币费用进入 `reporting.known_part`。若来源只是提供参考汇率，就不要配置预算。不得倒推、串联、自动选最新，也不得把预算汇率说成结算事实。

`budget.configure` 是完整替换，不是向现有 adopted rates 追加。续编前先 read 当前 reporting currency 与已采用汇率。同一 reporting currency 下，提交完整保留集合；来源明确更新某个 base 时，只把该 base 的旧快照替换为新快照，其他 base 的直达汇率继续传入。若现有 reporting currency 与新映射的 QUOTE 不同，来源又没有明确要求切换报告币种，不得只凭新公式覆盖当前目标；记录冲突并请求澄清。多条待采用映射指向不同 QUOTE 时也不能猜一个统一目标。

scope 省略时保留旧声明。categories 只保留调用方声明的局部范围，不筛选 Cost，也不证明类别费用完整。

## 预算投影

`read_workspace(state)["budget_projection"]` 与 Python `export_package(...)["budget_projection"]` 使用同一纯函数结果。CLI 可直接读取：

```sh
scripts/travel-handbook read /path/to/state.json
```

CLI export 仍只写规范 package；Cost 原币、ExchangeRate 和 Trip 采用关系保留其中，`budget_projection` 不夹入领域 JSON。

投影结构包含：

- `status=recorded_costs|no_recorded_costs`；
- `costs[]`：每笔 active Cost 一次，列明 cost_ref、采用的 confirmed/estimate 槽、原值、completeness、targets，以及可选 reporting 转换；
- `original_currency_groups[]`：按原币汇总已知部分，并单列 unknown Cost；无币种 unknown 的 currency 为 null，不塞入报告币种；
- 配置报告币种后有 `reporting`：只累计同币种或已有明确直达汇率的已知部分，列出缺汇率、未知金额与未知币种的 Cost；
- `completeness`：只有 budget_scope 明确 complete、没有 categories、所有 active Cost 完整且金额有界、所需换算均可用时，才返回 `caller_declared_complete`。这仍是调用方声明，不证明现实无遗漏。

confirmed 优先于 estimate，两槽不相加。range 保留上下限；from 只有下限；unknown 不作0。缺汇率保留原币并列缺口。所有十进制乘加使用按输入动态扩展的 Decimal 精度，不默认两位小数，不把展示舍入写回原值。

零条 active Cost 时返回 `no_recorded_costs`，不生成 exact 0 或“全程免费”。已知免费须显式记录金额0的 Cost。投影不累计 PriceQuote、breakdown、Payment、押金或引用副本，也不实现费用撤销、分账、票价资格、汇率链路或支付状态。
