# 基础准备待办、清单与重新打开

本指南描述基础准备部分可调用的 `task.add`、`task.amend`、`task.complete`、`task.reopen` 和 `task.retire`。它只保存调用方明确给出的准备动作、依赖、完成与撤下事实，不从标题或说明推断购买、负责人、付款或供应方确认。

稳定数据契约 1.0 支持 category、preparation、depends_on、checklist 和 `task.reopen`。重新打开已完成的 Task 会保留不可变完成历史。

## 先判断是不是行前待办

Task 是需要独立处理、处理后可明确完成的行动，不是对现场安排的另一份说明。编制行程时，主动检查已有证据中是否有适用的证件、通信、支付、行李、票务/预订等行前准备；只记录确有依据、对本次旅行有用的动作，不套固定清单，也不因为可选字段缺失而阻断首版。用户尚未选择的方案和未确认的支付、预订、出票不能标成完成。

标题只写简短明确的动作；截止、适用条件、凭证和需核实的细节放 `notes`，有可靠日期依据才写 `due`/`window`。`action` 表示要做的动作，`category` 表示准备主题，分别按实际语义选择，不从标题自动推断或为填字段一律写 `other`。例如“核实护照有效期”可用 `action=verify, category=documents`；“激活已选 eSIM”可用 `activate, connectivity`；“购买已决定的门票”可用 `purchase, booking`。仅知道要决定是否购票时，不能先写成 `purchase` 或声称已有订单；若已经决定购买，标题就写购买，别把“决定时间/方式”混入同一购买动作。需要先作选择时，先保留为调用方待决事项，选择明确后再建对应 Task。

反例：“乘车时打开电子票”只是现场使用注意，写在该次交通 Item/Leg 的说明，不建行前 Task；若确有提前激活或购票截止，另建对应 Task 并记录期限依据。“建议提前订座”不等于制度强制，只有用户已选订座才建对应行动；真实强制条件须有适用依据。天气复核按临行需要保留，未知日期不编造截止时间。

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

`category` 只接受模型已有的 `documents`、`clothing`、`health_supplies`、`connectivity`、`equipment`、`booking`、`verification`、`other`。省略不会自动填 `other`；不适用某一主题时可省略，而不是为每条 Task 强制分类。

`preparation.item_label` 必填且非空。quantity 与 unit 必须同时出现，quantity 大于 0；两者都省略表示数量没有记录，不默认 0 或 1。装包先核对已有物品，缺少且已决定添置才建采购；装备建议不一律变购物清单。上例仅适用于材料明确要求购买、装包及两者依赖的情况。

`depends_on` 只接受 Task handle，按首次出现去重。不存在引用、自依赖和直接或间接循环会使整批失败。依赖省略表示没有记录，不证明现实中相互独立。

`checklist` 是非空的 `{key,title}` 列表，每项初态 open。key 只为本动作回执和批内引用命名，不导出到领域包；清单项的领域记录只有 id、title、status。汇报待办进度时说明统计是否含父任务与子清单：例如一个装包 Task 下的三项物品不等于四个独立决策，界面行数不能直接当作决策负担或计算错误的证据。

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

`task.amend.set` 可整体替换 action、category、preparation、depends_on、targets，也保留 title、notes、due、window；`clear` 可删除 category、preparation、depends_on、notes、due、window。`set.action` 必须是模型已有的 `pack`、`obtain`、`purchase`、`install`、`activate`、`verify`、`reserve`、`return`、`cancel`、`pay`、`other`，不能清除。`set.targets` 必须是非空的完整目标 handle 列表，沿用 `task.add` 的目标类型；替换 Item 必须为 current。只提交 `targets`，不可直接写 `target_refs`、清空目标或按旧标题猜测新安排。status、completion 和 completion_history 均不能通过 amend 写入。1.0 已增加 assignees/beneficiaries 的 add/amend 快照入口，人数不能冒充负责人；handle形式、all/group展开和历史保护见[成员指南](PARTY_GUIDE.md)。

若已选车票的开放 Task 曾误录为 `verify`，先读回事实，再原位纠正，不另建一条丢失身份的 Task：

```python
{"method": "task.amend", "args": {
    "target": existing_task,
    "set": {"title": "购买已选车票", "action": "purchase"}
}}
```

此修订不表示车票已经购买、出票或付款；仍须保留真实状态与凭证。若 Task 已 done，先以真实理由 `task.reopen`，旧 `action`、标题和原完成记录进入不可变历史，然后只修当前定义。

早期普通交通 Item 已撤下、改为正式 Journey 时，先用 `client read` 确认新 Journey 所属的 **current transport Item**，再显式改挂已有 Task，不直接用 Journey/Leg handle：

```python
{"method": "task.amend", "args": {
    "target": existing_task, "set": {"targets": [current_journey_item]}
}}
```

旧 Item 仍保留退役历史；Task id、状态和无关字段不变。若 Task 已 done，先以真实理由 `task.reopen`，其原完成定义与目标进入不可变历史，再改当前目标；不可直接改写已完成 Task，也不会自动判定旧票据对新 Journey 仍适用。

## 完成、依赖提示与重开

用户说“已完成”时，先读 Task 定义与清单，只完成明确确认的范围。出票不等于已值机；网络已备不等于电子票已登录。有清单时用 `task.amend.checklist_edits` 只更新对应项；无对应项则按已知事实原位厘清任务范围并保留未完成动作，不为关闭整项而缩掉范围。整项确认后才用 `task.complete`，其必填 `record_note` 只记这次确认的完成事实，不猜凭证、完成时间或供应方核验。

只要仍有 open 清单项，`task.complete` 就以 `TASK_CHECKLIST_OPEN` 原子拒绝。done 与 not_needed 清单项均视为已处理。

若依赖 Task 仍为 open，调用方明确提交的完成事实仍会保存；回执、check 与 export validation 同时返回 `TASK_DEPENDENCY_OPEN`，列出未完成的直接依赖。该提示不会完成上游、恢复下游为 open 或传播状态。依赖已 done 或 not_needed 时没有这项提示。

done Task 不能修改 title、action、targets、category、preparation、depends_on、checklist、assignees 或 beneficiaries，必须先重开；notes、due、window 仍可按既有白名单修改。

```python
{"method": "task.reopen", "args": {
    "target": task,
    "reason": "数量需要调整",
    "reopened_at": {"local": "2026-10-04T12:00:00", "timezone": "Asia/Tokyo"}
}}
```

`task.reopen` 只接受 1.0 的 done Task 和非空 reason。reopened_at 可省略；省略时不会填系统当前时间。重开把原 completion、关键任务定义和当时 checklist 深拷贝追加到 completion_history，保留当前 checklist 和 Task id，删除 current completion，再把状态设为 open。之后修改当前字段不会改写旧快照；再次 complete→reopen 会按顺序再追加一条历史。成功 request_id 重放不重复追加。

## 明确撤下不再需要的 Task

仅在明确知道**整个当前 Task** 不再需要时，使用原 Task handle 调用。例：用户已决定当天现场购票，先用 `plan.update.set.notes` 等对应公开入口保留当天说明及必要条件，再撤下原“提前购票”Task，理由写“改为当天现场办理，无需行前购买”，不能标 done 或声称已购。只有“现场可买”的资料还不等于用户选择；部分清单不再需要时只改该项为 `not_needed`，保留其余行动。

```python
{"method": "task.retire", "args": {
    "target": task,
    "reason": "行程调整后，这项核验不再需要"
}}
```

此 1.0 方法只接受 `status=open` 和非空 reason，原位写入 `status=not_needed` 与 `retirement.reason`，保留 Task ID、target_refs、depends_on、清单、说明及已有 `completion_history`；不填系统时间、不制造 completion，也不删除对象。当前 `done` Task 不可直接撤下；若事实需要改为不再需要，先显式 `task.reopen`，让旧 completion 与定义进入历史，再调用 `task.retire`。已撤下 Task 不能用 `task.complete`、`task.amend` 或 `task.reopen` 重写，重复新请求也会拒绝；同一成功 request_id 的重放仍由公开事务去重。旧数据中的 `status=not_needed` 即使没有 `retirement` 仍合法。

此转换不自动完成、撤下或改挂其他 Task；原 target_refs 和下游 depends_on 仍指向相同身份。现有依赖检查把 `not_needed` 视为已处理，因此依赖它的下游 Task 不再出现 `TASK_DEPENDENCY_OPEN` 提示，但下游自己的状态和事实完全不变。回执的 `parts.review_refs` 列出直接依赖本 Task 的 Task、直接关联它的 GuideNote、以它为 `task_ref` 的 Issue，以及直接指向它的 Claim，供适配器核对；这些引用不会自动变更。待办投影只展示仍有当前待办行的 Task，`not_needed` 退出当前列表，保留的对象仍可按 ID 读取。Wi-Fi obtain/return 可在事实明确时建两个 Trip 目标 Task 并记录依赖；这不会创建 Reservation、Coverage、Cost、Payment 或服务使用记录。
