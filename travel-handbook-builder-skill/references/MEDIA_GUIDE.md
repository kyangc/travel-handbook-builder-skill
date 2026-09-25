# 图片素材与用途关系调用指南

本入口把 Agent 已经取得或生成的图片元信息写入攻略包，并显式关联 Trip 或 Place。它不搜索、下载、生成、上传或发布图片，也不从文件名、alt、caption 或来源标题推断用途、许可和表现形式。

当前版本的浏览器预览不渲染新增 Media，也不服务任意本地图片路径。`media.image.add`、`client read media` 和 `client check` 只能证明元信息、用途已记录且通过相应检查，不能证明页面已显示图片。本版已知的不渲染限制可据同版指南说明；服务/API 就绪不等于画面已渲染，未查看渲染页面时可交付记录与 URL，并说明其他页面内容尚未目视核验。

## Schema 与旧包边界

当前工作区仍使用 `schema_version: "1.0"`。Media 新增的 `representation`、`creation`、`usages` 都是可选字段；旧包中只有 id/kind/locator/alt 等原字段的 Media 会原样导入、读取和导出，不补默认值。包含新字段的包需要本次更新后的 Schema，旧的封闭 1.0 验证器可能按未知字段拒绝。

## 记录有官方来源的地点照片

先用 `source.record` 保存来源页面，再分别传图片 locator 与 Source handle。来源网页可访问不表示图片允许公开发布；许可不明时省略 usage_rights，不写“可公开使用”。

```python
{"method":"source.record", "as":"museum-source", "args":{
  "kind":"official", "title":"示例美术馆官方图片页",
  "url":"https://example.com/gallery"
}}
{"method":"media.image.add", "as":"museum-photo", "args":{
  "locator":"https://cdn.example.com/museum.jpg",
  "alt":"示例美术馆正门与石柱",
  "representation":"photo",
  "source":{"local":"museum-source"},
  "caption":"美术馆外观",
  "usages":[{"target":museum, "purpose":"place_intro"}]
}}
```

`locator` 是图片自身位置，可以是 URL、包内相对位置或本地私有路径；`source` 是已有 Source handle，两者不能互换。本方法只记录字符串，不读取 locator，也不检查远程可访问性。私有本地路径不会因此变成浏览器可读或可公开服务的文件。
临时本地路径离开当前机器或目录后可能失效；记录 locator 不会复制图片，未来要展示时须重新核对文件可达性及当时的运行时能力，不应承诺此路径可直接复用。

`source` 可省略；只有 Source 确实对应**这张图片**时才关联。地点介绍、菜单或营业信息的文字来源不自动成为图片来源。旅行者另行提供的自绘图可只记录其已知描述与私人使用范围；若需把旅行者的图片出处陈述作为 Source 留存，可另行记录该陈述，不能借用无关网页。自绘不等于 `creation.kind=generated` 或 `captured`，制作方式无可靠记录时省略 `creation`：

```python
{"method":"media.image.add", "as":"traveler-drawing", "args":{
  "locator":"/private/travel/cafe-drawing.svg",
  "alt":"旅行者自绘的茶屋与木栈桥",
  "representation":"illustration",
  "caption":"私人介绍插图，不表示精确路线",
  "usage_rights":"仅限这份私人攻略，未授权公开发布",
  "usages":[{"target":cafe, "purpose":"place_intro"}]
}}
```

`representation` 必须由调用方明确选择：

- `photo`：照片；不能仅凭逼真外观猜测。
- `illustration`：插画或手绘表达。
- `schematic`：关系、区域或路线示意；不表示精确地图和导航几何。

## 记录生成的旅程总领图

生成素材通过 `creation.kind=generated` 与非空 generator 明确记录，不使用 Source 的 `synthetic_fixture` 冒充生成来源：

```python
{"method":"media.image.add", "as":"trip-overview", "args":{
  "locator":"/private/travel/generated/overview.png",
  "alt":"巴黎主要区域与游览关系示意图",
  "representation":"schematic",
  "creation":{"kind":"generated", "generator":"OpenAI image generation"},
  "caption":"旅程总领示意，不表示精确导航路线",
  "usages":[{"target":trip, "purpose":"trip_overview"}]
}}
```

`creation` 可省略，表示没有记录制作方式；工具不会默认 captured 或 generated。已明确自行拍摄时可写 `{"kind":"captured"}`，并按证据另传 captured_at。generated 不保存 prompt、生成任务或模型参数，也不触发图片生成。

## 复用和解除用途

同一 Media 可同时用于多个 Place 或 Trip，素材只有一个 id：

```python
{"method":"media.usage.add", "args":{
  "target":media, "subject":another_place, "purpose":"place_intro"
}}
{"method":"media.usage.add", "args":{
  "target":media, "subject":trip, "purpose":"trip_overview"
}}
```

用途是封闭组合：`place_intro` 只接受 Place，`trip_overview` 只接受 Trip。同一 Media、目标、purpose 重复添加返回 no_change；创建请求中的重复用途会拒绝整批。所有参数都使用当前工作区 handle 或同批 alias，不接受其他工作区 handle 或 raw Ref。

解除一次用途不删除素材，也不影响其他用途：

```python
{"method":"media.usage.remove", "args":{
  "target":media, "subject":another_place, "purpose":"place_intro"
}}
```

移除不存在的用途返回 no_change。移除最后一个用途时，Media 保留原 id、locator、来源、许可、alt 和 caption，只删除 usages 字段；未绑定不表示候选、无版权或可删除。

## 修订可读元信息

```python
{"method":"media.update", "args":{
  "target":media,
  "set":{"alt":"更准确的替代文字", "caption":"更新后的说明"},
  "clear":["usage_rights"]
}}
```

update 只修改 alt、caption、usage_rights；caption 和 usage_rights 可 clear，alt 必须保持非空。locator、kind、representation、creation、source_ref 和 id 不可通过该方法替换，usages 必须使用专门的 add/remove。所有失败遵守批次原子性，成功 request_id 原样重放不会重复创建素材或用途。

`check.valid=true` 只证明结构、引用、用途类型和有限生成来源约束通过，不证明图片内容与 alt 相符、来源真实、许可足够、文件存在、浏览器可读、生成质量合格或页面已经展示。
