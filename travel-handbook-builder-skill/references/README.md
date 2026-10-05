# Travel Handbook Authoring public API

This is the callable protocol and method inventory, not a second setup path. Start with [the short default CLI workflow](DEFAULT_WORKFLOW_GUIDE.md). Read the [managed continuation guide](CLIENT_GUIDE.md) for a relevant edit, [arrangement edits](ARRANGEMENT_EDIT_GUIDE.md) when changing days or items, or [the optional Python examples](PYTHON_OPTIONAL_GUIDE.md) only when programmatic state handling is needed; use `CALLER_GUIDE.md` and other topic guides only for the methods the material calls for. Live `read.capabilities` remains authoritative.

首次创建与预览见[默认工作流](DEFAULT_WORKFLOW_GUIDE.md)，在同一 ROOT 续改见[受管理客户端](CLIENT_GUIDE.md)，旧自管文件的恢复见[恢复指南](RECOVERY_READ_PREVIEW_GUIDE.md)。本页列出公开方法合同；managed 续作仍按这些合同构造请求，再由客户端提交。

安装与解释器选择见[运行环境指南](RUNTIME_SETUP_GUIDE.md)；网页服务、Google 配置与图片目录见[浏览器预览指南](BROWSER_PREVIEW_GUIDE.md)。这两页是操作说明，不替代方法合同。

## Python 与公共协议

程序内创建和从任意已有 managed ROOT 做专业补充的可独立示例在[Python 备选指南](PYTHON_OPTIONAL_GUIDE.md)。下面是各公开方法的合同，不是另一条默认持久化流程。

安装后的 CLI 使用 `scripts/travel-handbook`，开发仓库可用 `python3 -m authoring`；`--example` 仅用于合成演示。CLI 失败时非零退出并输出结构化 JSON，输入严格拒绝重复键与非有限数字。`as` 是批内别名，后续请求使用回执或 read 返回的 `{"handle": "..."}`；底层对象 ID 与 Link、开放规则的局部 ID 均由实现分配。省略时间或参与者时，安排对应字段为 `unknown`。撤下或解绑不等于删除，未公开的方法不可调用。

Python API 返回新状态，不改传入状态；异常为 `AuthoringError`，`as_dict()` 给出未提交诊断。不能直接写 state 或 package 修补结果后宣称方法成功。read 的记录是副本，公开 schema_version、capabilities.coordinate_inputs 坐标输入要求及独立 budget_projection，可查当前对象和链接的 owner；无参数保持完整读取，selection/limit/cursor 提供有界局部读取，准确恢复与分页契约见[专门指南](RECOVERY_READ_PREVIEW_GUIDE.md)。

- 一批全部成功才提交；任一步或最终规范校验失败，数据、revision 和成功回执都不改变。不存在跳过错误后部分成功。
- 相同成功 `request_id` 必须携带完全相同载荷（包括原 expected_revision）。重试先查回执，返回原结果及当前 revision，不重复执行，也不把旧快照写回；当前 revision 已超过原提交时另返回 `historical_receipt=true`，旧回执中的失效 handle 仍只是历史。失败请求不记成功回执，可修正后再提交。
- 新请求的 expected_revision 必须匹配当前值；同一成功 ID 换内容报 `REQUEST_ID_REUSED`。不同 ID 不意味着相同业务：重复 `place.add` 会新建地点，重复 append 会再次追加，调用方应复用原请求 ID 重试。
- 更新省略字段保留；`set` 替换指定字段的整体值，嵌套对象不隐式深合并；`clear` 显式删除允许删除的字段；`append_note` 追加文字。同字段不能同时 set/clear/append。直接参数 null 被拒绝，不能把 null 当未知或清空。
- 每次新成功批次 revision 加一，即使某动作回报 `no_change`，以保存新请求回执；成功请求重放不增加 revision。`structured` 表示发生领域写入，不代表来源内容已全部转换、事实已核验或安排可执行。
- 直接动作错误带从 0 起的 `op_index`；基本输入错误尽量带 parameter。最终校验错误保留规范 JSON path，并给 `related_op_indices` 指向相关写操作；跨对象错误可能关联多项，不能将其当精确的唯一根因。

已有住宿订单与确认权益见[订单指南](RESERVATION_GUIDE.md)，住宿和房间计划见 [住宿指南](STAY_GUIDE.md)，独立于日程的地点推荐见 [推荐指南](RECOMMENDATION_GUIDE.md)，可完成的行前动作见 [Task 准备指南](TASK_PREPARATION_GUIDE.md)。

## 当前可调用的写动作

| 方法 | 必须参数 | 可选参数及边界 |
|---|---|---|
| `trip.define` | start_date、end_date、default_timezone | 只能定义一次；标题来自 new_workspace；新包 1.0 |
| `trip.change_dates` | start_date/end_date 至少一项 | 不批量移动 Day；范围外 Day 返回具体 warning 并保留 |
| `trip.update` | set.title/set.summary 或 clear.summary | 原位改旅行标题/摘要；标题须非空，保留 Trip 身份、日期、时区和其他事实 |
| `party.describe` | count、members_status、clear 至少一项 | 人数和名单完整性独立，不生成匿名成员 |
| `party.member.add` | label | age、declared_category；返回稳定 member handle |
| `party.member.update` | target、set | label可改，年龄/原词类别只补缺失或同值 |
| `party.group.add` | members | label；成员handle去重后建立不可变组 |
| `day.add` | date、timezone | 非空 title/summary、可选 weather_location handle；顺序按添加顺序，不按日期自动重排 |
| `day.update` | target；date/timezone/set/clear 至少一项 | set/clear 支持 title/summary/weather_location；日期/时区沿用执行事实日历保护，不改 Item/Service/Stay |
| `place.add` | name | roles 可省略为分类未知；restaurant 映射为 dining；可选 role_details 须与 roles 一致 |
| `place.update` | target | set、clear、append_note、add_links、replace_weekly_hours；role_details 整体替换/清除；也保留完整 links，至少一个有效修改 |
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
| `stay.action.add` | stay、action、title | day、timing、participants、purpose、notes、before；显式建立办理 Item，不猜 action，不生成订单/费用/待办 |
| `stay.action.bind` | target、stay、action | 把 current 普通 Item 原位细化为住宿办理，保留 Item 身份、内容、出处及外部引用；冲突原子拒绝 |
| `recommendation.add` | place、reason | related、interests、duration_advice、notes；不排入日程 |
| `recommendation.update` | target | set/clear/append_note；保留推荐主体，列表整体替换 |
| `plan.add` | kind、title；kind=other 时还需 purpose | place、timing、participants、purpose、day、before；有 day 时省略 before 追加，提供时插到同 Day current Item 前；可省 day 创建已选待排 Item，但不能同时传 before；kind 仅 meal/visit/shopping/rest/errand/other；shopping 可省略 place，visit 仍必填；扩展 timing |
| `plan.update` | target | set、clear、append_note；current stay_action 可改 title/purpose/notes/timing/participants，不可换 Stay/action/place；1.0 current shopping 可 set.place/clear.place，并检查结构化执行事实 blocker；1.0 时间变更检查已确认/完成事实 |
| `plan.move` | target、day | before；可把待排Item原身份归日；显式排序，不平移时间或执行对象 |
| `plan.withdraw` | target、reason | Item及主Journey/Route退役，保留订单、权益、费用、付款、待办与Claim并返回review refs |
| `task.add` | title、action、targets | notes、category、preparation、depends_on、checklist、assignees、beneficiaries；状态 open，1.0个人范围写快照并允许具体 Issue 目标 |
| `task.complete` | target、record_note | completed_at；open 清单阻止完成，open 依赖只提示，不推翻明确完成事实 |
| `task.amend` | target | set.action 可在模型枚举内原位纠错；set.targets 整体改挂至显式当前 Item 等受支持目标，不接受原始 target_refs；其他 set/clear/append_note、checklist_edits 及 assignees/beneficiaries 仍受原保护，done 定义字段须先 reopen |
| `task.reopen` | target、reason | reopened_at；只重开 done Task 并追加不可变完成快照 |
| `task.retire` | target、reason | 1.0 仅将 open Task 原位标为 not_needed，保留身份与历史并记录原因；done 须先显式 reopen，不自动改动引用方 |
| `issue.record` | title、targets、impact | resolution_needed；只接受明确 Place handle，建立 open Issue，不定位 Route/Segment |
| `issue.resolve` | target、resolution_note；operation.origin 必需 | 单调 open→resolved，生成 status Claim；同值 no_change、矛盾拒绝 |
| `service.record` | mode、service_number、service_date、calls | operator、mode_label、notes；Call按key返回稳定handle，operator可未知 |
| `service.update` | target；operator/call_updates至少一项 | 只补缺失/unknown时刻与Place→子AccessPoint，不替换已知事实 |
| `journey.compose` | day、title、legs、connections | participants、timing；可混合independent/scheduled Leg、完整显式Connection，并给independent driving Leg绑定owned vehicle |
| `journey.edit` | target、edits | independent时间、无损bind_service、Connection单调补全、所属Leg的set/clear路径及bind_owned_vehicle |
| `journey.replace_leg` | target、leg、replacement、connections、reason | 新Leg与相邻Connection身份，未改对象逐值保持；旧片段仍有领域/活来源引用或整Journey执行事实时拒绝 |
| `vehicle.record_owned` | 无必填业务字段 | category、actual_vehicle、drivers、requirements、notes；固定source_kind=owned，不生成租赁或费用 |
| `route.compose` | day、title、stops、segments | participants、timing；Segment可拥有唯一Leg，重复地点保持不同 Stop； `source_adoption` 见来源采用指南 |
| `route.bind_visit` | target、stops、segments、source_stop_key、reason | route_title 可选且默认原 Item.title；旧 Place 须与指定 Stop 的 Place ref 精确对应；把显式 current 普通 Visit 原位细化为 Route，保留 Item 身份、Day 序位及整体内容；不合并既有两安排，冲突字段受保护；详见[路线指南](MOVEMENT_GUIDE.md#已有-visit-原位细化为-route) |
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
| `media.image.add` | locator、alt、representation | creation、source、usage_rights、captured_at、caption、usages；只记录图片，不下载/生成/发布 |
| `media.update` | target | set/clear 仅限 alt、caption、usage_rights；保留素材身份、位置、来源和用途 |
| `media.usage.add` | target、subject、purpose | place_intro→Place，trip_overview→Trip；同一关系重复为 no_change |
| `media.usage.remove` | target、subject、purpose | 只解除精确用途；最后一个用途移除后仍保留 Media |
| `source.duration.adopt` | target、part、key、anchor、minutes、basis | 明确采用单个 Stop/Segment 耗时并建立来源基线 |
| `source.duration.refresh` | binding_id、anchor、minutes、basis | 比较实际基线、当前值及依据；有冲突则整批拒绝 |
| `source.duration.resolve` | conflict、choice、reason | 保留当前或采用已签发提议；同一冲突仅能裁决一次 |

允许编辑的字段：

- Place：name、roles、local_name、aliases、address、location、timezone、content、notes、availability；除 name 外可 clear。
- AccessPoint：name、location、access_notes、notes；除 name 外可 clear。place_ref 与 kind 不可改。
- Item：title、purpose、notes、timing、participants；只有 purpose、notes 可 clear；想把时间改回未知应显式 set timing 为 unknown。
- Task：title、notes、due、window、category、preparation、depends_on、assignees、beneficiaries；这些可编辑字段除 title 外可 clear。清单只接受 add/set_status/rename，其中 rename 保留子项身份、状态和顺序。done Task 的基础定义字段、清单和人群定义须先 reopen；notes/due/window 仍可改；相同完成说明和时间再次完成返回 no_change，不同完成事实拒绝覆盖。
- Media：alt、caption、usage_rights；caption、usage_rights 可 clear。locator、kind、representation、creation、source_ref、id 不可改，用途通过 media.usage.add/remove 单独维护。

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

### Place lodging 入住起始时间

`role_details.lodging.check_in_time` 是可选酒店当地 `HH:mm`（`00:00`–`23:59`），不含日期或时区。省略表示未知；不从 `check_in_rule` 自由文本或 Trip 默认时区解析/推断，不要求同时补 Place.timezone。旧 `check_in_rule` 和其他角色资料继续保留。

```json
{"method":"place.add","args":{"name":"示例酒店","roles":["lodging"],"role_details":{"lodging":{"check_in_time":"15:00","check_in_rule":"酒店明确的办理条件"}}}}
{"method":"place.update","args":{"target":{"handle":"<hotel-handle>"},"set":{"role_details":{"lodging":{"check_in_time":"15:00","check_in_rule":"酒店明确的办理条件"},"dining":{"cuisines":["地方菜"]}}}}}
```

第二例须已有或同批明确设置 `roles:["lodging","dining"]`；现有模型逐个检查角色一致性，不自动补角色。`set.role_details` 是整个对象替换，不嵌套合并：先公开读取，完整带回仍有效的兄弟字段及其他角色资料。只移除入住时间时，从读取的完整对象删除 `lodging.check_in_time` 后 `set.role_details`；`clear:["role_details"]` 清全部角色详情，保留roles。省略顶层role_details参数保留原对象；整体替换时未带回的嵌套键会移除。`check_in_time`及`update.set.role_details`不接受null，非法时间、未建模状态、点路径clear均拒绝。Python可选参数`Editor.place_add(role_details=None)`沿既有语义视为未提供；公开JSON请求仍按通用参数规则拒绝显式null。不新增寄存/登记/进房状态或动作，也不自动排序。

已有adopted Claim若指向实际变化的 `role_details`、其角色子树或具体点分隔字段，修改/移除会以 `PLACE_ROLE_DETAILS_CHANGE_BLOCKED` 返回Claim引用；同值及未改变的兄弟字段不误阻，来源/Claim不会自动删掉或改写。本批不新增source field binding aspect，现有来源采用/冲突流程不被替代。受管理ROOT用现有 `client prepare-request` → `commit` 提交同一公开请求；`prepare-place` 加法白名单不扩，返回unsupported并指向 `place.update` 和此公开请求路径，canonical保持不变。

- [本日主要天气地点](WEATHER_GUIDE.md)：Day 明确选择、改选或清除；天气数值不入 canonical。
