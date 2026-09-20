# 具体核实事项与待办

1.0 可用 `issue.record` 保存一个明确对象上的未决问题，再让 `task.add` 针对该 Issue。这个入口用于来源能命名问题对象、但不能把问题可靠定位到某个执行片段的情况；它不推断问题属于哪条路线或哪一个 Segment。

## 建立具体问题

先建立来源明确命名的 Place，再建立 Issue。`targets` 必须是非空的 Place handle 列表；raw Ref、Item、Route、Stop 或其他类型均拒绝。`title`、`impact` 和可选 `resolution_needed` 必须是明确非空文字。

```python
{"method": "place.add", "as": "south-bridge", "args": {"name": "南桥"}}
{"method": "issue.record", "as": "bridge-status", "args": {
    "title": "南桥是否开放",
    "targets": [{"local": "south-bridge"}],
    "impact": "影响徒步通行",
    "resolution_needed": "出发前核实开放状态"
}}
{"method": "task.add", "as": "verify-bridge", "args": {
    "title": "核实南桥是否开放", "action": "verify",
    "targets": [{"local": "bridge-status"}]
}}
```

这不会把南桥加入 Route Stops，不会生成坐标、开放时段或所属 Segment，也不会把 Issue 自动解释为整个 Route 已完成。`task.add` 可把具体 Issue 作为核实目标；VehicleUse 等未列出的类型仍不能作为 Task 目标。

## 明确完成与解决

Task 完成和 Issue 解决是两个独立动作。只有来源明确时才提交 `issue.resolve`；该动作必须带 operation `origin`。`estimate` 不能建立解决事实，非 example 工作区也不能使用 `synthetic_fixture`。

```python
{"method": "task.complete", "args": {
    "target": verify_bridge, "record_note": "已核实开放"
}}
{"method": "issue.resolve", "args": {
    "target": bridge_status, "resolution_note": "南桥开放"
}, "origin": {
    "basis": "observation", "statement": "来源记录：已核实南桥开放"
}}
```

`issue.resolve` 只允许 `open → resolved`，保留 Issue 身份、目标、影响及所需解决内容。解决说明保存在可审计 receipt；领域包生成一条 `target.field=status`、`value=resolved` 的 adopted Claim，依据直接来自 origin，不再生成泛化 `authoring_statement` Claim。相同解决说明和 origin 的新请求返回 `no_change`，不同说明或依据返回 `ISSUE_ALREADY_RESOLVED`；同一 request 重放不重复 Claim 或 revision。

Task 完成不会自动解决 Issue，Issue 解决也不会自动完成 Task。若原 Task 已经挂在 whole Item 或将删除的执行片段上，局部执行替换仍按原目标拒绝；工具不会自动改挂到 Issue。

`read` 返回 Issue 与 Task 对象及稳定 handle，`check` 校验关联，`export` 保留 `issues`、Task `target_refs` 和 status Claim。该结构表达核实事项及其依据，不证明 Place 已经被定位到路线，也不提供通行评估。
