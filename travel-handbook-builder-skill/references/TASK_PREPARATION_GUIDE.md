# 基础准备待办、清单与重新打开

本指南描述基础准备部分可调用的 `task.add`、`task.amend`、`task.complete` 和 `task.reopen`。它只保存调用方明确给出的准备动作、依赖和完成事实，不从标题或说明推断购买、负责人、付款或供应方确认。

稳定数据契约 1.0 支持 category、preparation、depends_on、checklist 和 `task.reopen`。重新打开已完成的 Task 会保留不可变完成历史。

## 新建准备待办

`targets` 是非空引用列表，只接受 Trip、Item、Stay 或 Stay 内的 Unit handle；1.0 另接受已有 Issue handle。Issue 用于来源能明确命名问题对象、但不能定位到执行片段的具体核实事项，调用见[Issue指南](ISSUE_GUIDE.md)。不直接接受 Place、VehicleUse、Journey 或 Leg。针对某个已选交通安排的待办可引用其所属 Item；覆盖整趟旅行的准备可引用 Trip。按来源的真实作用范围选择目标，不为了通过类型检查扩大或缩小事实范围；已有 Task 也不会自动迁移目标。标题和 notes 保留车辆、部件等原文细节。读取返回的字符串 handle 写入时使用 `{"handle": "..."}`。

```python
{"method": "task.add", "as": "buy", "args": {
    "title": "购买防蚊用品", "action": "purchase", "targets": [trip],
    "category": "health_supplies",
    "preparation": {"item_label": "防蚊液", "quantity": 2, "unit": "瓶"}
}}
{"method": "task.add", "as": "pack", "args": {
    "title": "把防蚊用品装包", "action": "pack", "targets": [trip],
    "category": "health_supplies",
    "preparation": {"item_label": "防蚊液"},
    "depends_on": [{"local": "buy"}],
    "checklist": [{"key": "carry-on", "title": "放入随身行李"}]
}}
```

`category` 只接受模型已有的 `documents`、`clothing`、`health_supplies`、`connectivity`、`equipment`、`booking`、`verification`、`other`。省略不会自动填 `other`。

`preparation.item_label` 必填且非空。quantity 与 unit 必须同时出现，quantity 大于 0；两者都省略表示数量没有记录，不默认 0 或 1。购买和装包是两个动作，只有原材料明确表达两者及依赖时才创建两个 Task。

`depends_on` 只接受 Task handle，按首次出现去重。不存在引用、自依赖和直接或间接循环会使整批失败。依赖省略表示没有记录，不证明现实中相互独立。

`checklist` 是非空的 `{key,title}` 列表，每项初态 open。key 只为本动作回执和批内引用命名，不导出到领域包；清单项的领域记录只有 id、title、status。

## 清单句柄与受限修改

新建回执的 `operations[i].parts.checklist[key]` 是可跨请求保存的工作区 handle。同批后续动作可用 alias part：

```python
{"method": "task.amend", "args": {
    "target": {"local": "pack"},
    "checklist_edits": [{
        "op": "set_status",
        "target": {"local": "pack", "part": {"kind": "checklist", "key": "carry-on"}},
        "status": "done"
    }]
}}
```

以后从回执或 `read` 取得该 handle，可将 status 设为 `open`、`done` 或 `not_needed`。标题纠正使用 rename，只改 title 并保留清单 id、handle、status 和顺序：

```python
{"method": "task.amend", "args": {
    "target": task,
    "checklist_edits": [{
        "op": "rename", "target": checklist_item,
        "title": "确认护照有效且在随身包内"
    }]
}}
```

目标必须属于指定 Task；空标题、额外字段和跨 Task handle 会原子拒绝。done Task 必须先 `task.reopen`，改名只影响当前清单，不改写 `completion_history.checklist_snapshot`。成功 request_id 重放不会重复修改。

新增项只用：

```python
{"method": "task.amend", "args": {
    "target": task,
    "checklist_edits": [{"op": "add", "key": "ticket", "title": "确认车票"}]
}}
```

当前不删除、重排或整表覆盖清单项。语义错误且不应改名复用的项标为 not_needed，再新增正确项。checklist handle 只在编制工作区内解析；它不是 AnyRef，不能写入导出的通用引用字段。

`task.amend.set` 可整体替换 category、preparation、depends_on，也保留 title、notes、due、window；`clear` 可删除 category、preparation、depends_on、notes、due、window。action、targets、status、completion 和 completion_history 均不能通过 amend 写入。1.0 已增加 assignees/beneficiaries 的 add/amend 快照入口，人数不能冒充负责人；handle形式、all/group展开和历史保护见[成员指南](PARTY_GUIDE.md)。

## 完成、依赖提示与重开

只要仍有 open 清单项，`task.complete` 就以 `TASK_CHECKLIST_OPEN` 原子拒绝。done 与 not_needed 清单项均视为已处理。

若依赖 Task 仍为 open，调用方明确提交的完成事实仍会保存；回执、check 与 export validation 同时返回 `TASK_DEPENDENCY_OPEN`，列出未完成的直接依赖。该提示不会完成上游、恢复下游为 open 或传播状态。依赖已 done 或 not_needed 时没有这项提示。

done Task 不能修改 title、category、preparation、depends_on、checklist、assignees 或 beneficiaries，必须先重开。action/targets 没有修改入口；notes、due、window 仍可按既有白名单修改。

```python
{"method": "task.reopen", "args": {
    "target": task,
    "reason": "数量需要调整",
    "reopened_at": {"local": "2026-10-04T12:00:00", "timezone": "Asia/Tokyo"}
}}
```

`task.reopen` 只接受 1.0 的 done Task 和非空 reason。reopened_at 可省略；省略时不会填系统当前时间。重开把原 completion、关键任务定义和当时 checklist 深拷贝追加到 completion_history，保留当前 checklist 和 Task id，删除 current completion，再把状态设为 open。之后修改当前字段不会改写旧快照；再次 complete→reopen 会按顺序再追加一条历史。成功 request_id 重放不重复追加。

Task 层的 not_needed 仍没有本批公共转换方法。Wi-Fi obtain/return 可在事实明确时建两个 Trip 目标 Task 并记录依赖；这不会创建 Reservation、Coverage、Cost、Payment 或服务使用记录。
