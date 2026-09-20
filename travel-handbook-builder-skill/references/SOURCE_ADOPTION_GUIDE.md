# 有界来源采用协议

本有界协议提供 `source.identity.bind`、`source.field.apply`、`source.field.resolve` 及 typed Route 的来源采用变体；不提供通用 Markdown 同步。

这些方法及 `route.compose/route.replace_interval` 的 `source_adoption` 变体要求 1.0。现有 `source.duration.*` 保持兼容；同一 dwell/duration 不能同时有两种活 binding。Task 只可建立/取得身份，没有状态 adapter；Issue、Reservation、Coverage、Cost、Payment 也没有来源状态 adapter。

## Anchor 与身份

先用 `source.register(document_key,title,text)` 保存完整原文。每次采用使用同一 `document_key` 的最新快照和精确 Unicode 半开区间：

```python
anchor = {
    "source": source_handle,
    "start": 0,
    "end": len(text),
    "exact_text": text,
}
```

身份唯一键为 `(document_key, semantic_key)`。`object_type`、首次 `occurrence` 和 `target` 绑定后不可改变。名称、文字相似、坐标相同均不合并。重复经过同一 Place 时复用 Place key，每个 Stop occurrence 使用不同 key。

首次绑定及以后取得：

```python
{"method": "source.identity.bind", "args": {
  "anchor": anchor, "semantic_key": "task/bridge-check",
  "target": bridge_task, "occurrence": "bridge-check",
  "expected_type": "task"
}}

{"method": "source.identity.bind", "args": {
  "anchor": newest_anchor, "semantic_key": "task/bridge-check",
  "expected_type": "task"
}}
```

第二次回执 `primary` 是原对象当前 handle，`parts.identity_outcome` 为 `reused`。同批新对象和 Route part 可用 local/part reference 首次绑定。错类型、错 occurrence、重指 target 或 tombstone key 均原子拒绝。

## Route topology 身份

`route.compose(..., source_adoption=...)` 映射首稿全部 Stop/Segment；`route.replace_interval(..., source_adoption=...)` 只映射本次新建 interior Stop/Segment：

```python
source_adoption = {
  "anchor": anchor,
  "route_key": "route/hk",
  "stops": {
    "typed-local-key": {
      "semantic_key": "stop/stable-occurrence",
      "place_key": "place/stable-place"
    }
  },
  "segments": {
    "typed-local-key": {
      "semantic_key": "segment/stable-occurrence",
      "leg_key": "leg/stable-occurrence"  # 仅 leg-backed Segment
    }
  }
}
```

新 topology 仍由 typed Route 参数完整表达，不另交 graph patch。成功后才绑定新对象；删除的纯身份原子转 `tombstoned`。`identity_index` 与 `topology_bindings` 是历史 metadata，不因自身阻止合法删除；活字段 binding、领域 Claim、Task、Cost、Coverage 等仍按各自保护规则阻止删除。

## 明确字段提议

`source.field.apply` 每次只提交一个原文明示值：

| aspect | identity target | value |
|---|---|---|
| `item.timing` | Item | TimePlan |
| `item.place_ref` | shopping Item | Place handle |
| `place.location` | Place | 完整 Location，显式 coordinate_system |
| `stop.dwell` | Route Stop | 分钟或 `[min,max]` |
| `segment.duration` | inline Route Segment | 分钟或 `[min,max]` |
| `segment.path` | inline Route Segment | Path handle |
| `leg.timing` | Route Segment 所属 Leg | TimePlan |

首次可同时建立身份；已有 identity 省略 target/occurrence：

```python
{"method": "source.field.apply", "args": {
  "anchor": anchor, "identity_key": "item/hk-route",
  "target": route_item, "occurrence": "route-item",
  "aspect": "item.timing",
  "value": {"kind": "fixed", "start": {
    "local": "2027-09-18T08:00:00", "timezone": "Asia/Tokyo"}},
  "basis": "user_statement"
}}

{"method": "source.field.apply", "args": {
  "anchor": r2_anchor, "identity_key": "segment/south-ridge",
  "aspect": "segment.path", "value": south_track,
  "basis": "synthetic_fixture"
}}
```

`basis` 使用现有 Claim vocabulary：`user_statement`、`confirmation`、`official`、`observation`、`estimate`、`synthetic_fixture`、`other`。`statement` 固定为 anchor 的 `exact_text`，`source_refs` 指向该快照。

方法经现有 typed 写入口更新：Item 用 `plan.update`，Place 用 `place.update`，dwell/duration/path/Leg timing 用 `route.edit`。已有时间、地点、路径、完成历史保护继续生效。成功只同步对应 Route topology guard aspect，不接纳其他人工差异。`field_proposal_history` 只记录 caller 明确提交的值和依据；扫描到但未提交的时间、地点不属于来源提议。

## 三方比较和裁决

已绑定字段比较上次 source baseline、当前领域 value/adopted Claim、当前明确 proposal。当前等于 baseline 时可采用；value、basis、statement、source 全同返回 `already_matches`。数值相同但 basis 改变仍是新依据。普通 typed 编辑不会移动 source baseline。

当前偏离 baseline 且不完全等于 proposal 时返回 `SOURCE_FIELD_CONFLICT`。A→B→A 即使 A 来自更高 sequence 也返回 `SOURCE_PROPOSAL_HISTORY_CONFLICT`，两者错误详情均含签名 `conflict`：

```python
{"method": "source.field.resolve", "args": {
  "conflict": exact_error_details_conflict,
  "choice": "keep_current",  # 或 apply_proposed
  "reason": "人工复核说明"
}}
```

`keep_current` 保存理由并保留旧 source baseline，只把该 exact aspect 的 topology guard 对齐当前值。`apply_proposed` 再走 typed 写入并更新 baseline。workspace revision、binding、当前值或 conflict 内容变化后会返回 stale/invalid conflict，须重新 apply。

`keep_current` 不进入“已实际采用”的历史。之后用**同一个 snapshot 和 statement**重提会幂等返回 `kept_current`；换成更高 sequence、不同 statement/source 但相同旧业务值，仍返回 `SOURCE_PROPOSAL_HISTORY_CONFLICT`。反复 `keep_current` 不解除保护；只有显式 `apply_proposed` 才把旧值写入实际采用历史。

`source.field.resolve` 在执行时重新验证 conflict anchor 仍是该 `document_key` 的最新 snapshot。同一批先登记该文档更晚 snapshot，再裁决旧 conflict，会返回 `STALE_CONFLICT`，整个批次包括新登记一起回滚。同一 snapshot 的幂等 register 或其他 document 的更新不使 conflict 过期。

## 可读 metadata 和限制

`read_workspace(state)["source_imports"]` 暴露 `identity_index`、`topology_bindings`、`proposal_history`（只含明确 topology）、`field_bindings`、`field_proposal_history`、`field_decisions`。不得手改。

规范 package 导入会明确报告 `source_imports` 不可恢复；要保留原文 snapshot、绑定与裁决历史，必须重新打开完整 state，见[恢复指南](RECOVERY_READ_PREVIEW_GUIDE.md)。本协议没有 Journey 来源采用、Task/Issue 状态采用、通用 JSON patch、任意字段 adapter、自动文本解析、自动路线选择或旧 topology 恢复。
