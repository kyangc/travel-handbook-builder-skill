# 交通订单与多范围权益

沿用 [订单与权益指南](RESERVATION_GUIDE.md) 的来源、原子批次与重放规则。以下示例为虚构材料。这里记录已明确发生的外部订单或已取得权益，不执行订票，不补班次、座位、付款或改签。

## 先取正确的交通对象

`journey.compose` 仍以正式日程 Item 为主返回；回执另外提供 Journey 主体和每个 Leg：

```python
result = receipt["operations"][0]  # 本次 journey.compose 的结果
transport_item = result["primary"]
journey = result["parts"]["journey"]
bus = result["parts"]["legs"]["bus"]
rail = result["parts"]["legs"]["rail"]
```

`reservation.record.targets` 和 `coverage.record` 的目标现在接受 Journey、Leg，以及原有 Stay、Stay Unit。**transport_item 不是 Journey handle，不能传给这两个入口。** 同批可用 `{"local":"transfer","part":{"kind":"leg","key":"bus"}}` 引用先前 compose 的 Leg；Journey 请使用回执中取得的 handle，本节不提供 Journey 的局部别名语法。

调用方必须根据原文选择订单关联整个 Journey 还是特定 Leg。相邻交通、同一平台、同一付款记录或相同端点，都不自动证明属于同一联程订单。

```python
{"method":"reservation.record", "as":"connection-order", "args":{
    "provider":"原文给出的示例供应方",
    "status":"confirmed",
    "targets":[journey]
}, "origin":{
    "basis":"user_statement",
    "statement":"来源明确这次巴士与电车接续属于同一笔已确认交通订单。"
}}
```

这只记录订单，不自动创建权益。若来源只证明一段已订，就只引用该 Leg；工具不会把它扩大为整段 Journey。

## 一份权益可以包含多个独立范围

单目标写法仍使用 `target` 及顶层 `validity/participants/quantity`。多范围改用非空 `scopes`，每项需要本次操作内唯一的 key 和 target：

```python
{"method":"coverage.record", "as":"connection-right", "args":{
    "reservation":{"local":"connection-order"},
    "benefits":[{"kind":"transport","notes":"原文明确包含下列两段乘车权益"}],
    "scopes":[
        {"key":"bus-range", "target":bus,
         "validity":{"date":"2026-10-02","timezone":"Asia/Tokyo"},
         "participants":{"kind":"count","count":2},
         "quantity":{"unit":"passenger","count":2}},
        {"key":"rail-range", "target":rail,
         "validity":{"date":"2026-10-02","timezone":"Asia/Tokyo"},
         "participants":{"kind":"count","count":2},
         "quantity":{"unit":"passenger","count":2}}
    ]
}, "origin":{
    "basis":"user_statement",
    "statement":"确认材料明确：10月2日两位乘客都取得巴士段和电车段乘车权益；这是同一份联程权益记录。"
}}
```

这次调用创建 **一个 Coverage**，其中两个 scope 各有自己的适用事实；不会创建两份 Coverage。scope 中的 validity、participants、quantity 都可省略，省略各自保存 unknown，不从 Journey、主 Item、其他 scope 或整笔订单补齐。

- `target` 与 `scopes` 必须二选一。
- 使用 scopes 时，不接受顶层 validity、participants、quantity；把事实分别写进对应 scope。
- 每项只支持 key、target、validity、participants、quantity。不接受原始 ID、scope state 或未支持字段。
- benefits 和 limits 属于整个 Coverage，不能暗示其中某项 benefit 只适用一部分 scope。不同待遇应明确拆分记录，不能凭拆分记录数推断实体票数。
- 同一个 target 可以有多个来源明确、条件不同的范围；工具不会按 target 去重。重复 key 会拒绝。

多范围结果中的 `parts.scopes["bus-range"]` 是对应 scope 的稳定局部 handle；单目标调用则返回 `parts.scopes["scope"]`。之后引用应使用 handle，不把输入 key 当永久业务 ID。这里没有通用 scope 修改入口。

### 范围和数量不能当作票张数

两位乘客各乘两段，意味着每段适用两位乘客，**不能相加后称买了四张票或有四位乘客**。Coverage 表达一组已取得权益，不是电子票凭证实体；一个 Coverage、一个订单和一张实体票不保证一一对应。

“两段都可以乘”与“A、B 任选一段且总共只能使用一次”不同。后者涉及共享额度或替代使用关系，当前多 scope 不足以表达，不能靠填两个 quantity=1 冒充已经建模。

## 订单范围检查

提供 reservation 时，它必须是 confirmed。各 scope 的 target 必须是订单直接关联的对象，或为订单关联 Journey 的直属 Leg；原有 Stay 到其 Unit 的关系也支持。

以下会失败并回滚整批：

- 订单只关联一个 Leg，权益却指整个 Journey 或其兄弟 Leg。
- 订单关联 Journey A，权益指 Journey B 的 Leg，即使两段端点相同。
- 多 scope 中任何一个引用不存在、越出订单范围、字段不合法或 key 重复。
- pending、unknown、cancelled 订单被用来关联新 active 权益。

这项检查仅核对模型对象关系，不证明票号、班次、票种、日期或供应方的实际承运条件匹配。当前已有覆盖诊断主要比较住宿 Unit；交通范围通过结构检查不等于班次适用性已经核验。

## 本轮仍未表达的内容

当前没有票号、PNR、二维码凭证、车厢号或座位分配的专门结构。它们不能伪装成 Journey ID、scope key 或 provider。必要的原文可通过明确的 origin 陈述保留，并标记仍未结构化；私人凭证不因此适合公开发布。

两个 record 入口不会更新旧确认、撤销某个范围、补付款或计算总票数。同一成功请求原样重放不会重复创建记录；用新 request_id 再 record 则创建新记录，不等于更新旧票。确认更新与整范围撤销使用 1.0 的 [确认修订入口](COVERAGE_REVISION_GUIDE.md)，不以重复 record 替代。
