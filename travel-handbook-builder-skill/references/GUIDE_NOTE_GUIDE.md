# 攻略说明与出处调用指南

本指南描述已经可调用的 `source.record`、`guide.note.add` 和 `guide.note.update`。GuideNote 是包级说明，适合保存入境、通信、购物提醒等跨日程文字；它不是 Item、Task、Claim，也不会自动进入某一天。

## 数据契约

新建 Trip 直接使用稳定数据契约 1.0。`source.record`、`guide.note.add` 和 `guide.note.update` 均可直接调用；调用方不需要管理内部迁移步骤。

## 记录普通来源

`source.record(kind, title, url?, published_at?, notes?)` 记录调用方已经掌握的来源元数据：

```python
{"method": "source.record", "as": "official", "args": {
  "kind": "official",
  "title": "示例官方说明",
  "url": "https://example.com/guide",
  "published_at": "2026-09-19",
  "notes": "调用方记录的来源地址"
}}
```

kind 使用 Source 既有枚举：`user_statement`、`confirmation`、`official`、`observation`、`estimate`、`synthetic_fixture`、`other`。该方法不联网、不抓取页面、不生成 checked_at，也不从标题、URL 或 notes 推断 Claim。普通来源的 citation 只导出 `source_ref`。

Source 元数据不可原位更新。需要纠正时，新建 Source，再用 `guide.note.update` 整体替换对应 paragraphs。

## 新建全局或关联说明

全局说明省略 related：

```python
{"method": "guide.note.add", "as": "entry", "args": {
  "title": "入境提醒",
  "paragraphs": [
    "第一段没有记录出处。",
    {"text": "第二段引用普通网页。", "citations": [
      {"source": {"local": "official"}}
    ]}
  ]
}}
```

字符串段落会归一化为 `{"text": ...}`。段落顺序保持；citations 若提供必须非空。省略 citations 表示出处未记录，不表示内容无来源或已经核验。

related 只提供阅读上下文，不修改关联对象，也不把说明变成日程或待办：

```python
{"method": "guide.note.add", "args": {
  "title": "住宿周边通信",
  "paragraphs": ["到店后按实际网络情况处理。"],
  "related": [trip_handle, stay_handle, trip_handle]
}}
```

related 必须是非空 handle 列表。重复引用按首次出现顺序去重。

## 精确引用已登记原文

完整原文继续用 `source.register(document_key, text, title?)` 保存于编制工作区。精确 citation 的 start/end 是 Python Unicode code point 的左闭右开范围：

```python
text = "甲🙂乙かな한글"
start = text.index("🙂")
end = start + len("🙂乙か")

{"method": "source.register", "as": "snapshot", "args": {
  "document_key": "entry-guide", "title": "原文", "text": text
}}
{"method": "guide.note.add", "args": {
  "title": "精确出处",
  "paragraphs": [{
    "text": "保留一段精确出处。",
    "citations": [{"anchor": {
      "source": {"local": "snapshot"},
      "start": start,
      "end": end,
      "exact_text": text[start:end]
    }}]
  }]
}}
```

工作区检查 source 身份、非空范围、边界和 exact_text。导出 citation 包含 source_ref、excerpt、`unicode_codepoint_range` 和 snapshot_sha256；完整 snapshot 正文不进入领域包。普通 `source.record` 不能冒充原文快照提供 excerpt。

若素材明确自称“完全虚构”“合成”或等义表述，说明段落的**每一条** citation 都必须能在它所引用的导出 Source 元数据中独立保留这一属性，不能依赖同段另一条 `synthetic_fixture` citation 代为说明。普通 `source.record` 使用 `kind="synthetic_fixture"`；需要精确引用 `source.register` 快照时，快照 title 也必须明确写出“完全虚构”或“合成”等原有属性。若通用快照 title 没有该标记，就不要把它和合成来源一起挂到该段落上；可只引用 `synthetic_fixture` Source。不得给没有自称虚构或合成的素材添加此标签。

GuideNote 可以引用同一 document_key 的历史快照。后续登记新快照不会回写旧 citation。这个规则只适用于说明引用；`source.duration.refresh` 仍要求同一文档的最新快照和既有 document_key 绑定，不能用本指南放宽耗时刷新合同。

## 原位更新

`guide.note.update` 保持 GuideNote id：

```python
{"method": "guide.note.update", "args": {
  "target": note_handle,
  "title": "修订后的标题"
}}
{"method": "guide.note.update", "args": {
  "target": note_handle,
  "paragraphs": ["整组替换后的段落"]
}}
{"method": "guide.note.update", "args": {
  "target": note_handle,
  "clear_related": True
}}
```

省略字段保持原值；paragraphs 和 related 提供时整体替换。`related=[]`、`paragraphs=[]`、同时 related 与 clear_related、未知字段和空文字都会原子拒绝。提交与当前值相同的更新返回 `no_change`，但新成功请求仍按共同协议保存回执并增加 revision。

从 `read_workspace` 或 export 读回的 citation 是导出形状，不能把其中的 `source_ref`、`excerpt`、`locator`、`snapshot_sha256` 原样作为更新请求。整体替换 paragraphs 时，先用 read 中的对象 handle 和 `source_imports` 重建调用形状：普通引用写 `{"source": source_handle}`；精确引用按原 citation 的 Source 身份找到对应 snapshot，再写 `{"anchor": {"source": snapshot["source"], "start": start, "end": end, "exact_text": snapshot["text"][start:end]}}`。保留历史引用时必须继续指向同一 snapshot，不能因为已有更新版本就擅自换成最新 snapshot。

默认调用不会新增 Claim。若调用方显式提供操作级 `origin: {basis, statement}`，通用协议仍会记录针对主对象的 `authoring_statement`；这是调用方声明，不表示网页内容已联网核验。
