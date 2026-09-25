# Python 备选：程序内创建与专业补充

只有需要在程序内处理 authoring state 或组合专业 request 时才读本页。普通新建和续作先按[默认文件式流程](DEFAULT_WORKFLOW_GUIDE.md)；发行包用 `scripts/python` 运行 Python caller，仓库内用项目 Python 3.12 与公开 `authoring` 模块。下列两个示例**各自独立**：创建示例输出一个新 managed ROOT；补充示例可从任何已有的 managed ROOT 开始，不依赖上段变量或旧初始化快照。示例事实均为合成材料，不可照抄为真实旅行事实。

公开调用失败抛出 `AuthoringError`，可用 `as_dict()` 查 `code`、`op_index`、参数与校验路径；不要在失败后继续提交或直接修改 state/package。managed 错误同样结构化返回，提交状态不明只重试原 operation ID。

## 程序内首次创建

从公开 `read_workspace` 取得起始 revision；只把材料明确给出的日期、时区、地点和已选安排写入语义 request。一个批次内使用 `local` 别名，不能把 preview 中的诊断性引用当成正式 handle：

```python
from pathlib import Path
import json

from authoring import apply, check, new_workspace, preview, read_workspace
from authoring.client import ManagedHandbook

root = Path("/absolute/output/managed handbook")  # 必须不存在或为空；首次网页前初始化
state = new_workspace("示例一日旅行", example=True)  # 仅合成演示使用 example=True
request = {
    "request_id": "create-handbook",
    "expected_revision": read_workspace(state)["revision"],
    "operations": [
        {"method": "trip.define", "args": {
            "start_date": "2027-04-06", "end_date": "2027-04-06",
            "default_timezone": "Asia/Tokyo",
        }},
        {"method": "day.add", "as": "day", "args": {
            "date": "2027-04-06", "timezone": "Asia/Tokyo",
        }},
        {"method": "place.add", "as": "first", "args": {
            "name": "示例地点甲", "roles": ["attraction"],
        }},
        {"method": "place.update", "args": {
            "target": {"local": "first"},
            "set": {"content": {"summary": "材料明确提供的地点甲简介。"}},
        }},
        {"method": "place.add", "as": "second", "args": {
            "name": "示例地点乙", "roles": ["attraction"],
        }},
        {"method": "place.update", "args": {
            "target": {"local": "second"},
            "set": {"content": {"summary": "材料明确提供的地点乙简介。"}},
        }},
        {"method": "plan.add", "args": {
            "day": {"local": "day"}, "kind": "visit",
            "title": "到访示例地点甲", "place": {"local": "first"},
        }},
        {"method": "plan.add", "args": {
            "day": {"local": "day"}, "kind": "visit",
            "title": "到访示例地点乙", "place": {"local": "second"},
        }},
    ],
}
proposed = preview(state, request)
```

**在此停下审阅** `proposed` 的变更、warnings 和材料一致性；不能自动认可预览。认可后才执行以下独立提交步骤。先把首次原 request 保存到已存在的 caller 输出目录，再调用 `apply`；成功后另存 receipt，供响应不明时用同一 ID/原载荷精确重放。不要从 receipt 反推 request；`ManagedHandbook` 的后续 journal 不会重建这次首次请求。

```python
Path("/absolute/output/create-request.json").write_text(
    json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
state, receipt = apply(state, request)
assert check(state)["valid"]
Path("/absolute/output/create-receipt.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
managed = ManagedHandbook.initialize(root, state=state)
status = managed.status()
assert status["state_revision"] == status["canonical_revision"] == state["revision"]
```

上面由公开语义 request 创建 Trip、Days、Places 与已选安排；managed 只接管持久化和以后续作，不替 Agent 选择事实。网页从第一次打开就读取 `root / "private-handbook.json"`，之后只从 managed 读取/提交，不再普通 `apply` 旧输入快照。`apply` 响应不明时用保存的同一 request ID/载荷恢复；`client init` 响应不明时先查 `client status ROOT`，不可覆盖已有目录。

## 从已有 managed ROOT 做专业补充

本段**不使用**上段的 `state`、`request`、`receipt`、`managed` 或别名。已有 ROOT 从当前 public context 取得 Place handle、revision、已有 content 与关联来源；有保存的 handle 时优先用 `target={"handle": "..."}`，否则仅在名称唯一时用 name。`place_context` 会追完分页，未找到或重名会结构化拒绝，不能按返回顺序猜一个。下面的开放事实、条件和来源仍只是合成示例；实际 request 只采用本次授权且有依据的内容，timezone 不从 Trip 猜测。

```python
from authoring.client import ManagedHandbook

managed = ManagedHandbook.open("/absolute/output/managed handbook")
context = managed.place_context(target={"name": "示例地点甲"})
place = {"handle": context["place"]["handle"]}
existing_content = context["place"]["record"].get("content", {})
adopted_cautions = [
    "本开放安排仅适用于 2027-04-01 至 2027-06-30。",
    "临时活动日或维护关闭可能另行公告，出行前需复核。",
]
merged_cautions = list(existing_content.get("cautions", []))
for caution in adopted_cautions:
    if caution not in merged_cautions:
        merged_cautions.append(caution)
updated_content = {**existing_content, "cautions": merged_cautions}

request = {
    "request_id": "enrich-first-place",  # 本次唯一且稳定；失败后有意修订才换 ID
    "expected_revision": context["revision"],
    "operations": [
        {"method": "source.record", "as": "hours_source", "args": {
            "kind": "synthetic_fixture",
            "title": "示例地点甲合成开放说明",
            "url": "https://example.com/place-a/hours",
            "notes": "合成演示；收录适用期、例外与临近出行复核条件。",
        }},
        {"method": "place.update", "args": {
            "target": place,
            "set": {"content": updated_content},
        }},
        {"method": "place.hours.update", "args": {
            "target": place, "scope": "venue", "timezone": "Asia/Tokyo",
            "weekly": [
                {"days": ["mon"], "closed": True},
                {"days": ["tue", "wed", "thu", "fri", "sat", "sun"],
                 "periods": [{"start": "09:00", "end": "17:00"}]},
            ],
        }},
        {"method": "guide.note.add", "args": {
            "title": "示例地点甲开放资料来源与适用条件",
            "related": [place],
            "paragraphs": [{
                "text": "合成示例的开放规则、适用期、例外和出行前复核条件。",
                "citations": [{"source": {"local": "hours_source"}}],
            }],
        }},
    ],
}
prepared = managed.prepare_request(request)
```

**在此停下审阅** `prepared["preview"]` 和材料授权。`place.update.set.content` 是整体替换；上例带回旧 content 子字段，只增本次已采用的 cautions。确需提交时只用同一 operation ID：

```python
committed = managed.commit(prepared["operation_id"])
current = managed.place_context(target=place)
diagnostic = managed.check()
```

核对 `committed`、`current` 和 `diagnostic` 的当前 revision、目标改动及 `publish_status`；发布失败但已提交时只重试同一 operation ID，不能另造 request。`diagnostic["report"]["availability_assessments"]` 是当前 state 的营业影响，旧 receipt warnings 不是；`stale` 表示网页仍在旧 canonical。确认其他 Place、Item/Day 身份与顺序未受越权改动，再刷新同一路径的网页。适用期是地点开放资料，不是本次到访日期；未知可保持未知，不能把 Day 日期复制到 Place。旧自管完整 state 的恢复与保存另见[恢复指南](RECOVERY_READ_PREVIEW_GUIDE.md)，不要把那套手写替换流程用于 managed ROOT。
