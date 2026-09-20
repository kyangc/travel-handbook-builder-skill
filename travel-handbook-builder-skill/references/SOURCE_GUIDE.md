# Agent 原文定位与单字段刷新

本入口只处理 1.0 中 Route 某次 Stop 的停留时长、某个内嵌 Segment 的耗时。沿用[共同批次约定](CALLER_GUIDE.md)和[路线方法](MOVEMENT_GUIDE.md)。不是 Markdown 解析器，也不是全攻略自动同步；Agent 负责理解文本和分钟数，工具检查位置、身份和覆盖条件。GuideNote 可引用历史快照，但这里的耗时刷新仍要求同一 document_key 的最新快照，详见[攻略说明指南](GUIDE_NOTE_GUIDE.md)。Route 首稿与区间替换的来源身份另见[Route 来源采用协议](SOURCE_ADOPTION_GUIDE.md)；它不改变本页的 duration binding。

## 1. 登记不可变原文

```python
{"method":"source.register", "as":"v1", "args":{
    "document_key":"trip-notes", "title":"原攻略 Markdown", "text":"🗾\r\n返程预计停留20分钟\r\n"
}}
```

必须先定义 Trip。document_key 是同一文档跨版本稳定的键，title 可省略为 document_key。text 是完整原文字符串，可为空；不读文件、不改文件、不规范化换行或 Unicode。Python 从文件读取时要保留 CRLF，例如 `path.read_bytes().decode('utf-8')`，不能用默认换行转换后再声称保存了原始字节语义。

primary / aliases.v1 是这份快照的 Source handle，同批后续可用 {"local":"v1"}。parts.snapshot 返回 document_key、sequence、sha256、source、title；快照原文可从 read_workspace 的 source_imports.snapshots 读取，按 source 指向的记录识别。

同一文档连续登记相同 text/title 复用最新快照；A→B→A 是三个不同序号/身份，不能用内容 hash 代替版本。不同 document_key 即使文字相同也不合并。新增快照不会自动刷新任何字段。

## 2. 首次明确采用，建立真实基线

先用现有 route.compose 建立安排和部件。首次采用某段原文：

```python
{"method":"source.duration.adopt", "args":{
    "target": hike_item, "part": return_stop, "key":"return-bridge-dwell",
    "anchor":{"source": v1, "start":3, "end":13, "exact_text":"返程预计停留20分钟"},
    "minutes":20, "basis":"estimate"
}}
```

示例偏移应由调用方按实际文本计算，推荐 Python：`start=text.index(phrase); end=start+len(phrase)`。若同样的句子出现多次，必须按上下文选正确出现，不能默认第一处。start/end 是 Python 字符串的 Unicode 码点半开区间，emoji 算一个码点，CRLF 算两个，组合字符不合并；不是 UTF-8 字节或 JavaScript UTF-16 下标。exact_text 必须非空并与保存原文切片逐字相等。

anchor.source 必须是该文档最新登记的快照。target 是 Route 的正式 Item，part 是属于它的 Stop/Segment handle；字段从 part 类型确定，调用方不传任意 JSON 路径。Stop 对应 dwell，Segment 对应 duration。minutes 是非负数字或 [min,max]，basis 用路线指南中的依据类型。Claim.statement 直接取 exact_text，没有第二份可自由改写的 statement 参数。

adopt 是明确写入操作，可以改变字段已有值；它不假装已经比较过原文历史。实现从实际写入的数值和当前 Claim 建立 baseline。parts.binding_id 返回绑定 ID；后续更新必须用它。key 在该 document_key 内唯一，一个耗时字段只允许一个来源绑定；重复声明不能新建另一个绑定绕过冲突。历史包只有对象身份、没有来源基线时，不能直接刷新，须明确采用一次。

生成的 Claim 指向具体部件字段，并以 source_refs 引用快照 Source。精确 anchor 保存在编制工作区 source_imports.claim_anchors，键为 Claim ID；完整原文和导入映射不塞进网页领域包。

## 3. 新原文刷新

先以相同 document_key 登记新文本，拿到新 Source handle，再调用：

```python
{"method":"source.duration.refresh", "args":{
    "binding_id": binding_id,
    "anchor":{"source": v2, "start": start, "end": end, "exact_text": phrase},
    "minutes":30, "basis":"estimate"
}}
```

只刷新这一个字段，不改同地点的其他出现。上次实际写入值、当前值及当前 adopted Claim 的身份/内容一起比较，不能仅看数字。旧声明和原来源不会被原地改绑，新快照采用后生成对应的新声明。

- 当前字段及其依据仍等于 baseline：可以采用新原文，并更新真实基线。
- 当前值、basis 和原句已与本次提议相同，但当前依据身份发生过其他改动：保留当前声明，记 `already_matches`，不把它伪装成来源写入的新基线。
- 否则返回 IMPORT_CONFLICT，整批未提交；包括前置合法修改、映射、声明和回执都回滚。
- 不支持静默回退旧快照、删除原文后自动删字段、跨文档复用绑定或整段替换路线。

parts.source_outcome 区分 adopted、already_matches、kept_current。metadata-only 操作的 effect 是 metadata；字段包变化是 structured，完全相同是 no_change。成功批次仍推进 revision 以保存回执。

## 4. 明确解决冲突

捕获 `AuthoringError`，从 `error.as_dict()["conflict"]` 取完整 conflict；里面给出 baseline/current/proposal 和读取版本。先按证据决定，再提交：

```python
{"method":"source.duration.resolve", "args":{
    "conflict": conflict, "choice":"keep_current", "reason":"已有明确选择，保留人工调整的40分钟"
}}
# 或 choice="apply_proposed"，明确采用原文提议。
```

conflict 必须原样传回，不能改值、target、anchor 或扩大字段范围。实现签名校验后重新检查 workspace、revision、binding、当前依据及最新快照；过期就重读并再次 refresh。不要把签名当网络安全边界：工作区文件是可信本地状态，能修改整份文件的调用者不在防篡改保证范围内。签名密钥不出现在公开 read/export。

keep_current 只记录这一份快照、这一条提议、这一份当前值的保留决定，**baseline 不变**。相同提议再次刷新且当前仍未变时不会重复冲突；换新快照、换提议或再改当前字段，需重新比较。apply_proposed 只采用签发冲突中的单字段提议，调用方不能夹带新的修改载荷。同一个 conflict 在同一批次只能裁决一次，重复则以 CONFLICT_ALREADY_RESOLVED 拒绝并整体回滚；不同字段的不同冲突可以同批处理。两种决定均保留 reason；不自动询问人或擅自选边，调用 Agent 依据已有授权作决定。

建议先独立提交 source.register，再刷新。若新快照和冲突发生在同一个失败批次，快照也会回滚；此时先登记成功、重新刷新取得冲突，不能假设失败返回的临时快照已经存在。

## 5. 恢复、读取与边界

read_workspace(state)["source_imports"] 可读取 snapshots 原文/序号、bindings 的 target/part/key/baseline/last_adopted/handled、claim_anchors 和 decisions。返回副本。普通 route.edit 不会偷偷改变来源基线。保留原工作区状态文件才能继续刷新和冲突恢复；只拿 export 的领域 JSON 不能恢复精确原文位置。

所有写操作走同一 apply 的 request_id、expected_revision 和原子提交。相同成功请求原样重放不恢复旧状态，也不新增快照、Claim或决定。reason 和 source文本不是执行指令。当前没有 source_refresh 通用模式、来源全文覆盖统计、字段删除、绑定迁移、自动冲突取舍或生产数据库并发能力。
