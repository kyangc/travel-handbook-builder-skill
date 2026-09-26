# 资料补齐与地点内容覆盖

本指南用于已选目的地的普通攻略内容编制，也用于反馈后的窄补充。Agent 默认先检查已有资料；若只有地点名或内容过薄，适度查询可靠公开资料，让首版尽量可读、可用，而不是等用户逐字段索取。authoring 运行时不会联网、抓取网页、判断事实真伪或替用户选择地点、酒店、航班、路线与每日主题；Agent 先完成研究判断，再把明确采用的事实写入类型化对象。

## 先确定本次覆盖范围

从用户目标、已有偏好和已经选定的行程对象推导最小覆盖范围，不为填满所有可选字段无限采集。默认只处理已选 Place 与本次明确要求评估的候选，以及会影响当前请求的开放预约、建议时长、位置、已选相邻交通和实用提示。先让重点目的地的简介讲清“是什么地方、为何值得来、以什么出名”，再按地点类型补真正有用的条件；`highlights` 只在有不重复的具体看点时补充。对地图，主动核对已安排目的地和关键交通端点是否有可信坐标，候选地点按本次用途取舍；可用且来源清楚的代表图是加分项，不是逐点配图指标。已有内容足以支持首版时可以交付，之后按反馈渐进补充；不因资料尚少阻塞首版，也不把仅录入名字宣称为内容编制完成。未采用方案和与本次旅行无关的百科信息不自动进入范围。

开始查询前，把缺项分为三类：

| 类别 | 处理方式 | 例子 |
|---|---|---|
| 可公开查询的事实 | Agent 先查可靠公开来源；资料不足或冲突时保留缺口 | 官方地点介绍、地址、开放规则、公开时刻表、许可明确的图片来源 |
| 需要用户选择 | 复用上下文已有选择；仅在缺失选择会阻塞当前明确目标时，给出事实与影响并请求最少必要决定，否则保持 unknown/gap 并继续其他工作 | 取舍地点、酒店或航班，游览节奏，最终路线，每日主题 |
| 需要私人凭证或用户确认 | 复用已有授权与确认；仅在缺失凭证会阻塞当前明确目标时索取最少必要信息，否则保持 unknown/gap；公开计划不能冒充私人事实 | 实际出票、预订房型、订单状态、付款、护照或会员信息 |

已有授权、偏好、选择或确认在适用范围内继续使用；在已选范围内查公开事实、补地点内容不逐字段询问。只有缺失选择会实质改变行程时才请用户决定。酒店、机票或门票凭证尚未提供，不会阻塞已选游览地点的公开介绍和实用信息采集。没有网络工具、来源无法访问、地点身份不明确或可靠来源仍不足时，记录原因和下一步，不把问题改写成用户已经确认的事实。公开班次或计划只能按其证据保存为 estimated；只有对应的确认材料才能写成 confirmed。

## 有边界地查询

1. 先读当前对象和已有来源，避免重复查询或覆盖人工修订。
2. 优先使用地点或运营方官方页面、政府或公共机构资料；时间敏感事实应核对适用日期。具体日期的官方日历若直接支持结论，无需再强制查一份节假日表；若是从通用规则推算日期结论，须保留规则和日期前提各自的来源及推理关系，缺少关键前提时保持未知。第三方资料可补充体验信息，但要保留其身份和局限。
3. 确认来源中的地点与当前 Place 是同一现实对象；同名、同区域或相似图片不足以证明身份。
4. 对每项采用内容保留来源标题、URL、可得的发布日期，以及本次检索日期或适用日期。`source.record` 不会自动生成 `checked_at`；需要保留检索日期时写入来源 notes 或调用方覆盖报告，不伪造发布日期。
5. 达到当前用户目标后停止。无需为每个可选空字段逐一找原因，也不要为了“完整”继续采集与本次旅行无关的信息。

研究步骤只产生证据、候选事实和缺项判断。写入前再决定哪些事实已足以采用；authoring 的成功校验不表示网页内容真实、最新或完整。

## 按角色选择有帮助的实用信息

以下是资料菜单，不是必填模板。先读 Place 的 `roles` 和本次用途，只补对当前目标有帮助且已有可靠依据的项目；其余字段可以省略，缺开放时间、建议用时、图片或某类详情都不阻塞生成、`check`、export 或首次交付。多 role 地点组合相关建议即可，不为前端固定详情壳填占位或重复改写同一句介绍。

| role / 用途 | 可优先补充的信息 |
|---|---|
| `attraction` 或作为游览目标的自然地点 / `area` | 看点、进入或开放条件、现场限制、通用体验时长及依据 |
| `dining` | 菜系与特色、适用的营业或餐段规则、预约条件和饮食限制 |
| `lodging` | 入住退房规则、对本次住宿有用的设施和早餐规则；不复制本次 Stay 的日期或状态。首次到店与后续返回按[住宿指南](STAY_GUIDE.md)分别用一个 `check_in` 与 `return`，不因提前到店再拆寄存/登记/拿房卡安排 |
| `retail` | 品类、品牌、楼层和适用营业规则；不把所在商场的时间直接当成店铺时间 |
| `complex` | 对本次用途相关的设施及各自边界；不用一个设施的资料代表整个综合体 |
| `transport_hub` / `service_point` | 按本次用途补入口/换乘、所提供服务、使用条件及适用服务时段 |

上述事实按语义写入角色匹配的 `role_details`、`content` 或带适用 scope / label 的 `availability`，具体字段先核对 live capabilities 与[地点角色合同](CALLER_GUIDE.md#地点类型与资料不足)。公开 `place.update.set.role_details` 会整体替换所有角色资料：先公开读回，保留未修改的兄弟字段及其他角色资料；`clear=["role_details"]` 清除整个对象，单字段撤回须读回后省略该键再整体 set，不用点路径 clear。受管理目录通过 `prepare-request`/`commit` 提交；`prepare-place` 的单字段加法白名单不支持 `role_details`，不代表公开 `place.update` 不支持。未知事实仍省略，不直接修改 canonical。

地图缺点位时，只在已选范围内有边界地查可靠来源，按[地点坐标指南](LOCATION_GUIDE.md)读取公开 `coordinate_inputs` 并用 `place.update.set.location` 补明确的 lat/lon、坐标系和精度；明确属于独立入口/站台的点按[入口指南](ACCESS_POINT_GUIDE.md)处理。Google Maps 搜索链接或可打开的地图 URL 只是链接，不是已核实坐标，也不能证明坐标系或入口精度；地址和城市中心不能冒充店铺或入口的精确位置。缺可靠坐标就省略 `location`，保留已知地址/链接与简短的 Agent 侧缺口说明，不猜点位，不将缺口统计写成旅客可见的大段占位。坐标覆盖是地图可用性的渐进改进，不是首版、`check` 或导出的硬门禁。

已选到访、用餐或购物有明确现实目的地时，用对应 Place 表达“去哪里”，让 Item 引用它；`Item.title` 留作本次安排名称，通用亮点和经确认的本次理由分别留在 Place 与 Item。已有对象先读后改；新增时按公开 `place.add`/`plan.add`、`route.compose`、`journey.compose`、`recommendation.add` 各自的合同选入口，不另造包装方法。无需为了每个动作造 Place：无明确地点的候车、取行李等事项仍可保留为普通 Item。未选关注点只作 Recommendation，不因研究到好资料就自动加入 Day。

地面接驳按已采用的端点和方式建 Journey 连接，不把“搭车去景点”改写成景点名；航班保留两机场端点与航程的 Journey/Leg/Service 事实，不造一个虚构的“航班地点”。

`Place.roles` 回答“这是什么地方”（如 `attraction`、`dining`、`transport_hub`，完整范围见[地点角色合同](CALLER_GUIDE.md#地点类型与资料不足)）；机场、车站用 `transport_hub`，不另造 `airport`、`station` 类别。公开 `route.compose` 生成的 `Route.Stop.role` 使用 `start`、`waypoint`、`end` 表示“这次路线中是起点、途经还是终点”，不是地点类别。同一 Place 可在不同 Stop 承担不同路线位置；不要把路线角色写成 Place 类别，也不要用它替代已知的地点类别。`Stop.encounter_kind` 另按[路线指南](MOVEMENT_GUIDE.md)记录这一次是 `visit` 还是 `pass_through`：有据的去程游览、返程只经过可以不同，不凭 Place 类别或 Stop 位置推断，未知则省略。地点类别没有依据时省略 `roles`，不传空数组 `[]`。

Route 有自己的 Stop 与往返顺序：若它已表达同一次游览，不再为同一发生额外 `plan.add` Visit；已有普通 Visit 后只是细化**这同一次**游览路线时，用[路线输入指南](MOVEMENT_GUIDE.md)的 `route.bind_visit` 保留原 Item，而不是另建 Route Item。若确是同地第二次到访或 Route 外另一次 Visit，则保留各自 Item 与时序。无法判定是不是重复时请调用方复核，不根据相邻、同名或 Place ID 自动删除、合并或重排。


前端可以隐藏无数据的整组内容；Agent 不应写“资料未收录”“暂无建议时长”等旅客占位文案。公开接口表达限制、来源抓取失败和后续建议只进入调用方自己的简短工作记录。旅客可见的 `summary`、`visit_advice`、`cautions`、GuideNote 正文只写现实世界事实、适用条件和旅客需要采取的动作，不写“周规则无法完整表达”“Schema 不支持”等实现说明。

记录营业或开放规则时读取调用指南的 `place.update` / `place.hours.update` 合同。场所整体使用 `scope=venue`；同一 Place 内相关附属服务只有在它没有被单独建模且公开接口适合表达时，才使用带明确 `label` 的 `scope=other`。`availability.timezone` 必须来自材料或可靠来源；未知时省略结构化 availability，不能套用 Trip 时区、UTC 占位或按地点名称推断。不要把“神社内博物馆周四休馆”写成整个神社周四关闭，也不要用商场营业时间证明内部餐厅或展馆开放。含节假日例外的“通常周一休园”不能只在 `weekly` 写无条件 `closed`、再仅在正文补一句例外；若现有接口能忠实表达整套周规则及相关日期/范围例外，可以一并记录，否则省略不成立的无条件周规则，只录已证实的具体日期事实，并在有来源的 `cautions` / GuideNote 保留其余条件，不猜造或穷举未来节假日。其他无法安全表达的复杂预约、季节或入口条件也保留为有来源的条件事实，不压扁成错误的每周时间表。

对未来旅行日期，来源若只公布当前常规规则，就只能采用“当前常规规则 + 未来待复核”的条件事实。尚未公布的展期、季节时刻、临时闭馆和特别日期继续是缺口；星期几相同不等于未来必然开放。

Place 资料只保存地点固有信息。地点安排在哪天、Item 的计划时段和本次计划停留多久，以当前 `Day → active Item → Place` 关系为唯一事实来源；不要手工复制到 `Place.content`、`availability`、Place notes 或 GuideNote。核对某条开放规则是否可能影响行程日期时，可以在调用方的临时评估中记录这一轮结论，但它不是新的地点事实，日程移动或撤下后必须从关系重新派生。`duration_advice` 只描述可复用的通用体验及其估算依据；不能把本次 Item 的起止时刻或计划停留时长倒算后写成通用建议。

## 已选日程的用时与相邻交通

用户需要更可用的日程时，先读已选 Day 的 active Item、已有时间/交通事实及确定的 Stay 地点；只对当前相关的缺口渐进补证。游览目标有可靠的通用时长资料时，可按体验、条件和依据写入 `Place.content.duration_advice`；这是建议，不是本次计划。多个相邻地点被用户合并为一张游览卡时，整段建议可带条件向用户说明；只有成为本次采用的停留计划时才写入该 Item 的 `timing`，不要冒充其中一个 Place 的通用时长。只有用户确需逐点安排时才考虑拆分，不为填字段强制重建 Place 或 Item。没有可靠依据则省略，不填零或从日程反推。

本次实际打算停留多久属于 Item `timing`（路线内某次 Stop 可用 `dwell_minutes`），不是通用 Place 建议。已有起止边界可得出本次时长，不再手写第二份事实；只有时长而无可靠起点时按[时间指南](TIME_PLAN_GUIDE.md)保留未知边界，不编造精确时刻。相邻活动时刻的空档也不能当作交通耗时。

对已定顺序中相邻的地点，以及确已选定住宿时从酒店到首个安排、最后安排回酒店的衔接，先复用已有 Journey/Route、模式和来源；尚缺且公开资料适用时，按[路线指南](MOVEMENT_GUIDE.md)核对交通方式、步行或乘车用时，以及必要换乘/候车范围。只有端点、方式和路线确已采用，才把相应事实写进正式交通安排及其 Leg/Segment/Connection；公开查询出的备选路线不自动变成用户选择。无可靠资料或尚未选方式时，保留重要未知并简短说明，不逐段追问、不为补全可选字段阻塞交付。

## 把资料写回正确对象

- `Place.content.summary`：默认承载地点身份、主要吸引力与有据的成名缘由，让卡片简介独立可读。`highlights` 只补充简介没有说过的具体看点；无需为同一句意思再列一遍，也不要标为“本次重点”。营业时间、建议用时、票券/预约/价格不是“亮点”，按已有适用结构或实用条件记录；无法可靠结构化时保留有来源的条件说明。
- `Place.content.visit_advice/cautions/duration_advice` 与 `availability`：地点通用的参观建议、限制、可复用建议用时及开放规则；不能借这些字段记录这一次的计划停留。
- `Item.purpose`：材料已明确这次选择到访的理由时，创建用 `plan.add.purpose`、修订用 `plan.update.set.purpose` 承接，不只写在 notes；不从通用亮点猜个性化理由。
- `Item.notes` 或对应 `Route.Stop` 的本次说明/停留：这一次如何游览、使用票券或执行安排的已知细节；本次玩多久按 Item/Stop 的计划时间表达，不复制成地点通用介绍。
- `Journey` / `Route` 及其 Leg / Stop / Segment：已选交通端点、方式、时间、路线和沿途顺序；公开搜索结果只是候选事实，未选路线不写成已定。
- `Recommendation.reason`：为什么把某个地点作为建议或候选，不证明已经加入行程。
- 带 citation 的 `GuideNote`：只补确有必要的出处、适用期、例外或尚未在 Place / Item / Stop 表达的具体旅行提醒，不复述整段 Place 内容；已写进 `availability` / `cautions` 的开放条件不再换一种说法复述，Route 的折返顺序也不写成地点亮点或重复说明。例：有来源证实“未来特别展期尚未公布”且会影响已选参观时，在相关 `cautions` 或本次 Item 如实写明条件和出发前复核动作，GuideNote 简述依据与适用期；“材料未给地址、坐标、路线、票价、建议时长”只是 Agent 工作说明中的缺项，不自动写成旅客可见的 GuideNote 清单。`related` 可关联对应 Place。

行前 Task 另按[准备待办指南](TASK_PREPARATION_GUIDE.md)编制：`action` 是可完成的动作，`category` 是主题。已决定购买才写 `purchase`，标题只写购买，期限、票种和渠道等条件放 notes/due；“决定入场时间和购票方式”仍是待选择事项，不能混入一条购买 Task 后伪装为已选。若现有 Task 把已选购票误写为 `verify`，读回后用 `task.amend.set.action` 原位纠错；done 先 `task.reopen`，保留原完成定义与记录。可选的现场分支不冒充必须完成的行前 Task。

不要用 `Item.purpose`、`Recommendation.reason`、原始来源备注或前端自动文案替代缺失的 `Place.content`。同样，不要把通用地点介绍写成用户已经决定的游览理由；当前网页详情已按地点通用资料与本次 Item 安排分区，字段仍须按各自语义编制，不靠展示分区自动纠正内容。

例如，已选神社只有名字时，可从其官方资料补一段“是什么、为何值得看、以什么出名”的简介；具体开放与入内条件另记，有明确偏好才在该次 Item 写“为何这次去”，本次玩法与票券使用注意写 Item/Stop。反例是把“杉林原路折返”当 Place 名、把“9:00 开门／建议 60 分钟／需预约”列成三个亮点、将景点简介复制为本次选择理由，或从两个相邻 Item 的空档编造步行时间。查不到可靠依据时保留未知并交付已有内容，不无限搜索、凑字数或为通过 `check` 加占位。

`place.update(set={"content": ...})` 会整体替换 content。先读取当前 Place，完整保留未获授权修改的子字段，再提交最小补丁。`Place.content` 当前没有字段级 citation；来源可用 `source.record` 保存，并用关联该 Place 的 `guide.note.add` 保留有出处的说明。这个关联提供阅读上下文，不要宣称它是对 content 字段的机器级来源绑定。

```python
operations = [
    {"method": "source.record", "as": "official", "args": {
        "kind": "official",
        "title": "示例地点官方游览说明",
        "url": "https://example.com/visit",
        "published_at": "2026-09-01",
        "notes": "2026-09-22 查询；适用日期见正文",
    }},
    {"method": "place.update", "args": {
        "target": place,
        "set": {"content": {
            "summary": "这是一处以某项有据特色闻名的地点，可了解其历史与建筑。",
            "visit_advice": ["有来源支持的实用提示"],
            "duration_advice": [{
                "experience": "参观主要展区",
                "duration": {"min_minutes": 60, "max_minutes": 90},
                "conditions": "不含特别活动排队时间",
                "notes": "Agent 估算；依据为一个主要展区的一般浏览范围，并非官方建议",
            }],
        }},
    }},
    {"method": "guide.note.add", "args": {
        "title": "示例地点资料来源与时效",
        "related": [place],
        "paragraphs": [{
            "text": "以上介绍依据官方游览说明；开放与票务仍应按出行日复核。",
            "citations": [{"source": {"local": "official"}}],
        }],
    }},
]
```

`place.update.set.content.duration_advice` 直接接收上例的规范对象，不能写成字符串、字符串列表或 `{experience, minutes}`。`recommendation.add` 的公开作者入参使用 `minutes`，运行时再转换成规范 `duration`；两处同名但输入形状不同。未知建议时长时省略该项，不填零或虚构范围。

GuideNote 应按有实质区别的事实簇关联来源，例如分别覆盖“身份与历史”“开放与票务”“交通入口”“现场限制”。它补出处、适用条件与时效，不把 `summary` 和 `highlights` 改写一遍；同一来源支持同一事实簇时无需逐句重复 citation，但不能用只覆盖开放时间的引用，声称同一 Place 的历史、看点、交通和限制也全部有出处。未能找到可靠来源的已采用内容应删去或在覆盖报告中明确标为 `partial` / `gap`。

同一来源要补一个或多个 Place 的多个内容字段时，优先在同一公开 request 中只登记一次 `source.record`，对各 Place 用保留既有子字段的 `place.update`，再按必要事实簇编写少量 `guide.note.add`，经 managed `prepare-request` 审阅提交；不要逐字段反复 `prepare-place` 并把每个字段正文复制成一条 GuideNote。`prepare-place` 仍适合单字段、非覆盖的窄补充，但每次补入新事实都要求一条来源说明，不能靠它自动合并近义 Note。

若来源文字需要逐字保存和精确引用，按 [攻略说明与出处指南](GUIDE_NOTE_GUIDE.md) 使用 `source.register` 与精确 anchor。普通公开网页通常只需记录来源元数据和可靠改写，不复制整页正文。

## 按需保留轻量工作记录

当用户明确要求资料完整性、一次研究涉及多个来源，或重要未知会直接影响当前行程时，可在 canonical package 外保留简短记录：这次采用了哪些事实与来源、哪些重要未知仍需临近复核、下一次从哪里继续。无需为每个 Place 或每类可选信息建立完整矩阵，也不要求用 `covered` / `partial` / `gap` 给所有地点评级。

若确实使用覆盖结论，名称必须与证据相符：字段列表或 `has=true` 只说明数据存在，不证明来源支持；`covered` 不能掩盖已经写入却没有依据的事实。该记录不是 authoring 请求，不应塞进 canonical package；没有这份记录也不阻塞 `check`、export 或交付。

## 导出后的按需抽查与反馈迭代

首次普通创建时，对同一份语义 request 审阅 `preview` 后 `apply`，运行公开 `check`；有效后在首次网页前 `client init`，由 managed 发布 canonical。已进入 managed 的反馈续作则从当前 `client read`/`context` 开始：支持的窄 Place 补充走 `prepare-place`，其他专业编辑按原公开 request 走 `prepare-request`，审阅 preview 后 `commit`；核对 `publish_status` 与当前 revision，`client read` 回本次目标，并保持网页原 canonical 路径。不要回到初始化输入快照普通 `apply`，也不要自行改写或另行 export managed canonical。旧自管完整 state 若尚未接入 managed，仍用公开 `preview`/`apply`、保存完整 state、`check`/export，并保留原请求以便精确重放。详见[默认工作流](DEFAULT_WORKFLOW_GUIDE.md)与[managed 客户端指南](CLIENT_GUIDE.md)。

managed 的 `client read` 与 commit receipt **不提供当前完整 `check` 报告**；receipt warnings 也不是最新 `availability_assessments`。若本次需要判断已选用餐与营业规则的当前影响，用只读 `client check ROOT` 取得当前 state 的完整 `report`，按[营业影响指南](HOURS_IMPACT_GUIDE.md)逐项读取 assessment，并分别核对 `publish_status`；不能读私有 managed state，或把“无 warning”当成 covered。这不新增必填资料或阻塞其他已证实内容的交付。然后只抽查本次新增或修改的字段，以及当前目标中风险较高的事实：

1. 已写入的事实应能对应到相关 GuideNote / Source 或明确的用户材料；没有依据的内容应删除、补证或改成不越界的条件表达。
2. 已写入的开放规则应区分场所整体与附属服务的 scope，不用一个服务的时间替另一对象背书；没有开放规则可以保持未知，不编造 `24/7`。
3. 已写入的 Agent 建议时长应明示为估算，并说明依据、条件和不包含项；没有可靠依据时可以省略，不影响首次交付。
4. Place 资料不得复制 Day / Item 的到访日期、行程时段或计划停留；日程关系由当前 `Day → active Item → Place` 投影派生。
5. 空分区不写占位，模型或接口限制不写进地点正文。旅客内容只保留现实条件和可操作的复核动作。
6. 若抽查发现错误，用新的 request 经当前路径重新预览并提交：managed 用 `prepare-request`/`commit`（支持的窄补充可用 `prepare-place`），旧自管才用普通 `preview`/`apply` 后 `check`/export；不得直接编辑 canonical JSON。

### Place、当前安排与 GuideNote 的写后语义复核

对本次改动的 Place，读 `client context` 中的 Place、关联 GuideNote/Source 和当前 Item；需要日期上下文时再用公开 `client read` 核所属 Day。把正文与当前 Item 的日期、purpose、计划时段逐项对照：来源公布年份、展期及营业适用期属于事实条件，不能见到日期就删；只有来自本次安排的日期或目的不应混入可复用 Place。此项由 Agent 判读，不以 `check.valid` 代替。

再对照 Place 与 GuideNote 的每个重复条件，检查是否另有适用期、例外、限制或独有事实。真正相同的条件只保留在一个正确层级的正文，同时保留 Source/citation 出处链；不要按相似度自动删 Note，也不要为了减少条数合并掉不同条件。例如反例是 Place 写“2026 年通常 09:30—17:00 开放；不保证本次 2027-06-08 开放”，共享 GuideNote 又重复后一分句。可改为 Place 仅保留“2026 年通常 09:30—17:00 开放”及原有关闭例外，共享适用说明保留“该来源不保证本次 2027-06-08 开放，出行前复核”及 citation；另一条“联合讲解是否恢复尚未公布”的独有条件不能删。

修复时先读完整旧 `content`，通过 `place.update` 只移出错槽/重复分句并带回其他子字段；若需更正 Note 则用 `guide.note.update` 保留其身份、仍有效段落和引用。先 `prepare-request` 审阅只涉及目标字段，再 `commit`；随后 `context/read/check` 核来源年份、例外、独有条件、citation 和未修改的当前 Item 均保留。没有独有内容可留也不授权伪造 Note 删除方法或暗改文件。这是有界写后复核，不增加硬 gate、自动去重或新一轮全量研究。

缺少可选字段不是错误，也不应阻塞一份已有明确事实的可用结果。默认先交付，简短说明会影响当前使用的主要未知；不要在最终答复中倾倒完整缺项清单。未来开放时间若被写入或对用户说明，必须保留展期、特别日期、临时关闭和临近复核等来源条件，不能把常规规则改写成确定承诺。

用户在产物中指出某个详情缺失后，做最小增量更新：从 managed `client read`/`context`（旧自管则从完整 state 的公开 `read`）读取当前 Place 和关联资料，只研究或采用这一个反馈点；完整保留未获授权修改的 `content`、`role_details`、`availability` 及其他对象。managed 续作通过 `prepare-place` 或原公开 request 的 `prepare-request`/`commit`，再 read 回目标并确认对象级 diff 只包含请求字段、canonical 仍在原路径；旧自管才用普通 `preview`/`apply` 后 `check`/export。无需重做全部地点或重新生成整份攻略。

## 图片与旅程总领图

用户需要图文攻略或图片能明显改善当前交付时，可为相关 Place 查找身份匹配、来源可靠的图片；不要求每个地点都有图，找不到也不阻塞交付，不用无关图或占位图凑数。采用图片时优先记录图片 URL、来源页面、许可说明和替代文字；许可未知应保持未知，来源可访问不表示可公开发布。不要用生成图冒充地点实景。

读取[图片素材指南](MEDIA_GUIDE.md)，通过 `media.image.add` 记录已取得的素材，用显式用途关联正确 Place 或 Trip。同一素材复用身份，解除一次用途保留其他用途。不要按文件名猜归属，也不要直接修改导出 JSON。

当用户需要旅程总领图时，可使用可用的图像生成工具，围绕已选安排表达主要区域、风格和节奏，再记录 `creation.kind=generated`、generator 和 illustration/schematic 表现形式。明确它是示意图，不能冒充精确地图、实景照片或创造未选行程。缺少生成工具或可用素材时说明具体缺口，不再把已提供的媒体写接口误报为不支持。

本地图片路径只有在 canonical 明确引用且位于允许目录内时才可经预览端点读取；远程 HTTPS 图片由浏览器直接加载。分别报告“素材已找到”“已采用到数据”“页面已展示”，只有实际查看渲染页面后才能声称最后一项；未目视核验仍可交付已验证的记录与可用 URL，并说明显示尚未核验。
