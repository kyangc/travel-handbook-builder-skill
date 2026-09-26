# 默认工作流：创建、补充、调整、查看结果

本指南只覆盖最常见的文件式 CLI 路径。新攻略在第一次打开网页前交给受管理客户端，后续从同一目录补充、调整和发布；已在网页使用的外部 canonical 尚不能接入，不要擅自换路径。事实采用和旅行选择仍由材料、用户与 Agent 判断，runtime 不替他们选地点或路线。先完成当前请求，再按需读取专业指南。公开能力以 `read` 返回的 `capabilities` 为准，未出现的方法或 Schema 字段不能调用。仅需程序内处理 state 时读[Python 备选](PYTHON_OPTIONAL_GUIDE.md)，不要为普通工作预读它。

## 共同约定

每个新请求使用当前 read 的 revision。批内前序对象用 `{"local": "alias"}`，后续请求用 read 或 receipt 返回的 `{"handle": "..."}`；不要用领域 ID 或 preview 的诊断性引用当正式 handle。首次创建先用公开 `preview` 审阅，再把**同一 request** 交给 `apply`；进入 managed 后只用 `client read`/`prepare-*`/`commit`，不对其内部文件普通 `apply`。

首次创建仍需保留实际发出的语义 request 与 receipt；完整 state 的续作和后续 request journal 由 managed 保存。receipt 或从 read 反推的 payload 不能替代原 request。失败批次不半提交：看结构化错误后有意修订。首次普通 `apply` 响应不明，用原 request ID/原载荷重放；managed 提交状态不确定时只重试同一 operation ID，不新造 request ID。

## 创建：默认文件式 CLI

新攻略按 `create` → `trip.define` 开始。Trip 和 Day 的日期、时区须来自材料；Place 只要求 name，但一串名字不等于可阅读的内容已编制完成。编制已选地点内容和到访 Item 前，先读发行包的 [内容指南](CONTENT_COLLECTION_GUIDE.md)：用已有材料，再按需做适度公开研究；以 `Place.content.summary` 写清地点身份与主要吸引力，只在不重复时另补看点，实用条件按其语义记录；不要为每个地点套同一模板或替用户新增选择。主动核对已安排地点与关键交通端点的可靠坐标，让有依据的地图可用；地图搜索链接不等于坐标，找不到时保留未知。已选但时间未知的普通安排可不写 timing；缺图片、开放时间、时长、地址、坐标、价格、预订或票据不阻塞 `check` 和首次交付，首版之后仍可按反馈渐进补充。

输入 Markdown 已有地点简介、出处、已选交通端点/方式或已采用安排的草案时刻时，先判断身份、来源和适用性，再把可采用的事实写入对应公开字段，不统统留在 notes 或写成 unknown；日期与时区有据的草案时刻用[时间指南](TIME_PLAN_GUIDE.md)支持的 `estimated`，而非冒充固定或忽略，未选备选仍不升格为正式安排。提交后用公开 read 对照原材料核对 Place、Item 与相关 Journey/Leg 的实际字段；`check.valid` 不能证明这些事实已经采用。

材料已说明某次已选到访的理由时，创建用 `plan.add.purpose`，修订用 `plan.update.set.purpose` 承接，不只放 `notes`。`Place.content.summary/highlights` 只写可复用地点事实，不把看点标成“本次重点”；GuideNote 简述来源、适用期和限制，不重述整段 Place 内容。材料没有地址、坐标或时长等信息时，缺项写在 Agent 工作说明里，不写成旅客可见的缺口段落。

发行包先按 Skill 根目录 `README.md` 备好 Python 环境；以下 `SKILL_DIR` 换成发行包绝对路径。仓库内用项目 Python 3.12 的 `-m authoring`，参数相同。路径加引号，每一步核对退出状态与输出后再继续，**不要整段自动提交**。STATE 是新文件；ROOT 不存在或为空。

```sh
SKILL_DIR="/absolute/path/to/travel-handbook-builder-skill"
"$SKILL_DIR/scripts/travel-handbook" create "/absolute/output/trip-state.json" --title "示例一日旅行" --example
"$SKILL_DIR/scripts/travel-handbook" read "/absolute/output/trip-state.json"
```

取刚才 read 的 `revision`，再根据**本次材料**保存 `/absolute/output/create-request.json`；不能猜起始 revision 或照抄示例事实。下面仅演示 read 为 `revision: 0`，材料明确给出日期、时区、地点和所选到访的合成请求；实际资料不要默认使用 `--example`：

```json
{
  "request_id": "example-create-2027-04-06",
  "expected_revision": 0,
  "operations": [
    {"method": "trip.define", "args": {
      "start_date": "2027-04-06", "end_date": "2027-04-06",
      "default_timezone": "Asia/Tokyo"
    }},
    {"method": "day.add", "as": "day", "args": {
      "date": "2027-04-06", "timezone": "Asia/Tokyo"
    }},
    {"method": "place.add", "as": "first", "args": {
      "name": "示例地点甲", "roles": ["attraction"]
    }},
    {"method": "plan.add", "args": {
      "day": {"local": "day"}, "kind": "visit",
      "title": "到访示例地点甲", "place": {"local": "first"}
    }}
  ]
}
```

地点的 `roles` 描述场所，安排的 `kind` 描述本次活动：已选餐厅可用 `place.add` 的 `roles: ["restaurant"]`（规范为 `dining`），对应 `plan.add` 用 `kind: "meal"`；已选景点到访可用 `roles: ["attraction"]` 与 `kind: "visit"`。只录入材料明确的选择，不由分类推断用户要安排什么；完整参数与其他类型见[公开方法索引](README.md)的 `place.add`、`plan.add` 和[地点角色合同](CALLER_GUIDE.md#地点类型与资料不足)。若简介有普通出处，同批可用 `source.record` + `guide.note.add` 记录来源说明（见[GuideNote 指南](GUIDE_NOTE_GUIDE.md)）；并非每条简介都要建立高级 source-adoption binding。

```sh
"$SKILL_DIR/scripts/travel-handbook" preview "/absolute/output/trip-state.json" "/absolute/output/create-request.json"
```

先核对 `preview_only=true`、预期变化与 warnings，由 caller 判断是否符合材料；**不能自动批准预览**。认可后才提交同一份 request，并保存 receipt：

```sh
"$SKILL_DIR/scripts/travel-handbook" apply "/absolute/output/trip-state.json" "/absolute/output/create-request.json" > "/absolute/output/create-receipt.json"
"$SKILL_DIR/scripts/travel-handbook" check "/absolute/output/trip-state.json"
```

核对 apply 的退出码与 receipt 中 `committed=true`、`replayed=false`、revision、aliases；再确认 `check.valid=true`。任何一步失败都不要初始化。成功后，在**第一次打开网页前**初始化最终新目录：

```sh
"$SKILL_DIR/scripts/travel-handbook" client init "/absolute/output/managed handbook" --state "/absolute/output/trip-state.json"
```

核对 `state_revision`、`canonical_revision` 和 `publish_status=current`。网页从一开始只读 `ROOT/private-handbook.json`；旧输入 state 此后只是快照，不能再回写或对 managed 文件普通 `apply`。`client init` 响应不明时先 `client status ROOT`，不覆盖非空目录。此路径保留首次 request/receipt，无需另写创建脚本或第二份续作 journal。

## 补充与纠正

补充或纠正 Place 时先用 `client context ROOT --handle HANDLE`；只有名称时改用 `--name NAME` 并核对唯一候选，不能按列表顺序猜。context 返回当前 revision、Place、关联 GuideNotes 和 Sources，即使已知 handle 也应查看这些上下文；它不代替其他对象的 `client read` 或全图依赖检查。支持的单 Place 单字段非覆盖补充用[managed 指南](CLIENT_GUIDE.md)的 `prepare-place`；同源多字段或多 Place 补充优先用 `prepare-request`，批量来源与 Note 去重见[内容指南](CONTENT_COLLECTION_GUIDE.md#把资料写回正确对象)。纠正、availability、旧 GuideNote 和安排调整按匹配的专业指南构造**原公开 request**，用同一 managed 目录的 `prepare-request`/`commit`；若窄入口返回 `unsupported`，当前 state/canonical 不变。`prepare-request` 仍执行原领域校验、origin、冲突和保护。

```sh
"$SKILL_DIR/scripts/travel-handbook" client read "/absolute/output/managed handbook" --type place
"$SKILL_DIR/scripts/travel-handbook" client prepare-request "/absolute/output/managed handbook" "/absolute/output/reviewed-request.json"
```

`reviewed-request.json` 先根据当前 read、本次授权及对应专业指南构造，不能凭示例猜 handle、revision 或事实。审阅 prepare 返回的 `preview`、warnings、operation ID 后才分别执行：

```sh
"$SKILL_DIR/scripts/travel-handbook" client commit "/absolute/output/managed handbook" "OPERATION_ID_FROM_PREPARE"
"$SKILL_DIR/scripts/travel-handbook" client check "/absolute/output/managed handbook"
```

再 `client read` 回目标并核对授权字段及未授权对象。`client check` 返回当前完整 `report`、`state_revision`、`canonical_revision` 和 `publish_status`；营业影响见[对应指南](HOURS_IMPACT_GUIDE.md)。`report.valid=true` 不证明营业已覆盖或网页已更新；`stale` 时诊断对应当前 state，网页仍是旧 canonical。提交响应不明只重试同一 operation ID。

`place.update.set.content` 是整体替换：只补开放时间就不要改 content；要改 content 子字段时先读旧值，完整带回未获授权改变的子字段。普通网页/材料出处用 `source.record` 配合 `guide.note.add` 或 `guide.note.update`；完整原文快照和精确 citation 用[GuideNote 指南](GUIDE_NOTE_GUIDE.md#精确引用已登记原文)的 `source.register` 与 anchor，不要求来源身份/字段 binding。只有需要稳定来源身份、字段采用或同源刷新时才读[来源采用指南](SOURCE_ADOPTION_GUIDE.md)，不要把普通出处升级成同步协议。材料明确自称合成才用 `kind="synthetic_fixture"`。GuideNote 记录来源、适用期、例外与复核条件；新事实取代旧事实时，检查 context 中受影响的现行说明并按[GuideNote 指南](GUIDE_NOTE_GUIDE.md)更正，保留仍有效的出处与无关说明，或标明旧说法的历史适用范围；无需全攻略扫描。影响使用的关键条件还需在可见 `content.cautions` 等字段表达。timezone 来自材料或可靠来源，不从 Trip 猜。不要为填满前端写“暂无资料”占位；到访日期、计划时段和本次停留时长只从 Day → active Item → Place 派生，不复制到 Place。

## 调整与查看结果

调整现有安排时保留身份：`client read` 当前 Item、Day 与必要依赖 → 以当前 revision 写最小原公开请求 → `client prepare-request` 审阅 → `client commit` 同一 operation → 读回并核对网页。移动、重排、撤下、Trip/Day 日期变化或局部 Route 替换先读[安排编辑指南](ARRANGEMENT_EDIT_GUIDE.md)；普通 Visit 细化为同一次 Route 先读[路线输入指南](MOVEMENT_GUIDE.md#已有-visit-原位细化为-route)；普通未排日期 Item 见[待排指南](UNASSIGNED_ITEM_GUIDE.md)，时间约束见[时间指南](TIME_PLAN_GUIDE.md)。不要删除重建模拟移动，也不要因日程变化自动改变预订、付款、班次等现实承诺。

`plan.withdraw` 撤下安排但保留相关历史与现实承诺；`guide.note.update` 更正说明；`clear_related` 仅解除说明关联。三者都不是彻底删除。没有公开删除方法的对象（如 Source、GuideNote、Place）不能以撤下或解绑冒充删除；只承诺方法合同实际支持的效果。

`client status ROOT` 报当前 state/canonical revision、发布状态和稳定路径。若 `committed=true` 但发布失败，旧网页仍可读，只重试同一 operation ID。作者写入预览与浏览器预览不同：发行包对 managed ROOT 运行 `scripts/preview-service start "/absolute/output/managed handbook" --port 0`，保存返回的 URL；续作用同一 ROOT 再次 `start`，服务保持可访问，仓库开发环境按 `docs/frontend/portable-preview.md`。打开实际 loopback 页面，检查地点简介、当天安排与新增资料；managed commit 后刷新**同一页面**。若页面有展示缺口，先区分数据未采用、发布未更新和前端未显示，沿同一 managed ROOT 增量修正并如实报告；不要另写独立 HTML 维护第二份旅行事实。`check.valid`、export 成功或 `publish_status=current` 都不能代替网页和事实核对。

交付前按本次范围做短核对：读回改动与未改对象；检查关键事实的来源、适用期和未知；有浏览器可用时逐页目视本次应展示的标题、安排、待办和图片，若未目视就明说；另核对交通衔接、营业和预订等现实可行性，不把结构 `check.valid` 当作这几项已通过。浏览器核对是证据层级，不是所有数据-only 任务的硬性门禁，也不能为通过检查编造时间或路线。

## 按需延伸

- 程序内创建与专业补充的独立示例：[Python 备选](PYTHON_OPTIONAL_GUIDE.md)。普通 CLI 工作无需阅读。
- 尚未进入 managed 的旧调用方自管完整 state：只读[恢复/读取/预览指南](RECOVERY_READ_PREVIEW_GUIDE.md)的文件保存段；不要用于 managed ROOT。package-only 导入不能恢复旧 receipts、snapshots 或作者决策。
- Place 内容、地址或坐标：[地点指南](LOCATION_GUIDE.md)；来源说明和 citation：[GuideNote 指南](GUIDE_NOTE_GUIDE.md)；营业影响：[营业影响指南](HOURS_IMPACT_GUIDE.md)。
- 完整原文快照与精确 citation：[GuideNote 指南](GUIDE_NOTE_GUIDE.md#精确引用已登记原文)；稳定来源身份、字段采用与同源刷新：[来源采用指南](SOURCE_ADOPTION_GUIDE.md)。需保存完整原文时也按 Skill 路由读取来源决策指南。
- 行前待办：只在需要建立或调整可完成的准备动作时读[Task 准备指南](TASK_PREPARATION_GUIDE.md)；现场执行提示留在相关 Item/Leg 说明。
- 住宿、交通、路线、费用、预算、票券、成员、Issue、图片等：只读[公共指南索引](README.md)中与本次材料匹配的部分。

交付时说明实际保存的 state revision、canonical 文件、网页检查结果和重要未知。结构有效、导出成功、页面可读仍不证明事实准确、来源齐全、旅行可行、已预订或可公开发布。
