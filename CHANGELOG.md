# Changelog

本文件记录 `travel-handbook-builder-skill` 的所有对外发布变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

目前没有尚未发布的变化。

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

[Unreleased]: https://github.com/kyangc/travel-handbook-builder-skill/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.2.0
[0.1.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.1.0
