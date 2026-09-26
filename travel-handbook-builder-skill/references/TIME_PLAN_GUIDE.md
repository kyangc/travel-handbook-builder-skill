# 常用时间输入指南

本文说明 可用的时间输入、有限诊断和事实保护；1.0 完整继承这些能力。它不选择时间、不自动排程，也不证明交通、营业或衔接可行。

新建 Trip 直接使用稳定数据契约 1.0，以下时间结构均可直接调用。不要手工修改 `schema_version`。

## 可直接输入的时间

`plan.add(..., timing=...)`、`plan.update(target, set={"timing": ...})`、`journey.compose(..., timing=...)` 和 `route.compose(..., timing=...)` 共用同一封闭输入。所有 ZonedDateTime 都必须显式提供当地日期时间和 IANA 时区；跨时区端点分别写自己的时区。

对已选游览 Item，先复用它已有的起止边界；两端足够明确时，本次停留时长由该时段得出，不再另写一个会漂移的数字。只知道本次预计停留长度时，可用 `timing={"kind":"boundaries","start":{"kind":"unknown"},"duration":{"min_minutes":60,"max_minutes":90}}` 这样的受支持形式保留未知起点，不为凑时长发明开始或结束时刻；通用的 `Place.content.duration_advice` 不能替代本次安排。相邻活动之间的时间差可能包含用餐、排队或自由活动，不能据此推算交通时长。

只知道明确结束时，可使用 end-only；工具不会补开始、午夜或零时长：

```python
{"kind": "fixed", "end": {
    "local": "2027-04-10T18:00:00", "timezone": "Australia/Hobart"
}}
```

两端确定性不同时使用 `boundaries`。裸 ZonedDateTime 是 exact；estimated 包装只约束这一端：

```python
{"kind": "boundaries",
 "start": {"local": "2027-04-10T09:00:00", "timezone": "Australia/Hobart"},
 "end": {"kind": "estimated", "value": {
     "local": "2027-04-10T11:00:00", "timezone": "Australia/Hobart"
 }}}
```

明确不知道某端可写 `{"kind":"unknown"}`。省略字段表示本次没有提交该事实；两者都不会从 Day、另一端或系统时钟推断值。

相对结束引用已有 Item 或 Activity handle，不复制目标当前时刻：

```python
{"kind": "estimated",
 "start": {"local": "2027-04-10T18:30:00", "timezone": "Australia/Hobart"},
 "end_from": {"target": boarding_item, "field": "start", "offset_minutes": 0}}
```

`target` 也可用同批更早的 alias。被引用边界以后变化时，投影随关系重新计算；目标缺少所需边界时关系保留、结果为 unknown。来源没有可识别的登机对象或时刻时，应在 GuideNote/引用中保留原文并报告来源不足；不能把起飞 Call 当登机边界，也不能制造占位 Activity。

约束可使用绝对时刻，或用友好的 `relative_to.target` 引用 Item/Activity：

```python
{"kind": "unknown", "constraints": [{
    "kind": "after", "applies_to": "start",
    "time": {"local": "2027-04-10T17:00:00", "timezone": "Australia/Hobart"}
}]}

{"kind": "fixed",
 "start": {"local": "2027-04-10T17:30:00", "timezone": "Australia/Hobart"},
 "constraints": [{
    "kind": "not_before", "applies_to": "start",
    "relative_to": {"target": prior_item, "field": "end"},
    "minutes": 15
 }]}
```

`after` 是严格大于；恰好等于阈值为 violated。`not_before` 包含等号。estimated、缺失或无法唯一求值的目标/锚点产生 unknown，不升级为 satisfied。

## 读取诊断

成功 apply 回执、`check` 和 `export_package` 的验证结果都可包含 `time_assessments`。每条约束逐条返回 `status=satisfied|violated|unknown`、目标引用和路径；violated/unknown 也出现在 warnings。调用方应读取 assessment，不能把“没有 warning”当作某条约束已检查并满足。

工具拒绝以下可确定错误：

- 当地时间在指定时区不存在；
- 夏令时重叠但未提供 offset；
- offset 与该当地时刻、时区不一致；
- 能唯一换算的结束时刻早于开始；
- `end_from` 自引用或形成边界求值循环；
- 引用不存在或引用类型不符。

夏令时重叠时显式 offset，例如 `"offset":"+02:00"`。offset 必须与时区在该时刻的实际偏移精确相等，历史带秒偏移不会被截断成分钟后误接受。

Item 的可解析 start 转换到所属 Day.timezone 后若日期不同，返回 `TIME_DAY_OWNERSHIP_MISMATCH` warning；只有 end 或 start 无法解析时返回 `TIME_DAY_OWNERSHIP_UNKNOWN`。两者都不改 Day、不平移时间，也不拒绝提交。

1.0 的已选待排 Item 没有 Day，返回 `TIME_DAY_UNASSIGNED` warning，不猜归属日期。Item 自身的明确边界、相对依赖和约束仍照常解析、评估并进入 `time_assessments`；只跳过必须依赖所属 Day 的日期匹配。创建与读取归属见[待排日期指南](UNASSIGNED_ITEM_GUIDE.md)。

## 替换与保护

`plan.update.set.timing` 替换完整 TimePlan，不做子字段合并。要保留的 start、end、notes 和 constraints 必须在新对象中一并提供。完全撤回时间表达时显式写 `{"kind":"unknown"}`。

已有 confirmed Reservation、当前有效 Coverage、已确认 Cost、settled Payment、done Task，或已采用 confirmation/observation Claim 保护 Item/Activity 的 timing 时，修改或删除既有时间事实会以 `PLAN_TIME_CHANGE_BLOCKED` 原子拒绝，并返回 blockers、引用和有限依赖路径。整批比较会捕获锚点或 Route 耗时变化造成的间接投影变化；给依赖对象补 notes 不能绕过保护。

补充原先缺失或显式 unknown 的边界仍允许，只要没有改动或删除既有边界、确定性、关系、窗口或约束。例如保留 exact start 后补 end、保留 exact end 后补 start、或把 boundaries 的 unknown start 补成 exact 都不会因为同一对象有其他保护事实而被粗粒度锁住。方法不会同步 Reservation、Coverage、Cost、Payment、Task 或 Claim；回执中的 review refs 只提醒调用方复核。

## 当前边界

1.0 同时允许 TransportService 缺少 operator，并增加成员年龄、声明类别及 Trip 所属的 member/group LocalRef 结构；这些结构与公开方法在 1.0 继续有效。班次记录、Leg绑定与接续已经有公开入口，见[班次与接续指南](TRANSPORT_SERVICE_GUIDE.md)；成员、分组和参与范围的公开方法见[成员指南](PARTY_GUIDE.md)。

Journey 可从首末 Leg 投影边界。Route 只有在首末 Segment 引用 Leg 且首尾 Stop dwell 明确为零时才使用这些端点；非零或未知停留保持 unknown。含 Leg 的 Route 总时长不会把各段行驶时间直接相加，因为固定候车或接续等待尚未求值。现有 只做上述有限投影和诊断，不提供通用依赖图、排程、时长求解或现实可行性结论。
