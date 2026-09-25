# Agent 常用输入指南

调用时以 `read.capabilities` 和本指南实际签名为准；未列出的 Schema 字段或方法不构成可调用能力。

重新打开完整 state、从规范 package 建立新工作区、按 Day/类型/handle 分页读取或在提交前预览批次，先读[恢复、局部读取与预览指南](RECOVERY_READ_PREVIEW_GUIDE.md)。package 导入不恢复 request 回执、原文快照/绑定或 Issue resolution_note 元数据，不能称为完整编辑历史恢复。

移动、重排、撤下安排、修改 Day/Trip 日期、改乘一个 Leg 或替换 Route 区间使用[安排编辑指南](ARRANGEMENT_EDIT_GUIDE.md)。这些入口及待排 Item 归日都属于稳定数据契约 1.0。

同一 `source.register` 文档驱动 Route 首稿、明确字段采用及区间替换时，使用 `source.identity.bind`、`source.field.apply/resolve` 与 typed Route 的可选 `source_adoption`；identity key、local key 映射、tombstone 和三方比较见[Route 来源采用协议](SOURCE_ADOPTION_GUIDE.md)。该协议有意保持有界，不提供通用自动同步。

本次费用、明确直达汇率与只读预算投影见[费用指南](MONEY_GUIDE.md)。PriceQuote 仍只是参考报价，不会自动成为 Cost 或 Payment。

坐标输入前先读 `read_workspace(state)["capabilities"]["coordinate_inputs"]`：Place 与 AccessPoint 的 location 必须明确坐标系，示意及记录 Path 均只接受 WGS84，全部无默认值。缺依据时只保存原资料、地址或入口说明，不猜坐标系；错误会给出字段位置和修复指引。记录路径的来源、模式、缺段和绑定见[路线指南](MOVEMENT_GUIDE.md)，地点与入口分别见[地点指南](LOCATION_GUIDE.md)和[入口指南](ACCESS_POINT_GUIDE.md)。

成员、分组、安排参与者、Task负责人和Coverage人群快照使用公开handle，不手找底层ID；见[成员指南](PARTY_GUIDE.md)。省略安排participants仍保存explicit unknown，不默认全体。

已经选定但尚未归入某一天的普通安排，从 可用省略 day 的 `plan.add` 保存；见[待排日期指南](UNASSIGNED_ITEM_GUIDE.md)。它不是候选安排或未知旅行日期。


先理解 Markdown，再提交其明确表达的事实。工具负责对象装配；它不会理解 Markdown、选择餐厅或把待办完成推断为预约成功。以下常用流程不需要阅读领域 Schema。

## 共同调用约定

通过包内 `scripts/python` 运行 Python caller，再从公共模块导入：

```python
from authoring import new_workspace, apply, read_workspace, check, export_package, AuthoringError

state = new_workspace("示例旅行", example=True)
request = {"request_id": "first", "expected_revision": 0, "operations": [
    {"method": "trip.define", "args": {"start_date": "2026-10-05", "end_date": "2026-10-05", "default_timezone": "Asia/Tokyo"}},
    {"method": "day.add", "as": "day", "args": {"date": "2026-10-05", "timezone": "Asia/Tokyo"}},
    {"method": "place.add", "as": "shop", "args": {"name": "示例餐厅", "roles": ["restaurant"]}}
]}
state, receipt = apply(state, request)
shop = receipt["aliases"]["shop"]
day = receipt["aliases"]["day"]
```

同批次可用 `{"local": "shop"}` 引用前面声明的别名。以后使用回执返回的 `{"handle": "..."}`，或从 `read_workspace(state)["objects"]` 的 handle/type/record 找回身份。新请求 expected_revision 取 `read_workspace(state)["revision"]`。

一批全部成功才提交。失败抛 AuthoringError，可读 `error.as_dict()` 的 code、op_index 和 parameter。相同请求重试应原样重发 request_id 和载荷；只返回旧回执，不重复写入，也不恢复旧快照。换 request_id 是新操作，不保证去重。

省略可选参数表示未知或保持原值；不要填 null。方法不会从旅行时区推断跨国地点时区；营业规则的时区必须明确提供。Trip 与 Day 仍须有明确日期；只有 1.0 的普通 `plan.add` 可省略 day，表示已选待排，而不是编造未知日期。

## 地点类型与资料不足

新建攻略默认使用 `1.0`。`place.add` 只要求 name；roles 可以省略，表示分类尚未记录，不猜一个类别。它仍是可被安排、交通和途经点引用的普通地点。如果提供 roles，必须是非空列表，支持以下角色（可组合）：

| roles 值 | 含义 |
|---|---|
| attraction | 景点、游览对象 |
| restaurant 或 dining | 餐饮场所；前者会规范为 dining |
| lodging | 住宿场所 |
| retail | 商店、零售场所 |
| complex | 综合设施，例如商场 |
| transport_hub | 机场、车站、码头、公交站、停车场等交通节点 |
| service_point | 寄存处、游客中心、洗衣、加油/充电等服务点 |
| area | 地理区域 |

这些值描述地点本身的功能，不是一次行程中的起点/终点/停留角色。仅知“集合点”“入口点”时可以省略 roles，不要填 area/service_point 代替未知。也不新增 point/unknown 角色。已知角色应照实录入；分类未知不表示该地点没有任何功能。

```python
{"method": "place.add", "as": "meeting", "args": {"name": "集合点"}}
{"method": "place.update", "args": {"target": meeting, "set": {"roles": ["restaurant"]}}}
{"method": "place.update", "args": {"target": meeting, "clear": ["roles"]}}
```

set.roles 替换完整角色集合，省略 roles 保留旧值；clear.roles 表示撤回已记录分类，地点身份、链接及行程引用保持。restaurant 在创建和更新中都规范为 dining。空列表、null、未知枚举及规范后重复均拒绝。如果已有分类专属资料与新角色不一致，修改会拒绝，不悄悄删资料；当前快捷入口尚不编辑 role_details。

`read_workspace` 返回当前 `schema_version`，尚未定义旅行时为 null。新建 Trip 使用稳定数据契约 1.0；不要手工修改版本字段。

## 收录资料：链接、参考价、营业时间

下面均是放入 operations 的动作。shop/day/task/lunch 是前述返回的引用。

**同一地点可以新增任意多个同平台链接。** `purposes` 是用途列表，可写 map、booking、review 等；platform 是可选的平台名称字符串，不根据 URL 猜平台。未提供 key 时，以本列表从 0 起的下标字符串作回执键。

```python
{"method": "place.update", "args": {"target": shop, "add_links": [
    {"key": "main", "label": "主入口地图", "url": "https://example.com/map", "purposes": ["map"], "platform": "示例地图"},
    {"label": "另一入口地图", "url": "https://example.com/alternate", "purposes": ["map"], "platform": "示例地图"},
    {"label": "点评", "url": "https://example.com/review", "purposes": ["review"]}
]}}
```

回执 `operations[i].parts.links` 返回每个 key 对应的链接引用。同平台、同用途乃至同 URL 都不自动合并。不得把 add_links 和完整 links 参数混在同一动作。纠正已有链接时，使用返回的链接引用（不是地点引用）：

```python
{"method": "link.update", "args": {"target": front_link, "set": {"url": "https://example.com/front-correct"}}}
```

这会原位修改同一个链接，保留其身份及兄弟链接。set 可写 url、label、purposes、platform、notes、language；platform 用名称字符串。clear 可显式删除 platform、notes、language，不能删除 URL/用途/标题。origin 可为本次链接纠错保留针对该链接的依据。尚无删除链接的入口。

**单值参考价直接写金额、币种、单位。** amount 接受非负整数或十进制字符串，小数用字符串，currency 为三个大写字母；unit 可用 person（人均）、room/night（每房每晚）、ticket（每张）等明确单位。不推算人数或本次总费用。

```python
{"method": "quote.record", "as": "price", "args": {
    "subject": shop, "amount": "1800", "currency": "JPY", "unit": "person", "estimated": True
}, "origin": {"basis": "user_statement", "statement": "原文：人均参考约1800日元"}}
```

`estimated=True` 保留“估算”性质，自动建立关联依据；生成的说明会标为输入的规范表达，不冒充原文。origin 可选，用于另存你提供的原话和依据；两份依据都保留。省略 estimated 或用 False **不代表已核实**，工具不根据此字段生成确认、费用或付款。

同一地点的成人、儿童等报价可以分别创建，用可选描述列表表达适用条件和内容：

```python
{"method": "quote.record", "args": {"subject": shop, "amount": "1200", "currency": "JPY", "unit": "person",
    "estimated": True, "eligibility": ["6–11岁"], "inclusions": ["儿童餐", "果汁"], "exclusions": ["成人餐"]}}
```

eligibility/inclusions/exclusions 各自保存到当前这一个报价，可用于展示和区分报价。它们是描述列表，不自动判断年龄是否合格、选择套餐或计算本次费用；未知内容省略，不用原文没有的条件补齐。

区间、起价、未知不强塞进单值金额；需要时使用以下 value 形式，不能再同时传 amount/currency。区间或起价也可附 estimated=True，不制造原文没有的上下限。

```python
# 1500–2000 JPY
{"kind": "range", "min": {"amount": "1500", "currency": "JPY"}, "max": {"amount": "2000", "currency": "JPY"}}
# 1800 JPY 起
{"kind": "from", "min": {"amount": "1800", "currency": "JPY"}}
# 价格未知，不附 estimated=True
{"kind": "unknown", "currency": "JPY"}
```

**按用途替换一整组每周营业规则。** scope 必填，可用 venue（整体营业）、breakfast、lunch、dinner、other。other 必须额外提供 label（例如“泳池开放”），按 scope+label 识别自定义用途，其他 scope 不传 label。只替换这个用途，保留其他用途；但同用途本次未列出的旧星期规则会被删除。因此仅补充某一天时，先读原规则并带上仍应保留的同用途规则。未列出的星期是未说明，不等于闭店。

```python
{"method": "place.update", "args": {"target": shop, "replace_weekly_hours": {
    "scope": "venue", "timezone": "Asia/Tokyo", "rules": [
        {"days": ["mon"], "periods": [{"start": "11:00", "end": "15:00"}]},
        {"days": ["tue"], "closed": True},
        {"days": ["wed"], "unknown": True},
        {"days": ["thu"], "all_day": True},
        {"days": ["fri"], "periods": [{"start": "22:00", "end": "02:00", "next_day": True}]}
    ]
}}}
```

days 使用 mon/tue/wed/thu/fri/sat/sun；同 weekday 在一组规则中只出现一次，午晚分段放到该行 periods 数组。每行只能选择 periods、closed、unknown、all_day 中一种。后三种只能是 True。

时间采用 00:00–23:59 的 HH:MM，正常同日营业无需给日期偏移。结束早于或等于开始必须显式 next_day=True，表示**开始营业的那一天**到次日；10:00 至次日 10:00 是一个明确 24 小时区间，不等同于某个自然日全天开放。自然日全天用 all_day。24:00 请表达为次日 00:00。空 periods 不被当作闭店。timezone 验证为有效 IANA 时区。

如果目标用途存在多份安排、日期例外、季节有效期或带附加说明的规则，快捷替换会拒绝，避免丢失原有资料。它不能与同次 set/clear availability 混用。相同内容再次提交保持身份并返回 no_change；营业规则不自动改变当天午餐时间。

**仅改某个星期时，优先使用增量动作，不重填整组规则：**

```python
{"method": "place.hours.update", "args": {"target": shop, "scope": "venue", "timezone": "Asia/Tokyo",
    "weekly": [{"days": ["tue"], "periods": [{"start": "10:00", "end": "17:00"}]}]}}
```

weekly 使用上面的 days/periods/closed/unknown/all_day 形式，只替换列出的星期，未列出的星期、其他用途、已有日期例外和临时关闭区间保留。单独的 `closed` 不可用来编码带节假日开放等例外的“通常关闭”：文字说明不能抵消无条件周规则。若现有接口能忠实表达整套周规则及相关日期/范围例外，可以一并记录；否则省略不成立的无条件周规则，只把已证实且可表达的具体日期事实写入结构化资料，其余保留为有来源的条件文字，不编造或无限列举节假日。other 用途仍须额外提供 label。时区必须与已有这组规则一致，不能通过局部编辑悄悄更改其时区。相同时间内容返回 no_change。

旧规则若把周一、周二写在同一行，只改周二会拆分：未变周一保留原规则身份，周二生成新规则。若涉及的旧规则带截止时刻、注释、依据或被其他记录引用，则拒绝自动拆分/覆盖；有多份同用途、季节有效期或重复星期规则也须先明确目标。未涉及的复杂旧规则完整保留。不要承诺已改星期的 rule ID 不变。

**某个当地自然日整天临时休业：**

```python
{"method": "place.hours.update", "args": {"target": shop, "scope": "venue", "timezone": "Asia/Tokyo",
    "closed_dates": ["2026-11-03"]}}
```

closed_dates 只新增绝对关闭区间：该当地日期 00:00 至下一日期 00:00，开始含、结束不含。它能截断前一天跨夜延续的营业，不修改以后每周同一天的常规时间，也不修改其他用途。重复添加同一区间不会复制。可与 weekly 放在同一动作；本入口暂不支持删除关闭区间或录入某日特殊开放时段。

若当地时区在某个边界午夜跳时，导致该时刻不存在或有两个可能时刻，工具返回 UNSUPPORTED_VARIANT，不擅自选择或调整关闭边界。检测依赖运行环境的时区数据库，不构成对当地规则的联网核验。

区别：weekly 中周六 closed 表示周六不开始新一轮营业，周五 22:00–次日02:00 仍可能延续；如果周六零点起就必须停业，用周六的 closed_dates。工具不会把这两种意思相互替换。

每周基础时段重复或重叠时，check/export/提交回执会报告 OPENING_INTERVAL_OVERLAP，保留原时段，不自动合并或宣布事实错误。此提示不计算日期例外、绝对关闭区间或真实可执行性。

## 正式安排和待办

`task.add.targets` 接受已建 Trip、Item、Stay 或该 Stay 的 Unit handle，可在同一待办中混合引用。1.0 另接受 `issue.record` 建立的 Issue handle；这用于明确问题对象，不能拿来改挂原本覆盖 whole Item 或具体执行片段的 Task。也支持同批先前别名和 Stay Unit 的局部别名；不直接接受 Place、Recommendation 或其他局部对象。完成待办只记录所做动作，不改变 Issue、住宿计划、房间或供应方确认。

```python
{"method": "plan.add", "as": "lunch", "args": {"day": day, "kind": "meal", "title": "午餐", "place": shop}}
{"method": "task.add", "as": "task", "args": {"title": "核实是否需要预约", "action": "verify", "targets": [lunch], "notes": "核实时同时确认预约渠道。"}}
```

未提供 timing/participants 时，安排的时间和参与者都是 unknown，不猜中午具体时刻或默认全体。普通安排 kind 可用 meal/visit/shopping/rest/errand/other；kind=other 必须同时提供非空 purpose，说明这个未落入既有枚举的安排用途。每次 plan.add 是新安排；修改旧安排须复用其 handle。

1.0 中，若安排已经选定但来源没有日历日期，普通 `plan.add` 可以省略 day，并由 Trip 的待排列表持有。省略 day 时不能传 before；`journey.compose` 和 `route.compose` 仍要求 day。read 会明确返回 Item 的 `ownership.kind` 为 day、unassigned 或 retired。完整调用与诊断边界见[待排日期指南](UNASSIGNED_ITEM_GUIDE.md)。

`plan.add` 默认把新安排追加到该 Day 末尾。若原始顺序明确且新项应位于已有安排之前，传同一 Day 的 current Item handle：

```python
{"method": "plan.add", "as": "shop", "args": {
    "day": day, "kind": "shopping", "title": "购买用品",
    "place": shop_place, "before": existing_later_item
}}
```

`before` 也可引用同批更早创建的 Item alias。工具只把新 Item 插到该锚点前，不按标题或 timing 自动排序；旧 Item 的身份、字段和相对顺序保持。锚点必须是目标 Day 中的 current Item。raw Ref、Place 等错误类型、其他 Day、retired 或不存在的 Item 都会使整批失败。这个参数不移动、撤下或改日期，也不证明相邻安排在时间或交通上可行。

移动已有 Item 使用 `plan.move(target, day, before?)`，撤下使用 `plan.withdraw(target, reason)`；不要以新建副本或手改 Day.item_refs 替代。跨日不会自动改固定时刻、班次、住宿、Task 截止或 Coverage 有效期；warning、执行事实 blocker、review refs 与 Trip 范围复核见[安排编辑指南](ARRANGEMENT_EDIT_GUIDE.md)。

明确改乘现有 Journey 的一个 Leg 使用 `journey.replace_leg`；替换 Route 中两个既有 Stop 之间的区间使用 `route.replace_interval`。两者都创建新的被替换执行身份，要求调用方完整给出相邻 Connection 或区间 Segment，不继承旧班次、路径、耗时或票券事实。旧片段有任何仍须解析的 Task、Claim、Coverage、Cost、GuideNote 或活来源字段 binding 时会原子拒绝；具体输入与 removed/kept/created 回执见[安排编辑指南](ARRANGEMENT_EDIT_GUIDE.md)。

若来源只命名一个具体核实对象而不能定位到 Route Segment，先建 Place，再用 `issue.record` 建立问题、让 Task 指向 Issue；核实完成后分别 `task.complete` 与带 origin 的 `issue.resolve`。不要把 Place 猜成 Route Stop，也不要把已有 whole-Item Task 自动改挂。完整例子、单调解决及诊断见[Issue指南](ISSUE_GUIDE.md)。

当前契约中，visit 与 shopping 条件要求 place；1.0 允许 shopping 暂无 place，visit 仍要求 place。若原文已明确一个真实商圈，可以引用该区域，但不能由工具替作者选择。具体绑定、替换和清除见[未定购物地点指南](SHOPPING_PLACE_GUIDE.md)。

```python
{"method": "task.complete", "args": {"target": task, "record_note": "已核实预约要求", "completed_at": {"local": "2026-10-04T18:00:00", "timezone": "Asia/Tokyo"}}}
{"method": "plan.update", "args": {"target": lunch, "set": {"timing": {"kind": "estimated", "start": {"local": "2026-10-05T12:30:00", "timezone": "Asia/Tokyo"}}}}}
{"method": "task.amend", "args": {"target": task, "append_note": "留意是否有预约截止时间。"}}
{"method": "task.amend", "args": {"target": task, "clear": ["notes"]}}
```

完成说明/时间只取明确输入。修改或清空 notes 不会重开任务或删除完成事实。可以 `place.update(set={"content": {"summary": "原文介绍"}})` 补介绍。set 整体替换对应字段，不做嵌套自动合并；省略其他字段即保留。

护照核验/装包、购买/装包、Wi-Fi 领取/归还等基础准备可显式保存 category、preparation、depends_on 与 checklist。数量单位成组校验、清单工作区 handle、open 清单完成门禁、open 依赖提示和 1.0 完成历史见[基础准备待办指南](TASK_PREPARATION_GUIDE.md)。工具不会从一句“准备物品”自动拆成购买和装包，也不接受用人数冒充负责人。

旅行层的明确简介使用 `trip.update(set={"summary": ...})`，删除使用 `clear=["summary"]`；该入口不改日期、时区或其他 Trip 事实。住宿计划建立后，可用 `stay.action.add` 新建显式办理安排，或用 `stay.action.bind` 把已有普通 Item 原位绑定到 Stay，完整边界见[住宿输入指南](STAY_GUIDE.md)。清单子项标题纠正使用 `task.amend.checklist_edits` 的 rename 操作，保持子项身份和状态；done Task 仍须先重开。

Agent 已取得地点照片或生成旅程总领图后，使用 `media.image.add` 分别记录图片 locator、Source、表现形式和制作方式，再以显式 usages 关联 Place/Trip。同一素材可复用，解除用途不会删除资产；许可未知、本地路径和旧包兼容边界见[图片素材指南](MEDIA_GUIDE.md)。工具不搜索、生成、下载、上传或发布图片。

检查和导出：

```python
report = check(state)
artifact = export_package(state, revision=read_workspace(state)["revision"])
package = artifact["package"]
```

导出是私有领域包，校验限结构和有限语义，不证明来源齐全、旅行可行或网页已经可用。遇到本指南不能表达的内容先记录能力缺口，不自行拼装私有 state，也不让工具猜事实。

多段交通、折返徒步、局部路线编辑、地图示意线、明确来源的记录路径及同一自有车在驾驶段间复用见 [路线输入指南](MOVEMENT_GUIDE.md)。

原文后续更新时，路线停留与耗时可使用[来源刷新指南](SOURCE_GUIDE.md)中的四个动作，保留精确原文位置，并保护手工修改。其范围仅限这两类字段，不代表本指南所有方法均已支持来源刷新。

更新营业资料后，check还会报告与既定用餐安排的覆盖关系；完整起止输入、covered/conflict/unknown语义及跨夜反例见[营业影响检查指南](HOURS_IMPACT_GUIDE.md)。这不会自动调整行程，也不触发source.duration的原文刷新。

常用时间输入、end-only、不同确定性的边界、相对结束、严格 after、夏令时诊断和已确认事实保护见[时间指南](TIME_PLAN_GUIDE.md)。`plan.update.set.timing` 替换整个 TimePlan，要保留的边界、说明和约束须一并提供。check/export/成功回执的 `time_assessments` 显式列出 satisfied、violated 或 unknown；不能只凭没有 warning 推断约束满足。

## 有界字段更新

`plan.update` 是字段补丁：只有 `set`、`clear` 或 `append_note` 明确提交的字段会进入写集合，其他字段由方法保留。来源若明确限制本次修订范围，被点名的领域字段就是完整写集合；描述现状、重申未知值或要求其余内容保持原样，均属于保留条件，不构成额外赋值。调用方应读取当前对象、构造最小补丁、先 preview，再 apply 同一个请求，随后重新读取目标并确认对象级差异没有超出该集合。若接口要求完整替换复合值，则携带未获授权子字段的原值，只改变来源明确修订的部分。

交通与徒步的整体时段可在 compose 中提供 timing，或用 plan.update 更新原主安排；整体安排结构另见[路线输入指南](MOVEMENT_GUIDE.md)。明确班次、逐段时间、Connection、单调补全与交通诊断见[班次与接续指南](TRANSPORT_SERVICE_GUIDE.md)；内部事实只从明确输入保存，不会由整体 Item 时间自动填入。

地点地址、坐标顺序、定位精度及未知坐标系的完整输入见[地址与坐标指南](LOCATION_GUIDE.md)。只补公开用法，不自动地理编码或核验来源。

同一地点内来源明确的入口、站台或航站楼使用 `access_point.add/update`；无坐标也可创建，具体身份、定位后补和不可变 parent/kind 见[入口指南](ACCESS_POINT_GUIDE.md)。创建入口不会改已有 Place、安排或交通端点。

住宿与房间计划见 [住宿输入指南](STAY_GUIDE.md)，地点推荐及理由见 [推荐输入指南](RECOMMENDATION_GUIDE.md)。两者都不会自动新增正式日程或供应方确认。

来源明确已有住宿订单或已取得权益时，见[订单与权益指南](RESERVATION_GUIDE.md)。reservation.record/coverage.record 必须提供操作级 origin；订单确认、含早餐和待扣款分别处理，不把缺失信息补成确认或付款。

交通订单与多范围权益见 [交通权益指南](TRANSPORT_COVERAGE_GUIDE.md)；确认更新和整范围部分撤销见 [确认修订指南](COVERAGE_REVISION_GUIDE.md)。新建包仍默认 1.0，修订方法可直接调用。

跨日程的入境、通信或购物提醒等文字及其来源见 [攻略说明与出处指南](GUIDE_NOTE_GUIDE.md)。GuideNote 可直接调用；普通来源元数据 `source.record` 可在既有版本使用。说明不会自动成为 Item、Task、Claim 或已核验事实。

已经决定购物但尚未选店时，使用 1.0 的无地点 shopping；后续绑定、替换和清除地点及结构化事实保护见[未定购物地点指南](SHOPPING_PLACE_GUIDE.md)。visit 仍必须有地点，说明文字也不会自动变成正式购物安排。
