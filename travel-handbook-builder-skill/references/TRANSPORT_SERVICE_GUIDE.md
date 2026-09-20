# 班次、逐段时间与明确接续指南

本指南说明 1.0 已实现的班次、Leg 时间与 Connection 编制。它只保存调用方从来源中明确识别的事实，不查询时刻表、不选择班次，也不判断现实中能否赶上。

新建 Trip 直接使用稳定数据契约 1.0；班次、Call、Leg 和 Connection 方法均可直接调用。

## 记录明确班次

只有 `service_number` 和 `service_date` 都明确时才创建 TransportService。`operator` 可省略；回执会给 `parts.operator_unknown=True`，领域对象不写占位运营方。

```python
{"method":"service.record","as":"flight","args":{
  "mode":"air","service_number":"EX123","service_date":"2027-04-10",
  "calls":[
    {"key":"board","endpoint":airport_t3,
     "departure":{"local":"2027-04-10T22:30:00","timezone":"Asia/Hong_Kong"}},
    {"key":"alight","endpoint":arrival_airport,
     "arrival":{"kind":"unknown","notes":"到达时刻未记录"}}
  ]
}}
```

Call 必须有 endpoint，以及 arrival/departure 至少一个。CallTime 有三种：

- exact：裸 `{local, timezone, offset?}`；
- estimated：`{kind:"estimated", value:{local, timezone, offset?}}`；
- 明确未知：`{kind:"unknown", notes?}`。

不要把 departure 复制为 arrival，也不要用耗时推另一端。`parts.calls` 按 key 返回稳定 Call handle，可跨请求使用；同一成功 request 重放不新增对象。新 request 的同名班次不会自动模糊去重，调用方应先 read 并复用已有 Service。

`mode=other` 时 Service 必须给 `mode_label`。scheduled Leg 会继承这个明确标签，调用方无需重复填写。

### 单调补全 Service

```python
{"method":"service.update","args":{
  "target":flight,
  "operator":"示例航空",
  "call_updates":[
    {"target":alight_call,
     "arrival":{"local":"2027-04-11T00:30:00","timezone":"Asia/Tokyo"}},
    {"target":board_call,"refine_endpoint":airport_t3}
  ]
}}
```

operator 只能从缺失补为已知；Call arrival/departure 只能从缺失或 explicit unknown 补为已知，或给缺失字段写 explicit unknown。同值为 `no_change`，已知非同值返回 `SERVICE_FACT_REPLACEMENT_REQUIRED`。

`refine_endpoint` 只允许 Place → 该 Place 自己的 AccessPoint。已是同一 AccessPoint 为 no_change；AccessPoint→Place、兄弟 AccessPoint 或异地替换拒绝。Service/Call id、Call 顺序、其他时间不变。

## Journey 的 independent 与 scheduled Leg

每个 Leg 二选一。未选定班次、步行、自驾、出租车，或只有线路/大致时段时保持 independent：

```python
{"key":"bus","mode":"bus","from":stop_a,"to":stop_b,
 "timing":{"kind":"boundaries","start":{"kind":"unknown"},
           "duration":{"min_minutes":50,"max_minutes":50}}}
```

这可忠实表达“开始未知、耗时已知”。不要为满足 duration 伪造 start。

接驳车、接驳巴士、摆渡车、班车、shuttle bus 或 shuttle coach 若明确是道路客运车辆，规范写法仍是 `mode: "bus"`。mode 与班次身份分开判断：operator 未知可以省略，不阻止创建 TransportService；service number、service date 与合法 Calls 明确时使用 scheduled Leg，即使部分 Call 时间是 explicit unknown。只有缺少必要的 service number/service date，或来源不足以建立合法 Calls 时，才按 independent bus Leg 记录已知端点和时间。不要因为班次资料不完整而降为 `other`；只有 “shuttle” 本身未说明车辆类别时才保留类别歧义。

明确班次使用 Service 和它自己的 Call handles：

```python
{"key":"flight","mode":"air","service":flight,
 "board_call":board_call,"alight_call":alight_call}
```

scheduled 分支不能再给 from/to/timing；端点和时刻只从 Calls 读取。Call 必须属于所选 Service、顺序正确，board 有 departure、alight 有 arrival；值可以 explicit unknown。

`journey.compose` 仍逐对要求 Connection。以下示例只记录明确资料，省略的行李、空侧与保护状态保持未记录：

```python
{"method":"journey.compose","as":"trip_item","args":{
  "day":day,"title":"接驳与航班",
  "legs":[independent_leg, scheduled_leg],
  "connections":[{
    "key":"airport","from":"bus","to":"flight","kind":"transfer",
    "steps":[{"kind":"terminal_transfer","necessity":"unknown",
              "duration":[40,55],"place":terminal_t2}],
    "connection_protection":"unknown"
  }],
  "timing":{"kind":"derived"}
}}
```

`timing={"kind":"derived"}` 是 1.0 的便捷写法：工具在 Journey 创建后指向它自己，不要求手编领域 ID。省略 timing 仍是 unknown。来源明确给出更宽的酒店出发、步行或候车包络时，应把该整体时间写在 Item，而不是 derived。

Connection 可写 `steps`、`connection_protection`、`baggage_through`、`airside_stay`、`required_buffer` 和 notes。`connection_protection` 取 protected/unprotected/unknown；`baggage_through` 与 `airside_stay` 分别取 yes/no/unknown。TransferStep 的 `kind` 是调用方从来源中选定的非空开放字符串，`necessity` 取 required/not_required/unknown，`place` 接受 Place 或 AccessPoint handle。step.duration 与 Connection.required_buffer 都接受分钟 number 或 `[min,max]`，但两者是不同事实；40–55 分钟摆渡只写 step.duration，不能自动写 required_buffer。

TransferStep 也可带低层规范 `deadline` TimeConstraint；当前不会把其中领域Ref转换成friendly handle，也不会自动生成、推算或单独评估该截止条件。它与 TimePlan 中支持 `relative_to.target` 的友好约束输入不是同一接口。没有已经装配好的规范截止结构时应省略，不手编ID。

回执 `parts.legs` 与 `parts.connections` 按 key 返回稳定 handles。未给 Connection key 时用相邻 Leg 的 `from->to` 作为回执键。

### 渐进编辑 Journey

`journey.edit.target` 使用 compose 返回的 current transport Item handle：

```python
{"method":"journey.edit","args":{"target":trip_item,"edits":[
  {"action":"set_independent_timing","target":bus_leg,
   "timing":{"kind":"fixed","start":{
     "local":"2027-04-10T14:30:00","timezone":"Asia/Hong_Kong"}}},
  {"action":"bind_service","target":flight_leg,
   "service":flight,"board_call":board_call,"alight_call":alight_call},
  {"action":"enrich_connection","target":connection,
   "kind":"transfer","baggage_through":"unknown",
   "add_steps":[{"kind":"security","necessity":"required"}]}
]}}
```

`set_independent_timing` 替换完整 independent timing，不改 Leg id、端点、mode 或 path。scheduled Leg 的时刻只能补 Service.Call。

`bind_service` 保留 Leg id，只允许 mode 与端点完全一致的 independent→scheduled。原 timing 必须恰为 `{"kind":"unknown"}`，或已有 start/end 与 Calls 在值、时区、offset 和 certainty 上逐项相同，且没有 notes、constraints、duration 或关系等无法迁移的事实。否则返回 `LEG_TIMING_MIGRATION_REQUIRED`，不会吞掉旧时间。回执列出迁移去重的边界，并给 `TIME_PROJECTION_REVIEW`，提醒复核保留的 Item 整体 timing。

`enrich_connection` 只允许 unknown/缺失 → 已知；kind 和已记录的枚举、buffer、notes 不能换成非同值。步骤用 `add_steps` 追加，不能整表替换或 clear。Call endpoint 精化与 Connection 补步骤可以放在同一原子批次，按最终状态诊断。

## Route 内的 Leg

原 inline Segment 不变。需要给某段记录独立时刻或班次时使用 `leg` 分支：

```python
{"key":"bus","from":"stop-a","to":"stop-b","leg":{
  "mode":"bus",
  "timing":{"kind":"fixed","start":{
    "local":"2027-04-10T14:30:00","timezone":"Asia/Hong_Kong"}},
  "notes":"有发车时刻但没有服务号"
}}
```

没有 service_number/date 时保持这种 independent Leg，不制造 Service。scheduled `leg` 改用 service/board_call/alight_call，Calls 的端点必须与两端 Stop endpoint 完全一致。回执 `parts.legs[key]` 返回 Leg，`parts.segments[key]` 返回所属 Segment。

`route.edit.target` 仍是 current route Item；两个新动作的 target 是 leg-backed Segment handle：

```python
{"action":"set_leg_timing","target":bus_segment,"timing":{"kind":"unknown"}}
{"action":"bind_service","target":bus_segment,
 "service":bus_service,"board_call":board_call,"alight_call":alight_call}
```

语义与 Journey 对应动作相同。inline Segment 不能借此获得时间，跨 Route handle 拒绝。Route compose 同样支持顶层 `timing={"kind":"derived"}` 自动指向刚创建的 Route。

Route 没有 Connection 表，不做 Journey 式换乘或buffer评估。Service.Call 后续从粗 Place 细化为 AccessPoint，若 Leg 端点不再与所连 Stop endpoint 精确相同，会给 `ROUTE_LEG_ENDPOINT_REVIEW` warning，返回 Segment、Leg 和两端 Stop 引用；工具不修改 Stop、不补接驳Leg，也不据此宣称路线已经连通。

## 诊断、保护与边界

1.0 的成功回执、check 和 export validation 都返回 `transport_assessments`。对每个 Connection.required_buffer：

- 两端 exact 且 gap ≥ max 为 satisfied；
- gap < min 为 violated，并有 `CONNECTION_BUFFER_VIOLATED` warning；
- gap 落在区间内部、任一端 estimated/unknown，或未给 buffer，均为 unknown。

满足 buffer 只证明这个明确输入条件满足，不证明接续可行。相邻端点不同且明确转移资料仍不完整时报告 `JOURNEY_TRANSFER_DETAILS_UNKNOWN`，不自动创建接驳 Leg。

exact scheduled 到达早于出发报 `LEG_TIME_REVERSED`；相邻 Leg 后段开始早于前段结束报 `CONNECTION_TIME_REVERSED`。两者是 error，整批回滚。跨午夜、跨时区按 UTC instant 比较。

改变 independent Leg 的已有时间或 bind Service 时，检查 Leg、Route内拥有它的Segment、所属 Journey/Route 与主 Item 上的 confirmed/current/done/confirmation 等结构化 blocker；命中返回 `PLAN_TIME_CHANGE_BLOCKED`，外部记录不变。补充原先 unknown 的边界可以保存。工具不扫描自由文字判断已执行，也不改 Reservation、Coverage、Cost、Payment、Task 或 Claim。

本批不提供换班、改 Service 身份、已知 Call 改期、Connection 改绑、任意 endpoint 纠错、路径实测导入或车辆入口。遇到这些情况应保留来源与缺口，等待对应受控方法；不要重建重复 Item/Leg 冒充修订。Journey/Route 的 participants 已可使用稳定 member/group handle，见[成员指南](PARTY_GUIDE.md)。
