# Contributing

这个仓库只接受会改变或维护公开 Skill 的内容：

- `SKILL.md` 的发现与调用指令；
- `references/` 中面向调用 Agent 的公共指南；
- `runtime/`、Schema、启动器和依赖；
- 安装、完整性、安全、兼容性和发布文档；
- 对上述内容有直接保护作用的发布工具或 CI。

请勿提交开发路线图、内部实验、评审日志、模型会话、私有旅行资料、真实订单信息、成功答案样本或与 Skill 发布无关的项目代码。

提交变更时：

1. 在 `CHANGELOG.md` 的 `Unreleased` 下说明用户可见影响。
2. 重新生成并验证 manifest。
3. 运行隔离 setup、CLI smoke test 和重复完整性检查。
4. 行为或 Agent 指南发生变化时，补做对应的零项目上下文验收；不要只依赖结构校验。
5. 确认仓库和 release ZIP 中没有凭据、绝对开发路径或私有旅行材料。

发布前完整步骤见 [RELEASING.md](RELEASING.md)。
