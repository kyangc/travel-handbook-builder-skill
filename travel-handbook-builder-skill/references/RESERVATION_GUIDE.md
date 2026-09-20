# 住宿订单与已确认权益

沿用 [CALLER_GUIDE](CALLER_GUIDE.md) 的原子批次、handle 和 local 引用。两个入口分别记录订单与已取得权益，不执行任何外部预订、扣款或取消。以下都是虚构输入示例；实际调用只能填写来源明确给出的事实。当前可调用能力以 read 返回为准。

## 两个入口分别做什么

| 方法 | 必填 args | 可选 args | 主返回 |
|---|---|---|---|
| `reservation.record` | provider、status、targets | cancellation_terms、recorded_at | Reservation handle |
| `coverage.record` | target、benefits | reservation、validity、participants、quantity、limits | Coverage handle |

**两种操作都必须在操作封装上提供 `origin`，不是 args.evidence。** 最小依据为 `{"basis":"user_statement","statement":"明确的来源陈述"}`；沿用公共 origin 规则。依据必须支持所记录的状态或权益，不能只有“以后查一下”。`basis="estimate"` 不足以建立这些执行事实，会被拒绝；`synthetic_fixture` 仅适用于 example 攻略。工具保留所给依据，不把笔记自动升级为供应方已核验。

住宿入口接受 Stay 或其 Unit 的稳定 handle，不能直接把酒店 Place 作为已订服务。另支持 Journey/Leg 与多范围权益，见 [交通指南](TRANSPORT_COVERAGE_GUIDE.md)。应先用 [住宿计划入口](STAY_GUIDE.md) 建立真实选定的 Stay；不得制造一个“待定酒店”填引用。

## 记录订单已确认，但尚待扣款

```python
{"method": "reservation.record", "as": "hotel-order", "args": {
    "provider": "来源明确给出的示例预订渠道",
    "status": "confirmed",
    "targets": [stay],
    "cancellation_terms": [
        {"description": "取消规则以确认信所述条件为准；准确截止时刻尚未记下"}
    ]
}, "origin": {
    "basis": "user_statement",
    "statement": "笔记转述确认信：这笔住宿订单已确认，待自动扣款；未记录实际扣款。"
}}
```

- provider 为来源中明确的供应方或预订渠道名称，不从酒店名称猜预订平台。
- status 显式选择 `pending | confirmed | cancelled | unknown`，不默认 confirmed。
- targets 是非空 Stay/Unit handle 列表，指明这笔订单关联的服务。两笔不同酒店订单分别记录，不因同一平台合成一笔。
- recorded_at 仅在记录时刻本身已明确且需要保留时提供，使用 `{local, timezone}`；它不是付款时刻、入住时刻或订单确认时刻的替代品，省略时不补系统当前时间。
- `confirmed` 仅写订单确认。**不自动生成 Coverage、Cost、Payment 或办理 Task**，也不把 Stay 请求改成供应方已保证。
- “待自动扣款”在 origin 陈述中保留；当前不会变成结构化付款状态。没有 Payment 不证明从未支付，也不能据此显示已付金额为零。即使陈述包含未来扣款日期，这两个入口也不会自动创建 scheduled Payment。

本轮没有 `booking_reference` 字段或专门的订单编号入口，不要自行给 args 添加未支持字段，也不要把编号塞进 provider 冒充供应方名称。必要时仅在明确需要保留的原文陈述中记录，并说明它尚未成为结构化订单编号；私人订单信息不因此取得公开发布许可。

## 含早餐属于明确记录的权益

```python
{"method": "coverage.record", "as": "hotel-benefits", "args": {
    "target": stay,
    "reservation": {"local": "hotel-order"},
    "benefits": [
        {"kind": "lodging", "notes": "确认中所述住宿服务"},
        {"kind": "breakfast", "notes": "确认中明确含早餐，逐日适用范围尚未记下"}
    ]
}, "origin": {
    "basis": "user_statement",
    "statement": "来源明确这笔已确认住宿含早餐；本次未摘录具体早餐日期、人数及份数。"
}}
```

这次调用创建一份新 `active` Coverage，内部只有一个 scope；调用方不手工生成 scope ID。benefits 必须是非空对象列表，每项为 `{kind, notes?, value?}`，不是字符串数组；kind 必须有实际含义，notes/value 是来源提供的可选非空文字，不是任意结构化字典。

reservation 可省略，允许记录明确取得的赠送权益。若提供，订单必须 confirmed；target 必须在订单 targets 中，或为订单已关联 Stay 下的 Unit。反向推断不成立：订单只订了某个 Unit，不能由此给整个 Stay 记录权益。pending/unknown/cancelled 订单不能借这个入口顺带升级成 confirmed。

每个 scope 的范围由本次确认事实独立给出：

| 可选输入 | 省略与允许值 |
|---|---|
| validity | 省略写 `{kind:"unknown"}`；支持 unknown、local_dates 或单日期 `{date,timezone}` |
| participants | 省略写 `{kind:"unknown"}`；已知总人数可用 `{kind:"count",count:2}`；1.0可用members/groups handle或完整名单下all，写入时均固化为member_ids，不保存动态all/group_ids；见[成员指南](PARTY_GUIDE.md) |
| quantity | 省略写 `{kind:"unknown"}`；也可显式 unknown，或 `{unit:"room",count:1}` 这类正整数数量；不支持零、负数或分数量 |
| limits | 可选非空文字组成的列表，保存已知限制；不自动解释为可执行规则 |

这些默认值**不会读取 Stay.period、Stay.participants 或 Unit.count 来补全**。例如计划两人同住，不证明两人的早餐都已经确认；确认只给人数时，不自动产生个人身份。调用方明确写数量一间，才表示一间已确认房间，不能用数量一泛指“有一条资料”。

### 房晚和早餐日期不能相互推算

已确认房间的使用期可以这样独立填写：

```python
"validity": {"kind": "local_dates", "check_in": "2026-10-02",
             "check_out": "2026-10-05", "timezone": "Asia/Tokyo"},
"participants": {"kind": "count", "count": 2},
"quantity": {"unit": "room", "count": 1}
```

但“10月2日入住、5日退房，含早餐”本身不足以把早餐自动安排成2、3、4日，也不能未经依据假定3、4、5日都覆盖。房晚数量不等于明确的早餐日期或份数。不同权益如果日期、人数或数量不同，应分成独立 Coverage，各自只放适用的 benefits；不要把住宿范围复制到早餐范围。

仅在来源明确“10月5日两份早餐已包含”时，才可为早餐单独提供：

```python
"benefits": [{"kind": "breakfast"}],
"validity": {"date": "2026-10-05", "timezone": "Asia/Tokyo"},
"participants": {"kind": "count", "count": 2},
"quantity": {"unit": "breakfast", "count": 2}
```

单日期写法没有 kind；时区仍必须来自明确资料。当前不支持 fixed 时刻区间、service_period、from_ref 或从计划实时派生的权益有效期。来源未给清楚就保留 unknown，不把信息不足改写成“不含早”。含早也不会自动生成每天的早餐 Item、零元 Cost 或任何 Payment。

## 取消条款：先忠实保留，再按确切信息结构化

每条 cancellation_terms 的 description 必需；只知道原文说明时，仅填这一项即可。来源明确准确截止及是否含边界时，才可补齐成对的 deadline/boundary：

```python
"cancellation_terms": [{
    "description": "来源明确：日本当地10月1日18:00以前取消不收取消费",
    "deadline": {"local": "2026-10-01T18:00:00", "timezone": "Asia/Tokyo"},
    "boundary": "before"
}]
```

`before` 不含该时刻，`not_after` 包含该时刻；不能只给其中一个。模糊的“10月1日前”不得自行补零点、23:59或酒店所在地时区。不同收费阶段可以各自保留 description，但这里不计算取消费，也不保证当前仍可免费取消。

## 修改、重放与本轮边界

这两个 record 入口只记录新的订单或已取得权益。确认更新和既有整范围撤销须直接使用 [确认修订方法](COVERAGE_REVISION_GUIDE.md)；范围扩展与范围内细分撤销仍不支持。不能再次 record 新 active Coverage 来假装旧权益已经更新；也不能把新订单 cancelled 自动传播成旧权益 revoked。原确认与计划冲突时如实保留差异，不能以重新 record 来隐藏历史。

Stay 后续改期不会修改已经记录的 Coverage.validity、人数或数量；只修改计划也不意味着供应方已改订。两间房只有一间含早时，target 应为被确认的 Unit，不扩展给其他房间。

同一成功 request_id 与相同请求重放返回原记录；新 request_id 再次 record 会新建，工具不按平台名称、同酒店或相同说明自动去重。已有成功回执时应复用 handle，不重造事实。

缺少 origin、估算冒充确认、未知/错误目标、非 confirmed 关联订单、来源未给清楚的非法日期或数量，都会拒绝整个批次；此前同批的合法操作也不保存。read/export 只证明这些事实已经按契约存储，不证明供应方已核查、款项已发生、条款适用或旅行可执行。

已有覆盖诊断主要比较房间单位的住宿期间、成员身份和房间数量。早餐的单日有效期、餐次数或只知人数会得到部分 unknown 诊断，这不表示早餐权益无效，也不是已经核验范围。计划改期与已确认房晚不一致时可出现 COVERAGE_PERIOD_MISMATCH；保存差异不自动改订。
