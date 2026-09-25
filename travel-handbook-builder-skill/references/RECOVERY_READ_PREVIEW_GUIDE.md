# 恢复、局部读取与变更预览

本文说明 `import_package`、有界 `read_workspace` 与 `preview`。这三个入口不增加写方法；以 `capabilities.write_methods` 返回值为准。

## State、canonical package 与 export report

这三种 JSON 用途不同：完整 authoring state 用来无损续作；canonical handbook package 是 `export_package(...)` 返回值的 `package` 成员，也是 `import_package` 唯一接受的领域输入；完整返回值是 export report，除 package 外还含 validation、适用的 projection 字段和 manifest。CLI `export` 已自动抽取并只写 canonical package。

```python
from pathlib import Path
import json
from authoring import export_package, read_workspace

def save_json(path, value):
    path = Path(path)
    with path.open("x", encoding="utf-8") as output:
        output.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")

save_json("trip-state.json", state)  # 完整 state，用于续作。
export_report = export_package(state, revision=read_workspace(state)["revision"])
save_json("private-handbook.json", export_report["package"])  # canonical import 输入。
save_json("export-report.json", export_report)  # 可选诊断报告；绝不作为 import 输入。
```

若保存完整 report，使用 `export-report.json` 之类的独立名称；不要把它命名为 handbook/package，也不要传给 `import_package` 或 CLI `import`。

此例只适用于尚未进入 managed、三个目标都不存在的**调用方自管**文件；`open("x")` 拒绝覆盖。新攻略默认应在首次网页前使用[受管理客户端](CLIENT_GUIDE.md)，不再手写这些文件。已在网页使用的旧自管 canonical 暂不能自动 `attach`；若继续旧路径，只替换调用方明确拥有的文件，候选同目录写入、重读并验证后再原子替换，不能把旧 state 当作 managed 的续作输入。

旧自管路径若要续作，可对**原调用方拥有且已存在**的文件执行以下同目录替换；先保存新 state 和 `export_package` 结果并核对 revision，不用于 managed 目录或任意用户文件：

```python
import os
import tempfile
from authoring import check, import_package

def replace_owned_json(path, value, *, canonical=False):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"not an existing caller-owned file: {path}")
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            json.dump(value, output, ensure_ascii=False, indent=2)
            output.write("\n")
            output.flush()
            os.fsync(output.fileno())
        loaded = json.loads(temporary.read_text(encoding="utf-8"))
        if loaded != value:
            raise ValueError("candidate JSON changed on disk")
        if canonical and not check(import_package(loaded))["valid"]:
            raise ValueError("candidate canonical is invalid")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
```

只有在调用方已经明确拥有上述路径时才可使用；这不是并发写者间的比较并替换事务。默认 managed 续作只用 `client prepare-*`/`commit`，由客户端完成候选验证与发布。

## 打开 state 与导入 package

继续编辑时优先保存并重新打开完整 state JSON。它保留 `workspace_id`、revision、稳定 handle、成功 request 回执、`source_imports` 原文快照/绑定/裁决，以及 `issue_resolutions` 的解决说明和同值重放依据。读取 state 不升级 Schema，也不重新分配身份：

```python
import json
from authoring import read_workspace

state = json.loads(open("trip-state.json", encoding="utf-8").read())
view = read_workspace(state)
```

只有规范领域 package 时，使用导入而不是把它伪装成旧 state：

```python
from authoring import import_package, check, export_package

state = import_package(package)
assert check(state)["valid"]
assert export_package(state, revision=state["revision"])["package"] == package
print(state["import_report"])
```

```sh
scripts/travel-handbook import trip.json new-trip-state.json
```

导入先运行该版本公开 check 的结构和有限语义校验；未知版本、悬空引用、重复顶层 ID 或不合法模型整体拒绝。CLI 不覆盖已有 state 文件。导入逐值保留 package 的 revision、example、所有领域 ID、关系、历史、退役对象、Source、Claim、Issue 与 GuideNote，并为模型支持的实体和 LocalRef 建立稳定 handle。两个 owner 下相同的 Stop 等局部 ID 会得到不同 handle。

导入的新工作区有新的 `workspace_id`，`receipts` 为空。package 不含 `source_imports` 或 `issue_resolutions`，因此不能恢复旧 request 幂等历史、原文全文/位置、来源绑定、冲突裁决签名或 Issue 的 resolution_note 同值记录；`import_report.unavailable_authoring_metadata` 明确列出这些缺失项。已有领域 citation 和 resolved Issue 保留。后续 `source.register` 建立新的作者快照，不根据 Source 名称、notes 中的 hash 或 citation excerpt 重建原快照；对已 resolved Issue 也不会伪造解决说明或重新打开。

## 局部读取

无参数 `read_workspace(state)` 保持原完整读取形状，包括脱去 `signing_key` 的 `source_imports`、coverage/budget 投影和全部已注册对象。只要传 selection、limit 或 cursor，就进入局部模式：

```python
page = read_workspace(
    state,
    selection={
        "day": day_handle,                 # 字符串或 {"handle": ...}
        "types": ["item", "route", "stop"],
        "handles": [route_handle],
    },
    limit=25,
)
next_page = read_workspace(
    state,
    selection=page["selection"],
    limit=25,
    cursor=page["pagination"]["next_cursor"],
)
```

三个过滤器取交集。Day 选择包含 Day、该 Day 的 current Item，以及 Item 明确拥有的 Journey/Leg/Connection 或 Route/Stop/Segment；不会扩展 Place、Source、Coverage、Task 或任意全图依赖。1.0 待排 Item 不属于任何 Day，但可按 `types=["item"]` 或自身 handle 读取。retired 对象同样可按类型或 handle 读取。

局部结果包含 `workspace_id`、revision、schema_version、规范化 selection、pagination、objects、`related_handles` 和 capabilities。对象 entry 仍有 handle/type/record/owner，1.0 Item 仍有 ownership。`related_handles` 只给本页记录直接引用及直接 owned 局部对象的 handle，不递归展开关联对象。局部结果不附完整 package、全量 `source_imports`、coverage/budget 全局投影或其他来源原文。

局部读取默认每页50个 entry，显式 limit 必须是1–100的整数。排序按稳定领域身份，不依赖 state 字典顺序。cursor 绑定 workspace、revision 和规范化 selection；换工作区、发生写入或改变过滤器会报 `CURSOR_INVALID`，不会从另一页继续。

CLI 提供相同过滤：

```sh
scripts/travel-handbook read trip-state.json --day h-day --type item --type route --limit 25
scripts/travel-handbook read trip-state.json --type place --limit 25 --cursor '...'
```

来源全文只在显式选择 Source handle 时返回：

```python
source_page = read_workspace(
    state,
    selection={"handles": [source_handle]},
    include_source_text=True,
)
texts = source_page["source_texts"]
```

只写 `types=["source"]` 再要求全文会被拒绝，避免一次遍历整个原文库。导入 package 中的普通 Source 没有作者快照，因此对应 `source_texts` 为空；citation excerpt 不是完整原文。

## 预览与提交

`preview(state, request)` 直接运行 `apply` 的同一候选编制、保护检查与最终校验，然后丢弃候选 state：

```python
from authoring import preview, apply

review = preview(state, request)
# 审阅 review["changes"]、review["operations"] 和 review["warnings"]
state, receipt = apply(state, request)
```

```sh
scripts/travel-handbook preview trip-state.json request.json
```

成功预览返回原 revision、`proposed_revision`、每个 operation 的 method/effect、warnings，以及领域 `changes`：既有对象给稳定 handle、changed_fields 和 before/after；新对象只给批内 alias（若有）、type 和不含 ID 的 key_fields。warnings 中的对象引用使用同一安全投影：既有对象给稳定 handle，新对象只给不可续写的 type/alias。它不返回候选 handle、候选领域 ID、来源签名密钥或可用于 `source.*.resolve` 的冲突票据。

preview 不修改传入 state、revision、receipts、`source_imports` 或 `issue_resolutions`，也不消耗 request_id。同一 workspace/revision 随后提交相同 request，会产生预览所用的同一领域变化；若中间发生写入，原 expected_revision 会按正常规则报 `REVISION_CONFLICT`。对已成功 request 的 preview 返回 `replayed=true`、`no_new_change=true` 和空 changes，不转发历史创建 handle。

失败仍抛 `AuthoringError`，保留 apply 的 code、message、op_index、parameter 和最终校验 errors/path。来源冲突只给带 `preview_only=true` 的解释性 `conflict_summary`；签名和本批临时身份已移除，不能传给 resolve。要裁决冲突，必须实际提交 refresh 取得当前工作区签发的完整 conflict。

preview 只回答“这一个明确批次经过现有有限校验后会怎样”。它不证明来源齐全、事实正确、路线可行或完整攻略已经覆盖。
