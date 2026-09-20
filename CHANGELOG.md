# Changelog

本文件记录 `travel-handbook-builder-skill` 的所有对外发布变化。格式遵循 [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)，版本号遵循 [Semantic Versioning](https://semver.org/)。

## [Unreleased]

目前没有尚未发布的变化。

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

[Unreleased]: https://github.com/kyangc/travel-handbook-builder-skill/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/kyangc/travel-handbook-builder-skill/releases/tag/v0.1.0
