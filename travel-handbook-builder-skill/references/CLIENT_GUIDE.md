# 受管理攻略续作客户端

`authoring.client.ManagedHandbook` 接管同一新目录中的完整 state、request journal、preview/commit 和稳定 canonical 发布。单 Place 单字段非覆盖补充使用 `context`/`prepare-place`；同源多字段或多 Place 补充优先使用 `prepare-request`，批量来源与 Note 去重见[内容指南](CONTENT_COLLECTION_GUIDE.md#把资料写回正确对象)。其他当前公开写方法使用只读 `client read` 后，按既有专业指南构造公开 authoring request，再交给 `prepare-request`。这不是新的领域编辑器：客户端不联网、不选择事实、不包装各个底层方法。`read.capabilities.write_methods` 才是当下可调用方法清单。

## 快速开始

新攻略先用公开 `create`/`preview`/`apply`（或同名 Python 函数）完成**首次语义请求**；`check` 有效后，在**第一次打开网页前**用所得完整 state 初始化最终新目录。浏览器从一开始就指向该目录的 `private-handbook.json`。只能在不存在或空目录中初始化；没有 `adopt`、`attach` 或 `force`，不能接管已经在网页使用的外部 canonical。完整 state 保留 receipts 和来源快照等作者上下文；初始化输入是快照，之后只能从 managed 读取/提交，不再回写它：

```sh
scripts/travel-handbook client init \
  "/absolute/output/managed handbook" \
  --state "/absolute/input/trip-state.json"

scripts/travel-handbook client context \
  "/absolute/output/managed handbook" \
  --name "北港声学阅览室"

scripts/travel-handbook client read \
  "/absolute/output/managed handbook" \
  --type place --limit 20

scripts/travel-handbook client check \
  "/absolute/output/managed handbook"
```

`context` 支持 `--name NAME` 或 `--handle HANDLE`；即使已知 Place handle，补充或纠错前也可用它取得该 Place、`related_guide_notes`、`related_items`（含当前 Day/退役归属）、`related_issues`、`sources` 和当前 revision。它会追完各类型分页，只返回与此 Place 直接关联的对象；名称重复时返回候选而不猜测第一个。`association_review.needed` 提示这些对象可能含随安排变化的文字判断，**不是**自动判定文字已过时；Item 撤下或改期后，调用方用这份有界关联集合复核 Note 与 Issue，按事实需要显式更新或保留，不自动改写、解决或删除。该集合不是全工作区反向依赖图，也不扫描自由文字寻找暗含关联。窄补充须用其 Place handle 和 revision。其他对象仍用 `client read`，它直接复用公开 `read` 的 `--day`、`--type`、`--handle`、`--limit`、`--cursor`、`--include-source-text`，返回当前 revision、handles、分页与 live capabilities；Source 原文需要显式 Source handle。不要读或直接改管理目录中的 state、journal、canonical。

`--type` 使用模型对象名，不是写方法名：例如 `service.record` 创建的对象用 `client read ROOT --type transport_service`，不是 `--type service`；Trip、Item、Task 分别用 `trip`、`item`、`task`。完整可读类型以当前 `read` 选择器和 live capabilities 为准。

`--day` 要 **Day handle**，不能直接传日期。先 `client read ROOT --type day --limit 50` 并追完分页，按返回的 `record.date` 选择其 `handle`，再执行 `client read ROOT --day DAY_HANDLE`。工具不把日期／名称猜成对象。`client context` 只服务 Place，参数是 `--handle PLACE_HANDLE` 或 `--name PLACE_NAME`，没有 `--target`；Task 等其他对象用 `client read ROOT --handle OBJECT_HANDLE`。错误仍为非零退出；错误中的 `recovery.argv` 可接在原 CLI 可执行入口后运行，返回帮助不等于已经正确选择对象。

需要完整能力时执行 `client read ROOT --type trip --limit 1`（默认包含 capabilities）。后续局部读取可显式加 `--omit-capabilities`，例如 `client read ROOT --type place --limit 20 --omit-capabilities > places-page.json`；Python 是 `include_capabilities=False`。它只省略顶层 `capabilities`（含重复的 coordinate_inputs），其余对象、revision、关联 handles、import report、显式 Source 全文及分页逐值保留，不截断、不缩写。默认输出不变；无需另建能力命令。每页继续按原过滤器和 `pagination.next_cursor` 读取；中途可切换是否省略能力，游标范围不变。`--report map-coverage` 本来不重复能力，加入此选项不会改变完整汇总或分页。stdout 始终为完整 JSON，可逐页重定向落盘；不要用输出长度代替是否追完分页。

`client check ROOT`（Python：`ManagedHandbook.open(ROOT).check()`）只读返回 `state_revision`、`canonical_revision`、`publish_status` 和 `report`。`report` 是同一当前完整 state 的公开 `check(state)` 完整报告，包括 `availability_assessments`；没有选择、分页或自动发布。`publish_status=stale` 表示 canonical/网页仍落后，即使 `report.valid=true`，本命令仍以校验成功的退出码 0 返回；调用方须单独核对发布状态，不能把当前 state 的诊断说成旧网页已展示的内容。无效目录或内部 state/canonical 沿用结构化错误与非零退出。读取不会改动 state、canonical、report 或 journal；package-only 的当前导入 state 可诊断，但缺失的旧作者元数据不会恢复。

地图输入覆盖可用 `client read ROOT --report map-coverage`，可加 `--day DAY_HANDLE`、`--limit` 和 `--cursor`。它按日给地点、Route Stop、Recommendation、AccessPoint 与路径绑定的当前 handle 和缺口原因，区分不同地点数与日期关联次数，不写正文、不加 check 门禁。完整分页、坐标精度、入口／路径未知及投影和实际网页的边界见[地图覆盖报告](MAP_COVERAGE_GUIDE.md)。

保存一个窄补充 intent：

```json
{
  "request_id": "north-condition-v1",
  "expected_revision": 1,
  "target": {"handle": "h-place-from-context"},
  "patch": {
    "path": "content.cautions",
    "op": "append_unique",
    "value": "适用期 2031-11-01 至 2032-03-31；社区录音活动期间可能临时关闭；当日需复核。"
  },
  "source": {
    "new": {
      "kind": "synthetic_fixture",
      "title": "明确由调用方提供的来源标题",
      "url": "https://example.invalid/source",
      "notes": "适用期与复核条件由调用方完整记录。"
    }
  },
  "guide_note": {
    "title": "到访条件来源",
    "text": "到访条件依据所引资料。"
  }
}
```

GuideNote 只补必要出处或尚未在 Place 表达的有据说明，不复述已写入 `cautions` 等字段的适用期、临时关闭和复核条件；不要把“这次改了什么／没改什么”等操作范围或当前日程复制进地点说明。操作范围写在答复或工作记录中，实际安排仍从 Day/Item 读取。

```sh
scripts/travel-handbook client prepare-place \
  "/absolute/output/managed handbook" \
  "/absolute/input/place-enrichment.json"

# 人或 Agent 审阅 preview 后，只传回不透明 operation ID。
scripts/travel-handbook client commit \
  "/absolute/output/managed handbook" \
  op-opaque-id

scripts/travel-handbook client status \
  "/absolute/output/managed handbook"
```

managed 网页预览由发行包的持久启动器提供，首次启动后保存返回的 `url`；续作时同一 ROOT 再次 `start` 会复用该 URL：

```sh
scripts/preview-service start "/absolute/output/managed handbook" --port 0
scripts/preview-service status "/absolute/output/managed handbook"
```

提交成功后刷新原页即可；不要在答复前停服。明确需要停服时执行 `scripts/preview-service stop "/absolute/output/managed handbook"`。独立 canonical 的前台预览仍用 `scripts/preview-handbook CANONICAL`。

## 窄补充与专业请求

| op | path |
|---|---|
| `set_if_absent` | `address`、`timezone`、`content.summary` |
| `append_unique` | `content.highlights`、`content.visit_advice`、`content.cautions` |

每次只能一个 patch。`source` 必须是一个新 `Source`，或 context 中已经与该 Place 相关的 `{"existing":{"handle":"..."}}`。有新字段写入时，客户端通常新增一个普通 citation GuideNote；若同一 Place 已有**完全相同**标题、单段文字、同一现有 Source 的普通引用，且仅关联该 Place，则复用该 Note，不另建副本。新 Source（即使元数据同文）、不同引用/正文或额外关联都不合并；不会覆盖人工改动，也不生成 exact citation。调用方负责来源类型、事实采用、日期、适用期、例外和复核措辞；未知字段继续省略。

窄入口对纠正、覆盖、删除、availability、旧 GuideNote 更新和“文本已存在但只想挂新证据”返回结构化 `unsupported`（CLI 非零退出）。`evidence_only` 表示新 Source/GuideNote **没有**写入；只有原 patch、existing Source 和同文 GuideNote/引用全部已存在才返回 `no_change`。纠正 Place 时仍可先用 `context` 找关联说明与出处；随后按返回的专业指南与当前 context/read 构造**原公开格式** request。新事实使现行说明失准时，针对受影响的旧 GuideNote 用 `guide.note.update`，而不是只加一条相矛盾的新说明。交给同一管理目录的 `client prepare-request`，不要回到初始化前的旧 state，也不要绕过客户端执行普通 `apply` 或直接改 managed 文件。

例如现有 `place.hours.update` 与非 Place 的 `plan.move` 都仍按各自专业指南填写 `operations`；客户端不替 Agent 判定事实、开放规则或安排。一个专业 request 仍只有公开的三个顶层字段：

```json
{
  "request_id": "reviewed-hours-v1",
  "expected_revision": 1,
  "operations": [{"method": "place.hours.update", "args": {
    "target": {"handle": "h-place-from-client-read"},
    "scope": "venue",
    "timezone": "Europe/Copenhagen",
    "weekly": [{"days": ["mon"], "closed": true}]
  }}]
}
```

```sh
scripts/travel-handbook client prepare-request \
  "/absolute/output/managed handbook" \
  "/absolute/input/reviewed-request.json"
# 审阅返回的 preview，再用上文同一条 client commit ROOT OPERATION_ID 提交。
```

专业入口只传输 live `write_methods` 中可由公开 `preview/apply` 执行的 request；不会为不支持的方法补语义，也不能恢复 package-only 缺失的旧精确引用/快照。专业 request 的 preview 错误、`op_index`、origin 要求、保护和冲突来自原引擎。revision 冲突时重新 `client read`，有意修订并用新 request ID；不可让客户端自动套用旧意图。

## 幂等、恢复与发布

- 同 request ID + 完全相同 intent 找回同一 operation；同 ID + 不同 intent 返回 `REQUEST_ID_REUSED`，其中 `recovery.action=new_request_id_for_changed_intent` 指示更正后的**新意图**另用新 ID，原 operation 的审计记录不改写。managed preview 失败时保留原 `code`/`op_index`，另返回 `recovery.action=correct_intent_with_new_request_id`；完全相同的原意图可沿用原 ID 重试。普通非 managed `preview` 不附加这层恢复信息。
- 两种恢复不要混用：更改标题、目标或其他请求载荷是**新意图**，读取当前 revision 并换新 request ID 后重新 prepare；同一提交的响应不明或发布失败是**同一意图**，只重试原 operation ID，不新造请求。
- 窄/专业入口共用 request ID 命名空间；已在输入 full state 成功提交、但不在 managed journal 的旧 ID 不会伪装成新 operation。专业入口仍须保留本次原 request 供失败诊断；不能从 receipt 反推请求。
- prepare 先保存 intent 和精确 request bytes，再 preview。commit 只接收 operation ID，且每次重算 request hash。
- 响应丢失时重提同 operation ID。底层 receipt 会恢复精确重放，不重复 Place 值、Source 或 GuideNote。
- 旧 operation 在新 operation 之后重试时，只能发布当前最新 state，不降级 state/canonical。结果分别报告 `operation_revision`、`state_revision` 和 `canonical_revision`。
- 若 state 写入或 operation sidecar 写入在目标替换后报告存储错误，客户端会重读 state 并用同一请求核对底层 receipt。确认已提交时返回 `committed=true`、实际 state/canonical revision 和非零 CLI 状态；无法确认时返回 `committed=null`、`commit_status="unknown"`。两种结果都只允许重试**同一 operation ID**，不要创建新 request ID。
- 若领域 state 已提交但导出失败，CLI 非零退出；结果为 `committed=true`、`publish_status="failed"`。旧 canonical/网页仍可用，重试同 operation 会发布当前 state。
- 已确认提交的结果中，顶层 `warnings` 原样呈现本次 `receipt.warnings`，包括 canonical 发布失败但提交已确认的情形。它不是重新运行 `check` 的警告清单；`client read` 也不冒充当前完整 `check` 报告。需要当前诊断时单独调用 `client check ROOT`，不要从历史 receipt 推断或读取私有 state。`committed=null` 时不能凭空声称已有 receipt 或 warning。

## Full state 与 package-only

`--state` 是 `full_state`；`--package` 是 `package_only`。package-only 会产生新 workspace 和新 handles，不能恢复旧 receipts、source snapshots/bindings 或其他作者元数据。导入后必须重新 context；只能安全追加新补充，不能声称恢复旧请求的幂等历史。`status` 会原样返回 `import_report.unavailable_authoring_metadata`。

## 完整性边界

客户端拒绝根目录/固定路径 symlink、marker/workspace 不一致和 revision 异常，并校验已持久化 request 的 SHA-256。这是单 writer 管理合同，不是通用防篡改系统：它**不能检测同 revision 的所有外部改写**。不要绕过客户端编辑 `trip-state.json`、operation 文件或 canonical。
