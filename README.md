# 行迹 · Travel Handbook Builder

**把散落的旅行资料，整理成一本能随时翻看、继续修改的私人旅行手册。**

给支持 Skill 的 AI 助手一份行程、一段笔记，或几轮对话。行迹帮助它整理每天的安排、收藏的地点、住宿与行前待办，并在浏览器里呈现。你决定去哪、怎么走；已确定的安排和待确认的事分别记清楚。

[下载最新版本](https://github.com/kyangc/travel-handbook-builder-skill/releases/latest) · [四个标签页的电脑／手机导览](docs/product-tour.md) · [开始使用](#开始使用) · [更新记录](CHANGELOG.md)

## 一份计划，整理到出发也用得上

- **对话里整理，计划变了继续改。** 从行程笔记开始，在同一份本地工作区补充和修订。
- **安排与想法分清楚。** 按天查看活动和交通，候选兴趣点单独保留，住宿与行前待办关联到旅行。
- **电脑筹划，手机查阅。** 同一份手册自适应呈现，地点可点开，准备清单可勾选。
- **按天查看天气。** 你明确选择每天的天气地点后，网页在线查询预报；天气卡显示气温、风速和降雨概率，总览标题和每日地点旁的信息入口可查看来源。
- **保留依据和未知。** 资料来源、待确认信息与已确定安排分别记录，关键事实由你审阅。

| 电脑：日程与其他兴趣点 | 手机：同一天的安排 |
| --- | --- |
| <img src="docs/screenshots/itinerary-desktop.png" alt="电脑日程：海岸散步、步行衔接与美术馆安排，候选兴趣点单列" width="600"> | <img src="docs/screenshots/itinerary-mobile.png" alt="手机日程：按日期查看同一天的活动与交通" width="195"> |

*0.3.6 实际渲染的纯虚构演示「青湾慢游」；风景为自制示意插图，不代表真实地点或可执行行程。[完整导览包含总览、待办、日程、途点的八张截图](docs/product-tour.md)。*

天气预报由浏览器直连 Open-Meteo，不附带 API key，免费接口限非商业使用；资料缺失或不在预报范围时明确提示。本地预览只保留会话天气；在另行部署且支持手动离线保存的站点中，只有你主动保存攻略才会保存匹配版本的天气，天气失败不阻断完整攻略。独立站点的鉴权与离线保存不包含在 Skill 中。

地图支持自行配置的 Google Maps；无配置或服务不可用时显示明确标注的地点示意。Skill 不附带 Google key，也不提供真实离线底图。

## 开始使用

行迹需要配合 Codex、Kimi CLI 等支持本地 Skill 的 AI 工具。运行环境为 Python 3.12+ 与 POSIX shell（如 macOS、Linux）。

1. 从 [Releases](https://github.com/kyangc/travel-handbook-builder-skill/releases/latest) 下载 ZIP 并解压，保留完整的 `travel-handbook-builder-skill` 文件夹。
2. 按 [安装指南](travel-handbook-builder-skill/README.md#install) 校验、准备运行环境，并让助手加载该 Skill。
3. 将旅行资料与工作区放在安装目录之外，在对话里开始整理：

> 请用 travel-handbook-builder-skill，把这份行程笔记整理成私人旅行手册，并打开本地预览。保留我已经确定的安排，推荐地点单独列出；没有确认的时间、预订和费用不要补猜。

后续可让助手继续补充或更正同一份手册。恢复、命令和专题说明见 [Skill 使用入口](travel-handbook-builder-skill/README.md)。

## 使用边界

浏览器预览在本机运行，默认不提供分享链接、跨设备访问或公开托管。使用云端 AI 助手时，资料的发送与保存取决于该工具；“本地手册”不表示所有处理都离线。

行迹不替你订票、付款或作出最终旅行选择，也不保证营业时间、价格、接驳和外部图片始终有效。请审阅结果并在出行前核实关键事实。版本变化与具体验证范围见 [CHANGELOG](CHANGELOG.md)。

[给 AI 助手的入口](travel-handbook-builder-skill/SKILL.md) · [贡献说明](CONTRIBUTING.md) · [维护与发布](RELEASING.md) · [MIT 许可](LICENSE) · [第三方归属](THIRD_PARTY_NOTICES.md)
