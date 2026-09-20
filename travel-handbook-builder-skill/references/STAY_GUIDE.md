# 住宿计划输入

沿用 [CALLER_GUIDE](CALLER_GUIDE.md) 的原子批次与 handle。以下内容都是虚构示例。

## 先建立住宿计划，按需补齐

酒店是可复用 Place；每段入住是独立 Stay。同一酒店间隔数日再次入住应新建另一个 Stay，不按酒店去重。`stay.plan` 主回执是 Stay，不是日程 Item；不会自动创建入住/退房事件、预订、付款、待办或票券。

```python
{"method":"stay.plan", "as":"stay", "args":{
    "lodging": hotel,
    "use_kind":"overnight"
}}
```

`hotel` 是已有 Place handle 或同批先前的 `{"local":"hotel"}`。无需先补角色，但调用方必须有依据选定这个住宿地点；不能造一个“待定酒店”Place。没有选定酒店时暂保留原文。本轮不支持住宿 ServiceBundle。

| 输入 | 规则 |
|---|---|
| lodging | 必填，Place handle |
| use_kind | 必填，overnight 或 day_use；不默认过夜 |
| period | 可选；省略为 `{"kind":"unknown"}`；已知过夜日期见下方 |
| participants | 可选，count/unknown/all或1.0的members/groups handle形式；省略明确保存 unknown，不猜全体 |
| units | 可选，房间/营位/客舱列表，见下方 |
| requests | 可选，如 `[{"kind":"无烟房","status":"desired","notes":"尚未向酒店申请"}]`；status 仅 desired/requested，均非已保证 |
| night_count | 可选，如 `{"value":3,"basis":"原文明确写明三晚"}`；不自动按日期推算 |
| notes | 可选非空原文说明 |

`participants.count=2` 仅保存人数，不表达“2 成人”资格；成人/儿童构成暂保留 notes。房型中明确的禁烟描述可写 unit.description，未保证的无烟请求应写 requests；不要相互替代。

本轮 period 仅支持 `unknown` 和 `local_dates`：

```python
period = {"kind":"local_dates", "check_in":"2026-10-02",
          "check_out":"2026-10-05", "timezone":"Asia/Tokyo"}
```

退房必须晚于入住，时区明确提供，不能填同日冒充日用房时段。`day_use` 当前主期间及各 Unit 期间均仅能记 unknown；已知日用钟点、跨时区的固定期间、邮轮 service_period 仍缺公开入口，保留文字并报告缺口，不能谎称已结构化。

## 房间单位有独立使用期间

```python
{"method":"stay.plan", "as":"stay", "args":{
    "lodging": hotel, "use_kind":"overnight", "period":period,
    "participants":{"kind":"count","count":2},
    "night_count":{"value":3,"basis":"原文明确夜数"},
    "units":[{"key":"room-a", "kind":"room", "count":1,
              "description":"示例双床房", "period":period}]
}}
```

每个 unit 需要 key、kind（room/pitch/cabin）和正整数 count。可选 period、description、occupants（Participants）、notes。1.0成员handle见[成员指南](PARTY_GUIDE.md)。省略 occupants 表示房间分配未知，不继承 Stay 全体；省略 unit.period 为 unknown，**不继承 Stay.period**。相同房型但不同入住期间应分成不同 unit；工具不从入住人数反推房间数。

回执 `operations[i].parts.units["room-a"]` 是稳定 Unit handle。同批可通过 `{"local":"stay","part":{"kind":"unit","key":"room-a"}}` 引用。units 的 key 在本次操作内不可重复；之后操作的 key 不是持久业务 ID，更新必须用 handle。

## 改计划而不修改供应方确认

```python
{"method":"stay.change_plan", "args":{
    "target":stay,
    "set":{"period":{"kind":"local_dates","check_in":"2026-10-02",
                      "check_out":"2026-10-06","timezone":"Asia/Tokyo"}},
    "clear":["night_count"],
    "append_note":"调用方明确延长整体住宿计划；房间安排另行确认"
}}
```

set 可改 use_kind、period、participants、requests、night_count、notes。clear 仅可移除 requests、night_count、notes；参与者未知用 `set.participants={"kind":"unknown"}`，不能清空触发“全体”缺省；未知期间用 `set.period={"kind":"unknown"}`。字段整体替换，省略保持；不支持 status/confirmed、id、直接 lodging_ref 或整表替换 units。

已有 night_count 时，改变 period/use_kind 必须在同一调用显式 set 或 clear 夜数，避免沿用过期数字。工具不会强制夜数等于日历日期差，也不会重写其 basis；调用方需按来源判断。不同酒店须新建 Stay；不允许原地更换 lodging，避免旧房型和请求悄悄变成新酒店的信息。

units 使用显式编辑列表，可单独调用，也可与 Stay 字段一起提交：

```python
{"method":"stay.change_plan", "args":{
    "target":stay,
    "units":[
        {"action":"update", "target":room,
         "set":{"period":period}, "append_note":"明确确认本房间的计划日期"},
        {"action":"add", "key":"room-b",
         "value":{"kind":"room","count":1,"description":"新增加的房间"}}
    ]
}}
```

update 可 set kind/count/period/description/occupants/notes；clear 仅 description/occupants/notes。必须是本 Stay 的 Unit，身份不变。新增单位回执仍在 parts.units；本轮不删除 Unit，不悄悄破坏未来票券/订单的引用。

Stay 改期不移动各 Unit 的期间；Unit 改期不改 Stay。期间是否覆盖、人数是否相符、是否与供应方确认一致，还需调用方核对。check.valid 不保证可入住、房量、价格、供应方承诺或整份材料完整。

`task.add.targets` 可以直接引用 Stay 或其 Unit，也可与 Trip/Item 混合引用。例如：

```python
{"method":"task.add", "args":{
    "title":"核实本房间的无烟需求", "action":"verify", "targets":[room],
    "notes":"尚未取得供应方承诺"
}}
```

同批可用 `{"local":"stay"}` 或 `{"local":"stay","part":{"kind":"unit","key":"room-a"}}`。新增待办为 open，`task.complete` 只记录动作完成，不修改 Stay/Unit，不生成预订、已获权益或付款。Place、Recommendation 及其他局部类型尚不能作为待办目标。入住/退房办理 Item 仍没有专门创建入口。

非法输入、跨 Stay 的 Unit 编辑、未知 handle、重复 key、未处理旧夜数，都拒绝整批提交；本批之前的合法修改也不会留下。
