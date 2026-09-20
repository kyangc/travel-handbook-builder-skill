# 确认更新与整范围撤销

这两个入口记录来源明确的确认变更，不联系供应方、不取消订单，也不生成退款。沿用 [调用协议](CALLER_GUIDE.md) 的原子批次、稳定 handle 和操作级 origin。住宿与交通都可以使用；交通首次录入见 [交通权益指南](TRANSPORT_COVERAGE_GUIDE.md)。

## 数据契约

确认更新和整范围撤销属于稳定数据契约 1.0，可在 Trip 定义后直接调用。

## 更正完整确认

`coverage.replace_confirmation` 必填 target、benefits、scopes。它创建新 Coverage，通过 supersedes_ref 指向旧确认；旧确认及其 scope 都保留原值和原 handle。以下变量是 read 或先前回执返回的 handle，示例事实为虚构：

```python
{"method": "coverage.replace_confirmation", "as": "updated", "args": {
    "target": current_coverage,
    "benefits": [{"kind": "transport", "notes": "供应方补充确认的乘车权益"}],
    "scopes": [
        {"key": "outbound", "previous_scope": outbound_scope, "target": outbound_leg,
         "validity": {"date": "2026-10-03", "timezone": "Asia/Tokyo"},
         "participants": {"kind": "count", "count": 2}},
        {"key": "return", "previous_scope": return_scope, "target": return_leg}
    ]
}, "origin": {"basis": "user_statement", "statement": "虚构示例：补充确认去程日期和两人适用；返程范围仍未明确。"}}
```

这是**完整资料快照**：每个旧 scope 必须映射一次，不能增删、拆分或换 target；benefits 全量给出。各 scope 省略 validity/participants/quantity 会变为 unknown，不继承旧值；limits 省略则新确认未记录限制。reservation 省略保留原关联，显式提供时只能是原订单，不能改挂订单或清除关联。仍未知的内容应明确保持未知，不能误把省略当局部 patch。

`parts.scopes` 按本次 key 返回新 handle；`parts.scope_replacements` 给出 previous/current handle 对照。导出的每个新 scope 用 previous_scope_id 指向直接前一确认的 scope，因此离开编制工作区后仍可追溯。

这个入口允许依据来源更正日期、人数、数量，但不表示已建模“退掉其中某人、某一天或某项 benefit”。确认资料更正和实际权益撤销由调用方依据原文区分，工具不从人数差值推断退款或撤销。已撤销范围的状态不会因更正恢复。

## 只撤销已有的一段范围

```python
{"method": "coverage.revoke_scopes", "args": {
    "target": current_coverage, "scopes": [return_scope]
}, "origin": {"basis": "user_statement", "statement": "虚构示例：供应方明确撤销返程范围，去程权益仍有效。"}}
```

scopes 是属于当前确认的非空 scope handle 列表。新确认复制原范围资料，仅把选中 active scope 标为 revoked；未选中的范围保持原状态。全部撤销时整体 Coverage 为 revoked，否则有 active scope 就仍为 active。方法不自动修改 Journey、Stay、Reservation、Task、费用或付款。

回执 `parts.scope_replacements` 是稳定的旧→新对照；撤销回执的 `parts.scopes` 用字符串索引 `"0"`、`"1"` 标识新快照中的顺序。后续操作必须使用新 Coverage 及新 scope handle；历史 handle 仍可读取，但不能继续修改历史确认。全部结束后本轮不支持重新激活。

## 读取和展示当前权益

1.0 的 read、check、export 回执返回一致的 `coverage_projection`：

- current_coverage_ids：每条确认链的当前记录，可能已全部撤销。
- historical_coverage_ids：被后续确认替代的记录，只用于历史展示。
- effective_scopes：当前记录中明确 active 的范围引用。

不要遍历所有 state=active 的 Coverage 累计权益：旧确认会保留当时的 active 状态。effective 仅表示记录状态，不是按当前日期判断仍能使用，也不证明实际可乘车。不同范围的数量不能直接加成票数、剩余次数或共享额度。

导出的 package 保存完整历史；上述投影属于返回结果中的派生视图，不是新增 package 字段。独立消费者可以调用 `scripts/validate_trip.py` 得到投影，或按 supersedes_ref 选出未被替代的记录再检查 scope.state。

本轮不支持范围内按人/日期/benefit 拆分撤销、同票任选行程、共享次数、重新激活、订单状态修订、票号/PNR/座位凭证。缺少对应模型时应报告缺口，不能用另一份独立 Coverage 冒充同一权益的修订。
