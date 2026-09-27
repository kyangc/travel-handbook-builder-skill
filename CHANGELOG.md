# Changelog

本文件记录 `travel-handbook-builder-skill` 的所有对外发布变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

本节暂无新增条目。

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

[Unreleased]: https://github.com/kyangc/travel-handbook-builder-skill/compare/v0.3.2...HEAD
[0.3.2]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.2
[0.3.1]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.1
[0.3.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.3.0
[0.2.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.1.0
