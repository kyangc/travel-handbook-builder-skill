# 默认工作流：创建、续改、查看

这是普通文件式 CLI 的最短路径。先为当前 shell 选一个入口；发行包使用第一行，仓库内从根目录使用第二行：

```sh
CLI() { "/absolute/path/to/travel-handbook-builder-skill/scripts/travel-handbook" "$@"; }
# 仓库内改为：CLI() { python3 -m authoring "$@"; }
```

先读本次材料，沿用用户已作的旅行选择；缺少可选图片、时刻、价格或凭证不阻塞首版。地点内容和事实采用需要研究时读[内容指南](CONTENT_COLLECTION_GUIDE.md)，具体方法从[公开索引](README.md)选对应专业指南。只在需要程序内处理 state 时读[Python 备选](PYTHON_OPTIONAL_GUIDE.md)。

## 首次创建

`STATE` 是尚不存在的新文件，`ROOT` 是尚不存在或为空的新目录；两者均放在 Skill 安装目录外。先创建空 state 并读取真实 revision：

```sh
CLI create "/absolute/output/trip-state.json" --title "本次旅行名称"
CLI read "/absolute/output/trip-state.json"
```

根据材料保存自己的 `/absolute/output/create-request.json`。以下仅演示一次已选到访；日期、时区、地点和标题都必须来自真实材料，不能照抄示例。`expected_revision` 取刚才 read 的值，批内引用用 `{"local": "..."}`，后续请求则用公开 read 得到的 `{"handle": "..."}`，不能猜 handle 或领域 ID。

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

先审阅 dry-run 的变化和 warnings；认可后提交**同一份** request，保存它和 receipt，再校验完整 state。失败批次不会半提交，检查结构化错误后有意修订；首次 `apply` 响应不明时，用原 request ID 和完全相同载荷重放。

```sh
CLI preview "/absolute/output/trip-state.json" "/absolute/output/create-request.json"
CLI apply "/absolute/output/trip-state.json" "/absolute/output/create-request.json" > "/absolute/output/create-receipt.json"
CLI check "/absolute/output/trip-state.json"
```

确认 receipt 已提交且 `check.valid=true`，然后在**第一次打开网页前**将完整 state 初始化到最终受管理 ROOT。以后只读写此 ROOT；旧 STATE 是初始化快照，不能再对 managed 文件普通 `apply`。初始化响应不明时先 `client status ROOT`，不要覆盖非空目录。

```sh
CLI client init "/absolute/output/managed handbook" --state "/absolute/output/trip-state.json"
```

## 在同一 ROOT 续改

先用 `client read ROOT` 取得当前 revision、handles 和能力；改 Place 时用 `client context ROOT --handle PLACE_HANDLE`（仅有名称时用 `--name NAME` 并核对候选），它同时返回关联说明与来源。只补一项有来源且不覆盖旧值的 Place 内容可读[managed 指南](CLIENT_GUIDE.md)使用 `prepare-place`。纠错、修改开放规则、调整安排和其他公开方法按匹配的专业指南构造原格式 request，用 `prepare-request`。更新复合字段前读回完整旧值并带回无关子字段；不要为改一个字段重建整份行程。来源适用期、例外和关键未知保持明确；公开计划不能冒充已出票或已预订。

下面是请求形状示意，实际 revision、目标和内容须来自当前 read 与本次授权。`trip.update` 不需要 target；其他对象遵循各自公开方法合同。

```json
{"request_id":"example-summary-v1","expected_revision":1,
 "operations":[{"method":"trip.update","args":{"set":{"summary":"根据本次材料写成的旅行简介"}}}]}
```

```sh
CLI client read "/absolute/output/managed handbook" --type trip
CLI client prepare-request "/absolute/output/managed handbook" "/absolute/output/reviewed-request.json"
CLI client commit "/absolute/output/managed handbook" "OPERATION_ID_FROM_PREPARE"
CLI client read "/absolute/output/managed handbook" --type trip
CLI client check "/absolute/output/managed handbook"
```

审阅 prepare 返回的 preview 后才 commit；提交状态不确定时只重试**同一 operation ID**。改动请求时从当前 read 取 revision 并换新 request ID。读回本次目标及必要相邻对象；`client check` 是当前完整 state 的报告，另核 `publish_status` 与 canonical revision。`check.valid` 不证明事实完整或网页已刷新。更多幂等和失败恢复见[managed 指南](CLIENT_GUIDE.md)。

## 浏览器预览与交付

发行包对 managed ROOT 执行 `scripts/preview-service start ROOT --port 0`，保存返回 URL；续作仍用同一 ROOT，刷新原 URL。仓库开发时先构建发行包；具体启动和地图设置见[浏览器预览指南](BROWSER_PREVIEW_GUIDE.md)。作者写入的 `preview` 与浏览器页面是两层证据：服务就绪或 `/api/handbook` 有数据不证明页面已经渲染。只有实际查看页面后才声称文字、图片或交互可见；未目视时如实说明数据和服务核验范围。不要把本地预览说成公开发布。

旧自管 state、package-only 导入、export report 和恢复按[恢复指南](RECOVERY_READ_PREVIEW_GUIDE.md)处理；新 managed 工作无需另建第二份 journal。交付面向旅客的变化、主要来源与适用条件、重要未知、可用预览 URL 和后续续作 ROOT。请求 ID、raw handle、revision 留在内部记录；审计或交接需要时再提供。结构有效、导出成功或网页可读仍不证明行程可行、预订有效或可公开发布。
