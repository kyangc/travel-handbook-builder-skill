# Travel Handbook Authoring public API

This index contains the callable protocol and method inventory. Read `CALLER_GUIDE.md` first, then only the topic guides needed for the supplied material. Live `read.capabilities` remains authoritative.

## 运行

安装后的 Skill 使用下列 `scripts/travel-handbook` 启动器；在开发仓库中可将每条命令等价替换为 `python3 -m authoring`。两种入口使用同一核心：

```sh
scripts/travel-handbook create /tmp/lunch-authoring-state.json --title 示例午餐行 --example
scripts/travel-handbook import /tmp/existing-trip.json /tmp/imported-state.json
scripts/travel-handbook apply /tmp/lunch-authoring-state.json /tmp/lunch-request.json
scripts/travel-handbook preview /tmp/lunch-authoring-state.json /tmp/lunch-request.json
scripts/travel-handbook read /tmp/lunch-authoring-state.json
scripts/travel-handbook check /tmp/lunch-authoring-state.json
scripts/travel-handbook export /tmp/lunch-authoring-state.json /tmp/lunch-trip.json --revision 1
```

create/export 拒绝覆盖已存在的目标，apply 只替换指定状态文件。失败退出非零并输出 JSON 诊断；check 未通过也退出非零。CLI 严格拒绝重复 JSON 键与非有限数字。状态和成功回执在同一文件中原子替换；**只支持单写者串行使用**，没有多进程锁、事务数据库或断电持久性保证。状态文件包含编辑信息，应当保留；给网页的是 export 导出的领域 JSON。

`/tmp/lunch-request.json` 最小示例：

```json
{
  "request_id": "create-lunch-1",
  "expected_revision": 0,
  "operations": [
    {"method": "trip.define", "as": "trip", "args": {"start_date": "2026-10-05", "end_date": "2026-10-05", "default_timezone": "Asia/Tokyo"}},
    {"method": "day.add", "as": "day", "args": {"date": "2026-10-05", "timezone": "Asia/Tokyo"}},
    {"method": "place.add", "as": "shop", "args": {"name": "示例荞麦店", "roles": ["restaurant"]}},
    {"method": "plan.add", "as": "lunch", "args": {"day": {"local": "day"}, "kind": "meal", "title": "午餐", "place": {"local": "shop"}}},
    {"method": "task.add", "as": "verify", "args": {"title": "核实是否需要预约", "action": "verify", "targets": [{"local": "lunch"}]}}
  ]
}
```

省略时间、参与者时，安排写入 `unknown`。本例没有价格、预约、付款、坐标或默认参加人数。`as` 是批内别名；下轮使用回执或 read 返回的 `{"handle": "..."}`。底层对象 ID 和 Link、开放规则的局部 ID 均由实现分配。

## Python 与公共协议

```python
from authoring import (new_workspace, import_package, apply, preview,
                       read_workspace, check, export_package)

state = new_workspace("示例午餐行", example=True)
state, receipt = apply(state, request)
view = read_workspace(state)  # 完整读取；局部读取与恢复边界见专门指南
review = preview(state, request)  # 同一 apply 引擎，无提交和临时身份输出
report = check(state)
artifact = export_package(state, revision=view["revision"])
trip_json = artifact["package"]
```

Python API 返回新状态，不改传入状态；异常为 `AuthoringError`，`as_dict()` 给出未提交诊断。不能直接写 state 或 package 修补结果后宣称方法成功。read 的记录是副本，公开 schema_version、capabilities.coordinate_inputs 坐标输入要求及独立 budget_projection，可查当前对象和链接的 owner；无参数保持完整读取，selection/limit/cursor 提供有界局部读取，准确恢复与分页契约见[专门指南](RECOVERY_READ_PREVIEW_GUIDE.md)。

- 一批全部成功才提交；任一步或最终规范校验失败，数据、revision 和成功回执都不改变。不存在跳过错误后部分成功。
- 相同成功 `request_id` 必须携带完全相同载荷（包括原 expected_revision）。重试先查回执，返回原结果及当前 revision，不重复执行，也不把旧快照写回；当前 revision 已超过原提交时另返回 `historical_receipt=true`，旧回执中的失效 handle 仍只是历史。失败请求不记成功回执，可修正后再提交。
- 新请求的 expected_revision 必须匹配当前值；同一成功 ID 换内容报 `REQUEST_ID_REUSED`。不同 ID 不意味着相同业务：重复 `place.add` 会新建地点，重复 append 会再次追加，调用方应复用原请求 ID 重试。
- 更新省略字段保留；`set` 替换指定字段的整体值，嵌套对象不隐式深合并；`clear` 显式删除允许删除的字段；`append_note` 追加文字。同字段不能同时 set/clear/append。直接参数 null 被拒绝，不能把 null 当未知或清空。
- 每次新成功批次 revision 加一，即使某动作回报 `no_change`，以保存新请求回执；成功请求重放不增加 revision。`structured` 表示发生领域写入，不代表来源内容已全部转换、事实已核验或安排可执行。
- 直接动作错误带从 0 起的 `op_index`；基本输入错误尽量带 parameter。最终校验错误保留规范 JSON path，并给 `related_op_indices` 指向相关写操作；跨对象错误可能关联多项，不能将其当精确的唯一根因。

已有住宿订单与确认权益见[订单指南](RESERVATION_GUIDE.md)，住宿和房间计划见 [住宿指南](STAY_GUIDE.md)，独立于日程的地点推荐见 [推荐指南](RECOMMENDATION_GUIDE.md)。

## 当前可调用的写动作

| 方法 | 必须参数 | 可选参数及边界 |
|---|---|---|
| `trip.define` | start_date、end_date、default_timezone | 只能定义一次；标题来自 new_workspace；新包 1.0 |
| `trip.change_dates` | start_date/end_date 至少一项 | 不批量移动 Day；范围外 Day 返回具体 warning 并保留 |
| `party.describe` | count、members_status、clear 至少一项 | 人数和名单完整性独立，不生成匿名成员 |
| `party.member.add` | label | age、declared_category；返回稳定 member handle |
| `party.member.update` | target、set | label可改，年龄/原词类别只补缺失或同值 |
| `party.group.add` | members | label；成员handle去重后建立不可变组 |
| `day.add` | date、timezone | title；顺序按添加顺序，不按日期自动重排 |
| `day.update` | target；date/timezone 至少一项 | 只改明确字段，沿用执行事实日历保护，不改 Item/Service/Stay |
| `place.add` | name | roles 可省略为分类未知；restaurant 映射为 dining |
| `place.update` | target | set、clear、append_note、add_links、replace_weekly_hours；也保留完整 links，至少一个有效修改 |
| `access_point.add` | place、name、kind | location、access_notes、notes；属于一个既有 Place，不从父地点继承定位 |
| `access_point.update` | target | set/clear/append_note；只改 name、location、access_notes、notes，place/kind 不改 |
| `place.hours.update` | target、scope、timezone；weekly/closed_dates 至少一个 | other 还需 label；按星期更新，或新增绝对自然日关闭，保留其他规则 |
| `link.update` | target | set/clear；以既有链接 handle 纠正资料，保留链接身份与兄弟链接 |
| `quote.record` | subject、unit；amount/currency 或 value 二选一 | estimated、eligibility、inclusions、exclusions；当前 subject 仅 Place；参考报价不产生本次费用 |
| `cost.record` | title、targets、price_status；amount/currency 或 value 二选一 | completeness、quantity_basis、quote、breakdown、notes；总额不按人数/目标倍增，confirmed须operation.origin |
| `cost.confirm` | target；amount/currency 或 value 二选一；operation.origin | completeness；保留estimate与身份，只补缺失confirmed，同值no_change |
| `exchange_rate.record` | base_currency、quote_currency、rate、as_of、source | notes；不可变正数直达汇率快照，不猜日期/来源 |
| `budget.configure` | reporting_currency、rates | scope；只采用明确直达汇率，不倒数/串联/自动选最新 |
| `reservation.record` | provider、status、targets；操作 origin 必填 | cancellation_terms、recorded_at；Stay/Unit/Journey/Leg 首次记录，不生成付款 |
| `coverage.record` | benefits；target/scopes 二选一；操作 origin 必填 | reservation、validity、participants、quantity、limits；住宿/交通新权益，多范围不等于多张票 |
| `coverage.replace_confirmation` | target、benefits、scopes；操作 origin 必填 | reservation、limits；完整快照替代，旧确认保留 |
| `coverage.revoke_scopes` | target、scopes；操作 origin 必填 | 仅撤销选中的既有整范围，不生成退款 |
| `stay.plan` | lodging、use_kind | period、units、participants、requests、night_count、notes；不生成订单或办理 Item |
| `stay.change_plan` | target | set/clear/append_note、units add/update；保留身份，不改供应方确认 |
| `recommendation.add` | place、reason | related、interests、duration_advice、notes；不排入日程 |
| `recommendation.update` | target | set/clear/append_note；保留推荐主体，列表整体替换 |
| `plan.add` | kind、title；kind=other 时还需 purpose | place、timing、participants、purpose、day、before；有 day 时省略 before 追加，提供时插到同 Day current Item 前；可省 day 创建已选待排 Item，但不能同时传 before；kind 仅 meal/visit/shopping/rest/errand/other；shopping 可省略 place，visit 仍必填；扩展 timing |
| `plan.update` | target | set、clear、append_note；1.0 current shopping 可 set.place/clear.place，并检查结构化执行事实 blocker；1.0 时间变更检查已确认/完成事实 |
| `plan.move` | target、day | before；可把待排Item原身份归日；显式排序，不平移时间或执行对象 |
| `plan.withdraw` | target、reason | Item及主Journey/Route退役，保留订单、权益、费用、付款、待办与Claim并返回review refs |
| `task.add` | title、action、targets | notes、category、preparation、depends_on、checklist、assignees、beneficiaries；状态 open，1.0个人范围写快照并允许具体 Issue 目标 |
| `task.complete` | target、record_note | completed_at；open 清单阻止完成，open 依赖只提示，不推翻明确完成事实 |
| `task.amend` | target | set/clear/append_note、checklist_edits；支持assignees/beneficiaries，done定义字段须先reopen |
| `task.reopen` | target、reason | reopened_at；只重开 done Task 并追加不可变完成快照 |
| `issue.record` | title、targets、impact | resolution_needed；只接受明确 Place handle，建立 open Issue，不定位 Route/Segment |
| `issue.resolve` | target、resolution_note；operation.origin 必需 | 单调 open→resolved，生成 status Claim；同值 no_change、矛盾拒绝 |
| `service.record` | mode、service_number、service_date、calls | operator、mode_label、notes；Call按key返回稳定handle，operator可未知 |
| `service.update` | target；operator/call_updates至少一项 | 只补缺失/unknown时刻与Place→子AccessPoint，不替换已知事实 |
| `journey.compose` | day、title、legs、connections | participants、timing；可混合independent/scheduled Leg、完整显式Connection，并给independent driving Leg绑定owned vehicle |
| `journey.edit` | target、edits | independent时间、无损bind_service、Connection单调补全、所属Leg的set/clear路径及bind_owned_vehicle |
| `journey.replace_leg` | target、leg、replacement、connections、reason | 新Leg与相邻Connection身份，未改对象逐值保持；旧片段仍有领域/活来源引用或整Journey执行事实时拒绝 |
| `vehicle.record_owned` | 无必填业务字段 | category、actual_vehicle、drivers、requirements、notes；固定source_kind=owned，不生成租赁或费用 |
| `route.compose` | day、title、stops、segments | participants、timing；Segment可拥有唯一Leg，重复地点保持不同 Stop； `source_adoption` 见来源采用指南 |
| `route.edit` | target、edits | Stop/inline Segment既有编辑；leg-backed Segment可设时间或无损bind_service |
| `route.replace_interval` | target、from_stop、to_stop、interior_stops、segments、reason | clear_stale_summary、实验性 source_adoption；保留两端并用 `from`/`to` 局部键完整重建区间；全程摘要须显式且无保护地清理 |
| `path.add_schematic` | coordinate_system、mode、parts | mode_label、notes；仅 WGS84 示意线，不做寻路/插值/距离推算 |
| `path.record` | kind、coordinate_system、mode、parts | source、mode_label、distance_m＋distance_basis、generated_at、notes；WGS84记录几何，observed/provider必须引用Source |
| `source.record` | kind、title | url、published_at、notes；只记不可变来源元数据，不联网、不生成核验标记 |
| `source.register` | document_key、text | title；保存不可变原文快照，连续同内容复用，A→B→A 保留版本顺序 |
| `source.identity.bind` | anchor、semantic_key、expected_type | target、occurrence；以 `(document_key, semantic_key)` 建立或取得稳定对象身份，不按名称猜合并 |
| `source.field.apply` | anchor、identity_key、aspect、value、basis | target、occurrence；每次只采用一个受支持字段，冲突时整批拒绝并返回签名 |
| `source.field.resolve` | conflict、choice、reason | 只裁决当前、未过期的签名冲突；可保留人工值或采用提议，不提供通用同步 |
| `guide.note.add` | title、paragraphs | related；段落可带普通来源或精确原文 citation |
| `guide.note.update` | target | title、paragraphs、related、clear_related；保持说明身份，段落整体替换 |
| `source.duration.adopt` | target、part、key、anchor、minutes、basis | 明确采用单个 Stop/Segment 耗时并建立来源基线 |
| `source.duration.refresh` | binding_id、anchor、minutes、basis | 比较实际基线、当前值及依据；有冲突则整批拒绝 |
| `source.duration.resolve` | conflict、choice、reason | 保留当前或采用已签发提议；同一冲突仅能裁决一次 |

允许编辑的字段：

- Place：name、roles、local_name、aliases、address、location、timezone、content、notes、availability；除 name 外可 clear。
- AccessPoint：name、location、access_notes、notes；除 name 外可 clear。place_ref 与 kind 不可改。
- Item：title、purpose、notes、timing、participants；只有 purpose、notes 可 clear；想把时间改回未知应显式 set timing 为 unknown。
- Task：title、notes、due、window、category、preparation、depends_on、assignees、beneficiaries；这些可编辑字段除 title 外可 clear。清单只接受 add/set_status。done Task 的基础定义字段、清单和人群定义须先 reopen；notes/due/window 仍可改；相同完成说明和时间再次完成返回 no_change，不同完成事实拒绝覆盖。

`timing` 可用封闭的友好输入，1.0 的 exact/estimated/unknown 边界、end-only、相对结束、严格 after、诊断与事实保护见[时间指南](TIME_PLAN_GUIDE.md)。`participants` 的 member/group handle、Task快照和保护见[成员指南](PARTY_GUIDE.md)。复杂价格 value 等其他局部值仍使用规范 Schema 的小结构。常见链接、单值报价、每周营业规则已有较直接的输入；这只覆盖本轮范围，不代表全部领域参数已足够易用。

### 优先使用的简化输入

```python
{"method": "place.update", "args": {"target": shop, "add_links": [
    {"label": "地图", "url": "https://example.com/map", "purposes": ["map"]}
]}}
{"method": "quote.record", "args": {"subject": shop, "amount": "1800", "currency": "JPY", "unit": "person", "estimated": True}}
{"method": "place.update", "args": {"target": shop, "replace_weekly_hours": {
    "scope": "venue", "timezone": "Asia/Tokyo", "rules": [
        {"days": ["mon"], "periods": [{"start": "11:00", "end": "15:00"}]}]
}}}
```

replace_weekly_hours 只替换指定用途的全部每周规则，保留其他用途；other 用 scope+label 识别，自定义 label 必填。同用途未列出的旧星期规则会移除，未说明不等于闭店。显式跨夜、全天、闭店、未知和复杂旧规则保护见[调用指南](CALLER_GUIDE.md)。amount 接受非负整数或十进制字符串；小数用字符串。estimated=True 自动生成关联的估算依据，同时附 origin 时两份依据都保留。省略估算标记不会生成已核实事实。

### 保留的完整输入：第一轮调用兼容

```python
{"method": "place.update", "args": {"target": shop, "links": [
    {"action": "add", "key": "map-main", "value": {
        "label": "地图入口", "purposes": ["map"], "web_url": "https://example.com/map",
        "platform": {"id": "demo-map", "label": "示例地图"}}}
]}}
```

links 目前仅支持 add，结果 `parts.links["map-main"]` 是新 Link 的 handle；key 只用于本动作回执。两个同平台链接不自动去重；修改用 link.update，删除尚未实现。

```python
{"method": "place.update", "args": {"target": shop, "set": {"availability": [
    {"scope": "venue", "timezone": "Asia/Tokyo", "weekly_rules": [
        {"weekdays": [1], "state": "open", "intervals": [
            {"start": "11:00", "end": "15:00", "end_day_offset": 0}]}]}
]}}}
```

完整 set.availability 接收整组每周开放规则，周一为 1，日期例外未支持。这个 set 会替换整个旧 availability，并分配新局部 ID；没有按规则 handle 局部修改。它和按 scope 替换的 replace_weekly_hours 不能混用。营业规则不会自动修改午餐安排。

只改某些星期应使用 place.hours.update 的 weekly，避免重填整组。某日整天临时关闭用 closed_dates，生成绝对 Closure，能截断前晚跨夜；它不是只覆盖营业起始日的 DateOverride。具体调用、保留语义及无法自动拆分的规则见 CALLER_GUIDE。

```python
{"method": "quote.record", "args": {"subject": shop,
    "value": {"kind": "exact", "money": {"amount": "1800", "currency": "JPY"}},
    "unit": "person"},
 "origin": {"basis": "estimate", "statement": "原文：人均参考约1800日元"}}
```

value.kind=exact 仅表示单一金额值；“约”的认识性质保存在 Claim.basis=estimate，报价的 evidence_refs 引用它，消费者不能忽略。金额用十进制字符串；原币保留，不按未知人数乘总价。`quote.record` 本身不执行汇率换算，也不把参考报价记成本次费用；费用和预算应使用上表独立的 cost/exchange_rate/budget 方法。

每个动作可附 `origin: {basis, statement}`，生成针对主对象的 Claim，回执提供 parts.evidence。它保留 Agent 明确给出的依据，不自动标“已核查”；quote 额外绑定 evidence_refs。单个路线耗时另有来源快照、定位与刷新方法，见 SOURCE_GUIDE；尚无通用字段合并或全量覆盖统计。
