# 资料补齐与地点内容覆盖

本指南用于用户要求一份可阅读、可使用的攻略，而现有材料不足以支撑该目标时。Agent 可以有边界地查询公开资料；authoring 运行时不会联网、抓取网页、判断事实真伪或替用户选择地点、酒店、航班、路线与每日主题。先完成研究判断，再把明确采用的事实写入类型化对象。

## 先确定本次覆盖范围

从用户目标和已经选定的行程对象推导最小覆盖范围，不为填满所有可选字段无限采集。默认只处理本次攻略已经选择或明确要求评估的 Place，以及会影响当前请求的日期、开放情况、位置、交通计划和实用提示。候选地点、未采用方案和与本次旅行无关的百科信息不自动进入范围。已有简介可以先形成可用交付；只有当前目标或用户反馈需要更多实用信息时，才继续补对应项目。

开始查询前，把缺项分为三类：

| 类别 | 处理方式 | 例子 |
|---|---|---|
| 可公开查询的事实 | Agent 先查可靠公开来源；资料不足或冲突时保留缺口 | 官方地点介绍、地址、开放规则、公开时刻表、许可明确的图片来源 |
| 需要用户选择 | 复用上下文已有选择；仅在缺失选择会阻塞当前明确目标时，给出事实与影响并请求最少必要决定，否则保持 unknown/gap 并继续其他工作 | 取舍地点、酒店或航班，游览节奏，最终路线，每日主题 |
| 需要私人凭证或用户确认 | 复用已有授权与确认；仅在缺失凭证会阻塞当前明确目标时索取最少必要信息，否则保持 unknown/gap；公开计划不能冒充私人事实 | 实际出票、预订房型、订单状态、付款、护照或会员信息 |

已有授权、偏好、选择或确认在适用范围内继续使用，不重复询问。酒店、机票或门票凭证尚未提供，不会阻塞已选游览地点的公开介绍和实用信息采集。没有网络工具、来源无法访问、地点身份不明确或可靠来源仍不足时，记录原因和下一步，不把问题改写成用户已经确认的事实。公开班次或计划只能按其证据保存为 estimated；只有对应的确认材料才能写成 confirmed。

## 有边界地查询

1. 先读当前对象和已有来源，避免重复查询或覆盖人工修订。
2. 优先使用地点或运营方官方页面、政府或公共机构资料；时间敏感事实应核对适用日期。具体日期的官方日历若直接支持结论，无需再强制查一份节假日表；若是从通用规则推算日期结论，须保留规则和日期前提各自的来源及推理关系，缺少关键前提时保持未知。第三方资料可补充体验信息，但要保留其身份和局限。
3. 确认来源中的地点与当前 Place 是同一现实对象；同名、同区域或相似图片不足以证明身份。
4. 对每项采用内容保留来源标题、URL、可得的发布日期，以及本次检索日期或适用日期。`source.record` 不会自动生成 `checked_at`；需要保留检索日期时写入来源 notes 或调用方覆盖报告，不伪造发布日期。
5. 达到当前用户目标后停止。无需为每个可选空字段逐一找原因，也不要为了“完整”继续采集与本次旅行无关的信息。

研究步骤只产生证据、候选事实和缺项判断。写入前再决定哪些事实已足以采用；authoring 的成功校验不表示网页内容真实、最新或完整。

## 按角色选择有帮助的实用信息

以下是资料菜单，不是必填模板。先读 Place 的 `roles` 和本次用途，只补对当前目标有帮助且已有可靠依据的项目；其余字段可以省略，缺开放时间、建议用时、图片或某类详情都不阻塞生成、`check`、export 或首次交付。多 role 地点组合相关建议即可，不为前端固定详情壳填占位。

| role / 用途 | 可优先补充的信息 |
|---|---|
| `attraction` 或作为游览目标的自然地点 / `area` | 看点、进入或开放条件、现场限制、通用体验时长及依据；读取已有 `role_details`，新增事实优先使用公开能力支持的 `content` 与 `availability` |
| `dining` | 菜系与特色、适用的营业或餐段规则、预约条件和饮食限制；读取已有 dining `role_details`，新增事实使用有来源的 `content` 与对应 availability scope |
| `lodging` | 入住退房规则、对本次住宿有用的设施和早餐规则；读取已有 lodging `role_details`，新增适用的 content / breakfast / subordinate-service availability，不复制本次 Stay 的日期或状态 |
| `retail` | 品类、品牌、楼层和适用营业规则；读取已有 retail `role_details`，新增事实使用 `content` / `availability`，不把所在商场的时间直接当成店铺时间 |
| `complex` | 对本次用途相关的设施及各自边界；读取已有 complex `role_details`，新增事实使用有明确 scope / label 的规则或 content，不用一个设施的资料代表整个综合体 |
| `transport_hub` / `service_point` | 按本次用途补入口/换乘、所提供服务、使用条件及适用服务时段；读取已有对应 `role_details`，新增事实只用公开能力实际支持的字段 |

`role_details` 目前可读、可导出，但公开 `place.update` 不提供编辑入口。不要为补类型化详情盲试该字段或修改 canonical；先读 live capabilities，用现有 `content` / `availability` 等受支持入口表达可表达的事实，其余保持未知，等待后续能力或用户反馈。

前端可以隐藏无数据的整组内容；Agent 不应写“资料未收录”“暂无建议时长”等旅客占位文案。公开接口表达限制、来源抓取失败和后续建议只进入调用方自己的简短工作记录。旅客可见的 `summary`、`visit_advice`、`cautions`、GuideNote 正文只写现实世界事实、适用条件和旅客需要采取的动作，不写“周规则无法完整表达”“Schema 不支持”等实现说明。

记录营业或开放规则时读取调用指南的 `place.update` / `place.hours.update` 合同。场所整体使用 `scope=venue`；同一 Place 内相关附属服务只有在它没有被单独建模且公开接口适合表达时，才使用带明确 `label` 的 `scope=other`。`availability.timezone` 必须来自材料或可靠来源；未知时省略结构化 availability，不能套用 Trip 时区、UTC 占位或按地点名称推断。不要把“神社内博物馆周四休馆”写成整个神社周四关闭，也不要用商场营业时间证明内部餐厅或展馆开放。含节假日例外的“通常周一休园”不能只在 `weekly` 写无条件 `closed`、再仅在正文补一句例外；若现有接口能忠实表达整套周规则及相关日期/范围例外，可以一并记录，否则省略不成立的无条件周规则，只录已证实的具体日期事实，并在有来源的 `cautions` / GuideNote 保留其余条件，不猜造或穷举未来节假日。其他无法安全表达的复杂预约、季节或入口条件也保留为有来源的条件事实，不压扁成错误的每周时间表。

对未来旅行日期，来源若只公布当前常规规则，就只能采用“当前常规规则 + 未来待复核”的条件事实。尚未公布的展期、季节时刻、临时闭馆和特别日期继续是缺口；星期几相同不等于未来必然开放。

Place 资料只保存地点固有信息。地点安排在哪天、Item 的计划时段和本次计划停留多久，以当前 `Day → active Item → Place` 关系为唯一事实来源；不要手工复制到 `Place.content`、`availability`、Place notes 或 GuideNote。核对某条开放规则是否可能影响行程日期时，可以在调用方的临时评估中记录这一轮结论，但它不是新的地点事实，日程移动或撤下后必须从关系重新派生。`duration_advice` 只描述可复用的通用体验及其估算依据；不能把本次 Item 的起止时刻或计划停留时长倒算后写成通用建议。

## 正确区分四类文字

- `Place.content.summary/highlights/visit_advice/cautions/duration_advice`：地点本身的通用介绍和实用信息。
- `Item.purpose`：为什么本次行程在这里安排这次到访，不是地点百科介绍。
- `Recommendation.reason`：为什么把某个地点作为建议或候选，不证明已经加入行程。
- 带 citation 的 `GuideNote`：来源说明、时效、限制和仍需核验的事实；`related` 可关联对应 Place。

不要用 `Item.purpose`、`Recommendation.reason`、原始来源备注或前端自动文案替代缺失的 `Place.content`。同样，不要把通用地点介绍写成用户已经决定的游览理由。

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
            "summary": "地点通用介绍的可靠改写。",
            "highlights": ["对本次游览有用的看点"],
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

GuideNote 应按有实质区别的事实簇关联来源，例如分别覆盖“身份与历史”“开放与票务”“交通入口”“现场限制”。同一来源支持同一事实簇时无需逐句重复 citation；但不能用只覆盖开放时间的引用，声称同一 Place 的历史、看点、交通和限制也全部有出处。未能找到可靠来源的已采用内容应删去或在覆盖报告中明确标为 `partial` / `gap`。

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

缺少可选字段不是错误，也不应阻塞一份已有明确事实的可用结果。默认先交付，简短说明会影响当前使用的主要未知；不要在最终答复中倾倒完整缺项清单。未来开放时间若被写入或对用户说明，必须保留展期、特别日期、临时关闭和临近复核等来源条件，不能把常规规则改写成确定承诺。

用户在产物中指出某个详情缺失后，做最小增量更新：从 managed `client read`/`context`（旧自管则从完整 state 的公开 `read`）读取当前 Place 和关联资料，只研究或采用这一个反馈点；完整保留未获授权修改的 `content`、`role_details`、`availability` 及其他对象。managed 续作通过 `prepare-place` 或原公开 request 的 `prepare-request`/`commit`，再 read 回目标并确认对象级 diff 只包含请求字段、canonical 仍在原路径；旧自管才用普通 `preview`/`apply` 后 `check`/export。无需重做全部地点或重新生成整份攻略。

## 图片与旅程总领图

用户需要图文攻略或图片能明显改善当前交付时，可为相关 Place 查找身份匹配、来源可靠的图片；不要求每个地点都有图，找不到也不阻塞交付，不用无关图或占位图凑数。采用图片时优先记录图片 URL、来源页面、许可说明和替代文字；许可未知应保持未知，来源可访问不表示可公开发布。不要用生成图冒充地点实景。

读取[图片素材指南](MEDIA_GUIDE.md)，通过 `media.image.add` 记录已取得的素材，用显式用途关联正确 Place 或 Trip。同一素材复用身份，解除一次用途保留其他用途。不要按文件名猜归属，也不要直接修改导出 JSON。

当用户需要旅程总领图时，可使用可用的图像生成工具，围绕已选安排表达主要区域、风格和节奏，再记录 `creation.kind=generated`、generator 和 illustration/schematic 表现形式。明确它是示意图，不能冒充精确地图、实景照片或创造未选行程。缺少生成工具或可用素材时说明具体缺口，不再把已提供的媒体写接口误报为不支持。

本地图片路径只是元信息记录，不自动提供浏览器文件访问；现有页面尚不显示新增媒体。分别报告“素材已找到”“已采用到数据”“页面已展示”，不能把前两者当成最后一项。
