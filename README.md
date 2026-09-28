# 行迹 · Travel Handbook Builder

**把散落的旅行资料，整理成一本能随时翻看、继续修改的私人旅行手册。**

给支持 Skill 的 AI 助手一份行程、一段笔记，或几轮对话。行迹帮助它整理每天的安排、收藏的地点、住宿与行前待办，并在浏览器里呈现。你决定去哪、怎么走；已确定的安排和待确认的事分别记清楚。

[下载最新版本](https://github.com/kyangc/travel-handbook-builder-skill/releases/latest) · [开始使用](#开始使用) · [更新记录](CHANGELOG.md)

![桌面日程：左侧当天安排，右侧其他兴趣点](docs/screenshots/itinerary.png)

*截图来自 0.3.6 实际渲染的虚构演示「青湾慢游」，风景为自制示意插图，不代表真实地点或可执行行程。*

## 从每天的节奏，看到一个地点的细节

按天查看活动与交通，点开地点了解介绍和游览建议。想去但尚未安排的地方留在“其他兴趣点”；住宿、往返交通和准备清单也可集中查看。计划变了，让助手在保存的本地工作区继续修改。

手机可以阅读同一份手册，打开详情和勾选准备清单。地图可使用自行配置的 Google Maps；无配置或服务不可用时显示有明确标注的地点示意。Skill 不附带 Google key，也不提供真实离线底图。

<img src="docs/screenshots/mobile-detail.png" alt="手机地点详情：示意图、地点介绍与游览建议" width="390">

## 开始使用

行迹需要配合 Codex、Kimi CLI 等支持本地 Skill 的 AI 工具。运行环境为 Python 3.12+ 与 POSIX shell（如 macOS、Linux）。

1. 从 [Releases](https://github.com/kyangc/travel-handbook-builder-skill/releases/latest) 下载 ZIP 并解压，保留完整的 `travel-handbook-builder-skill` 文件夹。
2. 按 [安装指南](travel-handbook-builder-skill/README.md#requirements-and-isolated-setup) 校验、准备运行环境，并让助手加载该 Skill。
3. 将旅行资料与工作区放在安装目录之外，在对话里开始整理：

> 请用 travel-handbook-builder-skill，把这份行程笔记整理成私人旅行手册，并打开本地预览。保留我已经确定的安排，推荐地点单独列出；没有确认的时间、预订和费用不要补猜。

后续可让助手继续补充或更正同一份手册。恢复、命令和专题说明见 [Skill 使用入口](travel-handbook-builder-skill/README.md)。

## 使用边界

浏览器预览在本机运行，默认不提供分享链接、跨设备访问或公开托管。使用云端 AI 助手时，资料的发送与保存取决于该工具；“本地手册”不表示所有处理都离线。

行迹不替你订票、付款或作出最终旅行选择，也不保证营业时间、价格、接驳和外部图片始终有效。请审阅结果并在出行前核实关键事实。版本变化与具体验证范围见 [CHANGELOG](CHANGELOG.md)。

[给 AI 助手的入口](travel-handbook-builder-skill/SKILL.md) · [贡献说明](CONTRIBUTING.md) · [维护与发布](RELEASING.md) · [MIT 许可](LICENSE) · [第三方归属](THIRD_PARTY_NOTICES.md)
