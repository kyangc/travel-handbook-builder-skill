# 未定购物地点调用指南

本指南描述 可用的 shopping 地点创建、绑定、替换与清除。它只适用于已经决定进行的购物，例如“购买伴手礼，但还没选店”。“也许去购物”或尚未选择的活动仍是候选，不应创建正式 Item。

## 创建

`new_workspace` 只建立编制容器；调用 `trip.define` 后即可创建地点尚未明确的 shopping Item：

```python
{"method": "plan.add", "as": "gift_shopping", "args": {
  "day": day_handle,
  "kind": "shopping",
  "title": "购买伴手礼",
  "purpose": "已决定购买，店铺未定"
}}
```

省略 place 表示当前没有记录购物地点，不表示现实中没有地点。结果是正式 Item，并保留稳定身份：有 day 时进入 Day.item_refs；1.0 中省略 day 时进入 Trip 的待排列表，见[待排日期指南](UNASSIGNED_ITEM_GUIDE.md)。shopping 可以暂时没有地点；visit 仍要求地点，不能用无地点 visit 表示候选景点。

`plan.add.shopping_without_place` 和 `plan.update.shopping_place` 都属于稳定数据契约 1.0，可直接使用。

## 绑定、替换和清除

地点变化通过现有 plan.update 的受限字段完成：

```python
{"method": "plan.update", "args": {
  "target": shopping_handle,
  "set": {"place": shop_handle}
}}

{"method": "plan.update", "args": {
  "target": shopping_handle,
  "clear": ["place"]
}}
```

set.place 接受同一工作区中的 Place handle；不能传底层 `{"type":"place","id":...}` Ref、null 或占位 Place。首次绑定和替换使用同一写法。clear.place 恢复为地点未记录。每次变化保持 Item id、Day.item_refs 顺序、标题、时间、参与范围、目的和说明；不退休或新建 Item。

设置当前同一 Place，或对已经无地点的 shopping 再 clear，返回 no_change。若同一动作还包含其他合法变化，只应用那些变化。place 不能同时 set 和 clear。非 shopping、退役 Item、不受支持的 Schema 版本均不能用这个入口改变 place。

## 地点未知诊断

当前无地点的 shopping 会在 apply/check/export 返回：

```text
SHOPPING_PLACE_UNKNOWN
unknown = [map_location, opening_hours]
```

这是信息提示，不是结构错误；保存仍然成功。绑定 Place 后只消除此项“地点未记录”提示。Place 身份本身不证明已有坐标、地图入口、营业资料或当前营业可行性；消费者必须继续检查 Place 的实际字段，不能把 warning 消失解释成地图和营业均已确认。退役 shopping 不产生该当前计划提示。

## 地点变化保护

首次绑定、替换和清除只要真的改变 place_ref，就检查以下结构化事实：

| blocker | 精确条件 |
|---|---|
| Reservation | status=confirmed，target_refs 直接包含该 Item |
| Coverage | 当前确认投影中的 effective active scope 直接指向该 Item；1.0 纯检查回退到整体 active 语义 |
| Cost | status=active、存在 confirmed，target_refs 直接包含该 Item |
| Payment | status=settled，且其 cost_refs 或 reservation_ref 所指记录再直接关联该 Item |
| Task | status=done，target_refs 直接包含该 Item |
| Claim | target.object_ref 为该 Item、field=place_ref、basis 为 confirmation/observation，且 disposition 为 adopted 或省略 |

存在 blocker 时返回 `PLAN_PLACE_CHANGE_BLOCKED`，details 中包含 `blockers` 和 `blocker_refs`；整个批次回滚。方法不会自动撤销订单、转移权益或费用、改写付款、重开任务、取代 Claim，也不会为新地点复制这些事实。

同地点 set 和空 clear 在 blocker 检查前识别为 no_change，所以不会因为已有执行事实而失败。Coverage 只使用当前确认投影：已被后续确认取代的历史 active scope，以及当前已 revoked 的 scope，不阻止地点变化。

保护是刻意有界的。pending Reservation、estimate-only Cost、pending Payment、open Task、disputed/superseded Claim 和普通 authoring_statement 不阻挡变化。标题、notes、GuideNote 或 Claim.statement 中的“已经去过”等自由文字不会被解析；调用方不能据此声称所有现实发生事实都受保护。

失败保持 Item、Place、外部事实、revision、handle 与回执全部不变。需要改变已有执行事实关联时，应先用对应领域的明确方法处理；当前没有的方法不能通过地点更新旁路实现。
