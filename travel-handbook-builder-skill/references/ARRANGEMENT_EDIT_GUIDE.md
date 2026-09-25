# 安排移动、日期与局部执行替换指南

本文说明六个受控编辑入口：`plan.move`、`plan.withdraw`、`day.update`、`trip.change_dates`、`journey.replace_leg`、`route.replace_interval`。稳定数据契约 1.0 支持这些操作，也支持把同一待排 Item 归入 Day。

这些方法只编辑现有身份和归属，不重新规划旅行、不自动排序、不平移执行时间，也不取消现实订单或付款。

## 移动与排序

```python
{"method": "plan.move", "args": {
  "target": item,
  "day": target_day,
  "before": later_item
}}
```

省略 `before` 时追加到目标 Day 末尾；提供时，锚点必须是目标 Day 的 current Item。工具先把 target 从原 Day 移出，再按目标 Day 的剩余顺序插入，不复制 Item。无按时间排序。同日以自身为 `before` 是 `no_change`；来自其他 Day 或待排列表的 Item 不能用自身充当目标 Day 锚点。

1.0 的待排 Item 可用同一方法归日，Item、已有时间、参与范围、Journey/Route 和内部对象身份全部保持。`plan.move.unassigned_item` 的 capability 门槛为 1.0。首次归日复用时间诊断的确定性边界解析：开始日期未知时不猜日期并允许归日；已解析日期与目标 Day 匹配时正常归日；若已解析日期与目标 Day 矛盾且相关确认、权益、费用、付款、完成待办或 Claim 已保护该含义，则以 `PLAN_TIME_CHANGE_BLOCKED` 原子拒绝。没有 blocker 的矛盾仍保存并返回下述 warning。

跨日只改变 Day 归属。固定时刻、TransportService 的 service_date/Calls、Stay 期间、Task 截止和 Coverage 有效期都不变。若已知时刻落在新 Day 的其他日期，receipt/check 返回 `TIME_DAY_OWNERSHIP_MISMATCH`；调用方须复核并通过各对象自己的编辑方法显式更正，不能把 warning 当作已自动重排。

若从一个 Day 移到另一个日期或时区会改变由 confirmed Reservation、当前 Coverage、confirmed active Cost、settled Payment、done Task 或 adopted confirmation/observation 所保护的日历含义，调用以 `PLAN_TIME_CHANGE_BLOCKED` 原子拒绝。检查包括 Item 及其有限 Journey/Route、Leg、Stop/Segment、TransportService/Call 与 Stay Unit 所属链。同日展示顺序不改变日历含义，因此不会被这些事实粗粒度阻挡。

## 撤下安排

```python
{"method": "plan.withdraw", "args": {
  "target": item,
  "reason": "改为不执行该安排"
}}
```

`reason` 必须是非空审计说明，保存在成功 receipt 的 `parts.reason`。方法把 Item 从当前 Day 或 1.0 待排列表移除并标记 `retired`；若主对象是 Journey 或 Route，也同步标记该主对象 retired。Leg、Stop、Segment、Place 和所有其他子对象不删除、不改字段。

撤下不等于取消现实承诺。Reservation、Coverage、Cost、Payment、Task、Claim 全部保留；active Cost 继续进入 `budget_projection`。receipt 的 `parts.review_refs` 列出与 Item 及其执行所属链相关的当前确认、active Cost、关联 Payment、Task 和 Claim，调用方据此逐项决定是否还需现实取消、退款或人工复核。再次撤下同一 retired Item 返回 `no_change`；本入口不恢复 retired 安排。

若相关 GuideNote 或 open Issue 只关联 Place、文字却描述「当前到访/冲突」，`plan.withdraw` 不会自动改写或解决它们。managed 续作可对该 Place 调用 `client context`，从 `related_items`、`related_guide_notes`、`related_issues` 的有界集合复核当前状态，再按旅客决定显式修订；`plan.move`、`plan.update` 改期后亦同。日期本身的来源事实可保留，不能把撤下等同于来源失效。

## 修改 Day 日期或时区

```python
{"method": "day.update", "args": {
  "target": day,
  "date": "2027-04-11",
  "timezone": "Australia/Hobart"
}}
```

至少提供 `date` 或 `timezone`，只修改明确提供的字段。Day 标题、item_refs 和所有 Item/Service/Stay/Task/Coverage 字段保持。日期使用 ISO 自然日，时区使用 IANA 名称。

对已有 Item 而言，Day 日期或时区变化与跨日移动使用同一有限所属链事实保护。无 blocker 时允许保存，并通过时间诊断报告新的 Day 归属不一致；有 blocker 时整批拒绝，不能靠改 Day 绕过单 Item 时间保护。

Day 自身若有 adopted confirmation/observation Claim 精确指向 `date` 或 `timezone`，该字段的实际变化也会被原子拒绝，包括没有 Item 的空 Day。保护按字段生效：日期 Claim 不阻挡单独修改时区，时区 Claim 不阻挡单独修改日期；把字段提交为当前同值仍是 `no_change`。

## 修改 Trip 日期范围

```python
{"method": "trip.change_dates", "args": {
  "start_date": "2027-04-11",
  "end_date": "2027-04-13"
}}
```

至少提供首尾之一；省略的一端保持。最终 `start_date` 不得晚于 `end_date`。方法不批量移动或删除 Day，不修改班次、Stay、Task、Coverage 或 Item 时间。

若既有 Day 落在新范围外，receipt/check 返回每个 Day 独立的 `DAY_OUTSIDE_TRIP_RANGE` warning，包含 `day_ref`、Day 日期及新首尾日期。warning 是明确复核清单；它不表示这些 Day 已重新安排，也不阻止保存范围。

## 替换 Journey 的一个执行 Leg

```python
{"method": "journey.replace_leg", "args": {
  "target": transport_item,
  "leg": old_domestic_leg,
  "replacement": {
    "key": "domestic-319",
    "mode": "air",
    "service": new_service,
    "board_call": new_board_call,
    "alight_call": new_alight_call
  },
  "connections": [{
    "key": "terminal-shuttle-319",
    "from": unchanged_international_leg,
    "to": "domestic-319",
    "kind": "transfer",
    "baggage_through": "unknown",
    "steps": [{"kind": "terminal_shuttle", "necessity": "required",
               "duration": [40, 55]}],
    "notes": "T3 到 T2，针对新国内段明确重述"
  }],
  "reason": "只换国内段为 SYN319"
}}
```

`target` 必须是 current transport Item，`leg` 必须属于它的唯一 Journey。`replacement` 完全复用 `journey.compose` 的单个 Leg 输入：scheduled Leg 提供 service 与两个 Call；independent Leg 提供明确 from/to，可选 timing、path、vehicle 等既有字段。工具总是创建新 Leg 身份，不修改旧 Leg 的名称或 Service 来冒充同一次执行。

`connections` 只提交被替换 Leg 两侧的最终相邻 Connection，数量必须为 0、1 或 2，与目标在 Journey 中的位置完全一致。既有相邻 Leg 用稳定 handle，新 Leg 用 `replacement.key` 字符串；每一侧的 kind、steps、buffer、行李、保护和说明都须明确给出。旧 T3→T2 摆渡资料不会自动复制到新国内段；仍适用时像上例一样重述。与目标不相邻的 Connection 逐值保持。

成功 receipt 的 `parts.legs`、`parts.connections` 给出可在同批后续动作继续引用的新 handle；`parts.kept/created/removed` 和 `parts.replacements` 说明身份变化。旧 Service/Calls 保留，但旧 Leg 和相邻 Connection 从当前 handle 枚举移除，旧 handle 不能再写入，也绝不重指新对象。相同成功 request 原样重放仍返回原 receipt；若当前 revision 已超过该次提交，返回 `historical_receipt=true` 和原 `original_commit_revision`，这不恢复旧对象为 current。

## 替换 Route 的一个区间

```python
{"method": "route.replace_interval", "args": {
  "target": route_item,
  "from_stop": ridge_stop,
  "to_stop": lake_stop,
  "interior_stops": [
    {"key": "lookout", "place": lookout_place, "purpose": "北眺"}
  ],
  "segments": [
    {"key": "ridge-lookout", "from": "from", "to": "lookout",
     "mode": "other", "mode_label": "hiking"},
    {"key": "lookout-lake", "from": "lookout", "to": "to",
     "mode": "other", "mode_label": "hiking"}
  ],
  "reason": "在山脊与湖畔之间插入北眺台"
}}
```

两端必须是同一 current Route 中先后不同的 Stop；它们保留身份。端点在新 `segments` 中分别使用保留字 `from` 与 `to`，内部 Stop 使用各自非重复 key。`segments` 必须按声明顺序完整连接 `from → 内部点… → to`；没有内部点时传空 `interior_stops` 和一段 `from → to`。inline 与 leg-backed Segment 输入均复用 `route.compose`。工具不补直线、不猜模式，也不继承旧区间的距离、耗时、路径或班次。

所有内部 Stop、Segment 及其专属 Leg 都分配新身份。即便折返到相同 Place，“第二次山脊”仍要创建新的 Stop occurrence。区间外 Stop/Segment/Leg 及字段逐值保持，因此南步道口→首次山脊的轨迹、90–120 分钟区段和湖畔→车站的 14:30 巴士不会被清除；13:50 接驳是替换区间内另一个新 Leg。

Route 级 `path_ref/path_usage/overall_estimate` 在拓扑变化后可能误导。只要存在任一字段，就必须传 `clear_stale_summary=true`；工具仅在对应 Route 字段没有 adopted 或 superseded confirmation/observation Claim 保护时原子清除。省略标志或字段受保护均返回 `ROUTE_SUMMARY_REVIEW_REQUIRED`，不会留下新拓扑配旧全程摘要。主 Item 的显式 TimePlan 保持并在 receipt 返回 `ROUTE_TIME_PLAN_REVIEW`；已有 现有 时间事实保护仍会在整批检查中拒绝受保护投影变化。

## 删除保护与来源边界

两个替换入口都会在删除前检查旧 Leg、相邻 Connection、内部 Stop/Segment 和专属 Leg。Claim、GuideNote、Task、Reservation、当前或历史 Coverage、Cost 等任何仍指向旧对象的领域引用，以及现有 `source.duration` 活字段 binding 的 target/part，都会返回 `EXECUTION_HISTORY_REQUIRED` 和引用路径。方法不会删除保护记录、把它改指新对象或复制票券/权益来换取成功。

整 Journey 或 Route/Item 上的结构化确认、权益、已确认费用、结算付款、done Task 与 execution Claim 也按具体字段检查。adopted 或 superseded 的 `timing/movement`、Journey `leg_refs/connections`、Route `stops/segments` 等执行组合字段继续阻止替换；disputed Claim 和只描述 `title/notes` 等未改字段的 Claim 保持且不阻挡。若 Claim 直接引用将删除的局部对象，则不论 field/disposition 都严格拒绝，不能留下悬空引用。若旧 Task 只关联到整个 Item，结构无法证明它与替换区间无关，调用仍会保守拒绝；首次编制时应把确有局部作用域的事实关联到可证明的具体对象。

成功 receipt 的 `kept/created/removed` 按替换前对象集划分：三组互斥，旧集合等于 `kept ∪ removed`，新集合等于 `kept ∪ created`。新建 Leg 不会同时列入 kept。

当前工作区没有通用 identity 索引或 topology baseline 写入口。纯 identity 索引只在受支持的 typed 替换中转历史 tombstone；活字段 binding 继续阻止删除；历史 topology baseline 不构成活引用。不要虚构 `source.binding.*` 方法，也不要把未知索引一律当作删除 blocker。

## 原子性与重放

六个方法沿用共同批次协议。任一步或最终校验失败，归属、lifecycle、日期、执行链、revision 和 receipt 都不改变。相同成功 request_id 与完全相同载荷重放时返回历史成功结果，不重复移动、退役或创建执行，也不把后来状态回写为旧快照。

本入口不支持恢复 retired 安排、自动取消订单/权益/付款、未知 Trip 日期、多人并行重排、整条 Route 拆分、承接必须保留的旧片段执行历史，或按旧 semantic key 恢复已删除拓扑。Typed Route 的 `source_adoption` / tombstone 只按[来源采用协议](SOURCE_ADOPTION_GUIDE.md)开放；不能据此宣称通用来源重译。
