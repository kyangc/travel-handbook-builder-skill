# Changelog

本文件记录 `travel-handbook-builder-skill` 的所有对外发布变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

## [0.3.11] - 2026-10-08

### Changed

- Skill 续改首次读取可直接按本次目标类型或 handle 获取对象、revision 与完整 capabilities；后续仍可省略重复能力说明并追完分页。
- 受管理预览启动合并同阶段重复的数据校验，启动完成后仍重新核验当前 canonical；`status` 新增 `canonical_revision`。
- 预览启动超时报告最后就绪阶段、HTTP 探测结果和私有日志位置，便于排查；既有偶发超时的根因尚未确定。

### Fixed

- `preview-service stop` 不再依赖历史操作状态或当前攻略数据有效性，仍须核对进程 birth 与 HTTP instance，并在发信号前复核 birth。停服结果用 `publish_status: null`、`data_error: "not_checked"` 明确表示未检查数据；`client status` 的历史完整性错误保持原样。

### Compatibility and validation

- Schema 1.0、公开业务方法和运行依赖保持不变。受影响的本地回归和合成包已验证；正式发行 ZIP 仍需独立验收。

## [0.3.10] - 2026-10-05

### Changed

- 首次有界读取保留完整能力说明；续改、分页及日期错误恢复使用已有选项省略重复能力说明，业务数据与 CLI 默认输出不变。
- 受管理读取与发布直接校验 canonical，不再为校验创建临时工作区；地点上下文在一次读取内复用快照，保留完整分页、来源授权和错误诊断。
- 公开发行准备只生成最终 ZIP；指南检查与整包构建分开，发布命令统一使用本次选定的版本变量。
- 首次创建只维护默认工作流中的一套示例；公共索引保留全部方法合同。安装说明利用安装器自带预检，保留安装后的完整性复核。
- 地点窄补充在一次持锁期间完成上下文读取和准备，消除重复重读与查重；保留候选预览、修订冲突和同请求恢复。

### Fixed

- 能力说明和坐标诊断中的指南路径统一指向安装包内的 `references/`，可直接找到对应指南；仓库入口沿用既有路径适配。

### Compatibility and validation

- 公开方法、数据合同 1.0、Schema 与依赖保持不变；独立私人站点的 Service Worker 修复不进入 Skill。
- 本地已验证合成安装包在仓库外读取指南、续改并校验 canonical；这不等同于自然 Agent 使用或线上发布验收。正式发行 ZIP 仍需单独核验。

## [0.3.9] - 2026-10-05

### Changed

- 精简 Skill 入口、安装说明和默认工作流，集中说明创建、在原目录续改和保持原网址预览；专题细节通过随包指南按需读取。
- 公开指南统一从开发仓库的 `authoring/` 生成，修复仓库内引用；发行包的 `references/` 路径保持不变。
- 同一 Python 进程重复校验时复用固定 Schema 的加载与准备；每次仍执行输入数据和领域规则校验。
- 修复公开首页安装指南的段落链接。

### Compatibility and validation

- 不改变公开 API、数据合同 1.0、网页、依赖或既有攻略；保留来源、未知、原子写入和失败恢复边界。
- 本地已验证安装包完整性及合成攻略的创建、修改、同网址预览数据读取和停服。未新增自然 Agent 使用效率、跨模型或页面目视验收声明；正式发行产物另行核验。

## [0.3.8] - 2026-09-29

### Changed

- 总览“旅途天气”标题旁统一提供一个来源信息入口，各天的总览卡不再重复显示。每日行程卡保留地点标题旁入口；复用原来源、许可、舍入说明及 hover/键盘/tap 操作，总览卡仍进入对应日程。

### Compatibility and validation

- 只调整来源入口位置，不改变数据合同、天气请求、离线快照、真实旅行数据或其他页面。公开包仍不包含私人站点鉴权与离线存储；原八张电脑/手机导览及完整许可文件保留。
- 聚焦天气/总览测试、桌面与 390/320 真实 Chrome 的唯一入口、导航和来源交互、默认/站点 build 已验；正式 ZIP 另验完整性、隐私、确定性构建和包外渲染。未重复无关全套、历史截图或外部 caller，未新增真机或生产网络验收声明。

## [0.3.7] - 2026-09-28

### Added

- Day 可选择一个已有 Place 或 AccessPoint 作为天气地点，公开 `day.add` / `day.update` 支持选择与清除；新增天气指南与能力说明。不会从酒店、地图中心或日程顺序自动选点。
- 网页直接查询 Open-Meteo，按 Day 日期、时区和地点显示天气、气温、风速与降雨概率。总览天气卡可进入对应日程，日程整卡可刷新；地点标题旁信息入口提供可交互的 Open-Meteo / CC BY 4.0 来源链接，支持 hover、键盘与移动 tap。

### Compatibility and validation

- 数据合同仍为 1.0，`Day.weather_location_ref` 为可选新增字段；旧无天气包保持有效，带字段包需 0.3.7 或更高版本支持，旧严格验证器可能拒绝新字段。预报是运行时资料，不写入 canonical。
- 在线预报只在会话中保留，直连请求不携带本站凭据或私人 headers；免费接口限非商业使用。另行部署的站点可在用户手动保存攻略时保存绑定版本的天气，部分天气失败不阻断完整攻略；独立站点鉴权、离线存储、私人资料与 key 不进入 Skill。
- 受影响模型、authoring、分发、Web 及 build 已验；真实 Chrome 1440/390/320 覆盖天气状态、来源交互和离线边界，旧无天气六张页面截图逐像素一致。公开坐标的一次本地浏览器直连成功，合成预报不冒充真实数据。正式 ZIP 另行核对完整性、隐私、确定性构建和包外公开入口。
- 既有八张电脑／手机导览保留为 0.3.6 页面证据，不声称包含新天气区域。未新增自然 caller、真实手机、生产网络或真实旅行地点选定验收；历史冻结评估 ZIP 缺失门禁保持原结论。

## [0.3.6] - 2026-09-28

### Changed

- 公开产品介绍、安装包入口与页面截图统一使用“行迹”品牌名称；Skill 标识 `travel-handbook-builder-skill`、命令、公开 API 与 1.0 数据合同保持不变。
- 精简公开主页与包 README，保留截图、安装和首次使用所需提示；运行环境与本地预览服务细节通过两份随包指南查看，专业方法和恢复示例从各自指南读取。

### Compatibility and validation

- 本版为品牌与文档发行，不新增运行行为、依赖或托管能力。独立私人站点的品牌图标、鉴权、离线内容存储、真实攻略和 Google key 不进入 Skill。
- 截图用完全虚构的“青湾慢游”与自制示意插图在候选网页重新拍摄，未使用私人旅行或地图凭据。候选另行检查品牌文字、文档链接、297 文件完整性、包外入口与确定性 ZIP。
- 不新增自然 caller 成功率、旅行事实、所有设备体验或真实手机验收声明；此前各版未验边界与历史冻结评估 ZIP 缺失门禁保持原结论。

## [0.3.5] - 2026-09-27

### Fixed

- 修复移动端详情在打开时先出现在上方、随后跳回底部的问题。外层原生 dialog 不再因入场中的聚焦元素而自动滚动；地点、事项、待办、交通、路线与地图详情保持从底部连续进入。
- 保留面板内部长内容滚动、关闭后的焦点与原滚动位置，以及系统“减少动态效果”偏好；不改变动画时长、曲线和历史栈行为。

### Compatibility and validation

- 仅共享前端外层裁切方式修复，不改变旅行数据、公开调用方法或 1.0 合同。本站品牌图标、私人攻略、Google key 及托管站点能力不进入 Skill。
- 在桌面 WebKit 稳定复现外层 dialog 自动滚动造成的位置跳动，修复后反馈由红转绿。84 个真实浏览器场景（WebKit/Chromium、多尺寸、六类入口、关闭重开及 reduced motion）、84 项受影响单测、默认/站点构建通过；长内容内部滚动与动态视口尺寸另有检查。
- 本机 Chromium 未自然复现原症状，不据此限定问题只在 Safari，也不宣称用户手机 Chrome/PWA 已实机验收。原 IAB 不可读取，用户仍需刷新后复验；真实地址栏动画未在桌面模拟器完整重现。
- 发布候选另行核对完整性、隐私隔离、确定性 ZIP 与包外入口。历史冻结评估 ZIP 缺失门禁不变，不声明 Python 全套全绿或新的自然 caller 效果。

## [0.3.4] - 2026-09-27

### Fixed

- Google Maps 缺配置、加载/鉴权失败或浏览器离线时，不再自动请求公共 OpenStreetMap 瓦片，避免服务封禁图片被当作底图呈现。部分错误图片即使返回 HTTP 403 或 200 仍能被浏览器解码，不能仅靠图片 load 事件判断地图可用。
- fallback 保留手册自有地点、线段及交互，明确显示“地点示意，底图暂不可用”；可在线重试 Google，或打开外部 Google 地图。浏览器恢复在线后可重新加载地图。

### Compatibility and validation

- Google 优先需要用户自行配置、正确限制且获授权的 Maps JavaScript API 浏览器 key；本 Skill 不附带 key，也不替用户开通或支付 Google 服务。没有配置时仍可查看地点示意，**不提供真实离线底图**。既有无 key / `provider: osm` 响应可继续消费，但显示为无底图示意。
- 不改变旅行数据、公开调用方法或 1.0 数据合同。独立托管站点的鉴权、离线下载与生产 key 配置不进入 Skill。
- 73 项受影响地图/日程测试、Web 构建及合成资料的真实 Chromium 回放通过；HTTP 403/200 错误图片场景均不再引入外部瓦片。其他安装环境的 Google 权限、真实 iOS/Safari、外部事实与素材仍需分别核验，不以 stub 或当前站点验收替代。
- 发布候选另行校验完整性、隐私、确定性 ZIP 和包外入口。历史冻结评估 ZIP 缺失门禁不变，不声明 Python 全套全绿或自然 caller 效果提升。

## [0.3.3] - 2026-09-27

### Fixed

- 图片加载失败时保留原有占位尺寸并提供局部重试；原本没有图片的内容保持简洁。地图加载设有超时、失败提示与恢复操作，快速切换日期时清理旧任务，不再无限等待或让旧结果覆盖当前日程。
- 待办勾选无法保存到浏览器时明确提示未保存，并允许重试；同一次页面会话内切换栏目仍保留勾选，按旅行隔离。正常保存不增加打断阅读的提示。
- 地点、任务、交通、事项和地图详情使用可中断的进出动效；快速关闭重开、重复按 Escape、嵌套地图内地点详情和浏览器返回只处理相应层级，并恢复焦点与滚动位置。

### Changed

- 手机详情随短内容自然收缩，长内容最多约占屏幕高度的 90%，适配安全区；桌面详情保持便于阅读的宽度。控件按下即时反馈，选中日期保持可见，地图悬停只高亮，点击或键盘操作才打开信息。
- 尊重系统“减少动态效果”偏好，取消详情位移及地图飞行动画；离线打开外部链接时提供局部提示，链接目标保持不变。

### Compatibility and validation

- 不改变旅行数据、公开调用方法或 1.0 数据合同；独立托管的多旅行站点、鉴权与离线下载不包含在本 Skill 中。
- 集成 Web 检查通过 231 项、跳过 5 项既有私人样本检查；构建及使用合成资料的 Chromium 行为检查通过。真实 iOS/Safari、Google 鉴权服务及外部素材可用性仍需单独验收。
- 发布候选另行核对包完整性、确定性 ZIP、隐私隔离及包外入口。既有历史冻结评估 ZIP 缺失的门禁不变，不声明 Python 全套全绿或自然 caller 效果提升。

## [0.3.2] - 2026-09-27

### Changed

- 日程中的“其他兴趣点”采用更紧凑的桌面与中屏缩略图；手机继续上图下文，图片高度适应屏幕。已在当天日程地点卡出现的同一地点不再重复显示，其他日期及未采纳的推荐保留。
- GitHub 主页改为中文产品介绍，加入真实页面截图、简短开始步骤及自然语言示例；技术用法与详细验证边界通过专门文档链接查看。截图使用完全虚构的演示资料与自制示意插图，不包含私人旅行资料。

### Compatibility and validation

- 本次不改变旅行数据、公开调用方法或 1.0 数据合同。受影响的 60 项日程测试、构建和响应式页面检查通过。
- 发布候选已校验 ZIP、公开文件、图片链接、隐私和包外入口。既有 Python 全套中两个历史冻结 ZIP 缺失保持原失败门禁，不宣称全套全绿。
- 不新增自动规划、订票或事实核实能力，不声明自然 caller 效果或效率提升；实际攻略升级、真实地图服务、外部素材和旅行事实仍单独核对。

## [0.3.1] - 2026-09-27

### Fixed

- Source URL 与图片 locator 保留原文，Unicode/空格在显示边界编码，已有转义与查询参数保持；新写入非法地址拒绝，历史坏地址给局部诊断，不再因单个资源地址阻断整份攻略。
- managed 预览正常 stop→start 保留外部 media-root 配置；提供显式更换/清除和失效提示。只读 preview-status 识别实际包、服务与前端资源，不能把版本号或旧 tab 当成已刷新证明。
- 日程路段解释收进所属详情，统一弹层与关注点响应式布局；Google AdvancedMarker 使用当前标准点击事件并清理监听，OSM 测试等待真实 marker 就绪。

### Changed

- 新增只读 `read --report map-coverage`，按日完整分页核对地点、入口、候选与路径的输入/投影缺口，不自动选点或增加门禁。
- `read` / `client read --omit-capabilities` 显式省略重复能力元数据，默认输出保持；错误提供不猜测对象的恢复路径。
- 指南收敛地点介绍、当天节奏、本次选择与来源说明，明确 Task 完成范围、现场办理撤下及候选采纳边界；素材盘点同时分页 Place/Media，避免遗漏未绑定介绍图的地点。

### Compatibility and validation

- 继续使用 `1.0` profile；保留原身份、来源和未知项。使用更新后的运行时与网页消费新增 URL 合同；旧版严格校验器不保证接受这些来源地址。
- 当前候选通过 Web、构建/包完整性与隐私、受影响测试及包外公开入口验收。Python 完整首跑的两个过时文案断言已修后通过，另两项历史冻结 ZIP 缺失仍保留原失败门禁，不宣称全套全绿。
- 未开展新的自然 caller 效果/效率实验。真实鉴权 Google SDK、原 in-app browser 问题、远程素材可用性/许可和旅行事实仍有独立验收边界；发布不代表本机已安装或真实攻略已更新。

## [0.3.0] - 2026-09-26

### Changed

- 增加 `task.retire`：仅对 open Task 写入有理由的 `not_needed`，保留身份、历史及旧完成记录，返回需复核的引用；当前待办不显示撤下项，不伪造完成。
- Route Stop 可选 `encounter_kind=visit|pass_through`，支持公开 compose/edit 设置与清除，缺省保持未指定；原位 `route.bind_visit` 保留安排身份。日程仅对明确经过点去卡，连接和必要事实保留，不做同地点全局去重。
- 扩展 Trip/Day 原位文案、Task action/targets/notes 和来源可读性；网页补足图片、详情、待办和响应式表现。无 Google Key 可用 OpenStreetMap；统一分类标记与跨尺寸重算，保持 Place/AccessPoint 坐标身份，内部采集诊断不进入旅客界面。
- 公开指南补充 Task/现场提示、地点事实/行程日期、共享来源批量写入和地图有界采集的具体核对；不新增自动选择、预订、付款或公开发布能力。
- 酒店地点可明确记录当地入住起始时间 `role_details.lodging.check_in_time`，公开 Place 创建/更新支持角色详情整体设置与清除并保护已有字段证据。首次到店仍为 check_in；只有明确到店时间与酒店时间上下文可安全比较且早于起始时间时，页面显示“入住·行李寄存”。等于/晚于或时间未知、冲突时保持“入住”，后续 return 不变；不推断提前进房或自动改行程顺序。
- 继续使用 `1.0` profile；旧数据缺省保持兼容，含新可选字段的包不保证旧严格校验器接受，须保留生成版本。
- 既有独立 caller 在 GuideNote 重复及日期归属仍有部分失败；已知问题的确定性副本修复和指南静态检查不证明最终指南的自主执行效果。本版工程、包外 CLI 与页面验证已分别留证；这些证据不替代外部事实、Google真实鉴权和公开素材许可的核对，也不表示用户本机已安装。

## [0.2.0] - 2026-09-25

### Added

- 受管理攻略续作：`client init/read/context/prepare-request/prepare-place/commit/check/status` 在同一目录保存完整 state、请求记录与稳定 canonical；完成后仍可由新会话读取并继续更正。
- 独立的 owned `preview-service`：启动、核对和停止同一 managed ROOT 的本地预览；合法提交后可在原 URL 刷新最新数据。
- 扩展的公开 Task、Stay、Trip 摘要与 Media 方法及按需指南；已完成 Task 的清单更正保留原完成事实与历史，图片记录与用途不冒充网页显示。

### Changed

- Skill 入口更明确地区分公开读/写、来源与用户决定、数据级预览和页面目视证据；普通旅客答复默认先交代实际结果、重要未知与可用预览，不必罗列内部 ID。
- 默认发布构建版本升为 0.2.0。公开调用仍以当前 bundle 的方法清单、manifest 与 Schema 为准；本版未增加自动选行程、预订、支付或公开发布能力。

### Compatibility and validation

- 继续使用 `1.0` schema profile；含新增可选字段的 0.2.0 包可能被旧版严格 `1.0` 校验器拒绝，保留产物对应的 bundle 版本。
- 发布候选须通过确定性构建、manifest/ZIP 完整性与隐私检查、公开 CLI/运行环境检查及受影响回归。此前不同候选上的外部 Agent 单例是有限参考，不替代本版 release asset 的验收。
- 本次不以 0.1.0 文档中的 Kimi 多场景集冒充 0.2.0 已通过；发布后将另用新会话 Codex 和用户提供的旧行程 Markdown 检查真实重建，结果与缺口届时单列。

## [0.1.0] - 2026-09-20

首个公开版本。

### Added

- 发布完整的 `travel-handbook-builder-skill` Agent Skill、公开调用指南、本地 Python 运行时、Schema、启动器和完整性 manifest。
- 将开发阶段的多版 draft Schema 收敛为单一公开数据契约 1.0；新建 Trip 直接启用完整公开能力，不需要逐级升级。
- 支持新建工作区、完整 state 恢复、canonical package 导入、局部读取、preview、原子 apply、check 和私有 export。
- 支持旅行日期与 Day、地点与入口、安排、推荐、住宿、交通与路线、成员与分组、费用与汇率、准备任务、来源快照、有限来源刷新和确认历史。
- 支持 selected-but-unassigned 安排、明确未知值、跨轮稳定 identity、成功请求日志和相同请求精确重放。
- 将明确受限的来源修订映射为最小字段 patch；现状、unknown 或 unchanged 的重申只作为保留条件，并通过 preview、apply 后 readback 核对对象级差异。
- 将明确的道路客运接驳车、接驳巴士、摆渡车、班车及 shuttle bus/coach 规范化为 `bus`；scheduled/independent 仍由必要班次身份和合法 Calls 决定，运营方未知不阻止 scheduled，班次身份不足时保留为 independent bus Leg，不降级为 `other`。
- 提供隔离 `.venv` setup、绝对路径 CLI/Python wrapper、运行时 bytecode 抑制、重复 setup 和 bundle 完整性校验。
- 提供 MIT 许可证、第三方归属、发布维护文档、确定性 ZIP 构建工具和 GitHub CI。

### Safety and boundaries

- 不从缺失资料推断现实日期、地点、坐标、资格、价格、预订或付款。
- 不执行旅行选择、现实预订、支付、公开发布或事实核验。
- 完整 state、canonical export 和 export report 有明确边界，避免把诊断报告误作可导入领域包。
- 运行库只从 bundle 内加载，忽略继承的 `PYTHONPATH`；正常使用后仍可重复验证 manifest。

### Validation

- 外部自然发现发布门槛固定使用 Kimi CLI、请求配置 `kimi-code/k3` + high，不自动重试或切换模型；实际版本和结果随 GitHub Release notes 发布。
- 冻结验收集覆盖多人多币种、自驾、跨日航班、混合徒步、恢复重放和独立保留案例。
- 公开包由开发仓库确定性生成；分发测试验证单一 `runtime/schemas/v1`、无 draft 目录和无 `trip.upgrade_schema` 调用面。

[Unreleased]: https://github.com/kyangc/travel-handbook-builder-skill/compare/v0.3.11...HEAD
[0.3.11]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.11
[0.3.10]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.10
[0.3.9]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.9
[0.3.8]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.8
[0.3.7]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.7
[0.3.6]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.6
[0.3.5]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.5
[0.3.4]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.4
[0.3.3]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.3
[0.3.2]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.2
[0.3.1]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.1
[0.3.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.0
[0.2.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.1.0
