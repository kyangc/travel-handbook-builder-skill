# Travel Handbook Builder Skill

把用户提供的旅行资料转换成**私有、结构化、可持续编辑**的旅行手册工作区。

This repository contains the public release of the `travel-handbook-builder-skill` agent skill. It is designed for agents that need to preserve explicit travel facts, unknowns, sources, revisions, and decisions without silently inventing plans or booking status.

## 它解决什么问题

普通旅行文档很容易在多轮修改中丢失来源、覆盖人工决定，或把“推荐”“参考价”“已预订”“已付款”混为一谈。这个 Skill 提供一套受约束的本地编制运行时，让 Agent 可以：

- 从 Markdown 或 JSON 旅行资料创建 typed handbook；
- 保存完整 state，并在新会话中无损续编；
- 渐进补充日期、地点、成员、路线、住宿、费用、任务和来源；
- 区分推荐与正式安排、参考报价与本次费用、费用与付款；
- 保留未知值，不用猜测补齐缺失信息；
- 在写入前 preview，并在写入后 read、check 和私有 export；
- 使用稳定 request ID 和调用方保存的 request journal 安全重放。

运行时不会替用户选择目的地、酒店、航班、餐厅或路线，也不会执行现实预订、付款、公开发布或事实核验。

## 仓库内容

```text
travel-handbook-builder-skill/
├── travel-handbook-builder-skill/   # 可直接安装的完整 Skill
│   ├── SKILL.md
│   ├── README.md                # 运行环境与 API 使用说明
│   ├── references/              # 面向 Agent 的公开调用指南
│   ├── runtime/                 # 本地 authoring 运行时与 Schema
│   ├── scripts/                 # setup、CLI、Python wrapper、完整性校验
│   ├── requirements.txt
│   └── MANIFEST.json
├── CHANGELOG.md                 # 对外发布记录
├── RELEASING.md                 # 维护与发布流程
└── tools/                       # manifest 与确定性 ZIP 构建工具
```

开发路线图、内部实验、评分器、私有旅行数据、历史会话和验收原始日志不属于发布仓库。

## 安装

要求 Python 3.12+ 和 POSIX shell。首次 setup 需要从已配置的包索引或缓存安装依赖。

```sh
git clone https://github.com/kyangc/travel-handbook-builder-skill.git
cd travel-handbook-builder-skill

python3 travel-handbook-builder-skill/scripts/verify_bundle.py
python3 travel-handbook-builder-skill/scripts/setup_runtime.py
```

setup 只会在 Skill 目录中创建 `.venv`，不会修改全局 Python 环境。

### Kimi CLI

仓库根目录就是 skills parent directory：

```sh
kimi --skills-dir "$(pwd)"
```

随后可以直接提出自然语言任务，例如：

> 请根据 source.md 中明确的旅行资料创建可继续编辑的结构化攻略。保留未知，不新增原文没有的预订、付款或安排。把完整状态、私有导出、请求日志和逐项对账保存到 output/。

### Codex 或其他 Agent

把完整目录 `travel-handbook-builder-skill/` 放入 Agent 的 skills 目录。不要只复制 `SKILL.md`；公开指南、运行时、Schema、启动器和 manifest 都是 Skill 合同的一部分。首次使用前在目标机器运行上面的完整性校验和 setup，或按 [Skill README](travel-handbook-builder-skill/README.md) 使用已有的合适 Python 环境。

在新的 Codex 任务中可用自然语言指向你**本地私有**的旧行程 Markdown，例如：

> 请用 travel-handbook-builder-skill 根据这份旧行程 Markdown 建立可继续编辑的私人攻略，并给我原目录下的预览。保留原文已确定的事实与未决项，不自行替我选新地点、路线、预订或付款；说明实际写入、尚未确认和页面核验到哪一层。

旅行资料、完整 state 和导出应留在安装目录之外。这个示例只说明用法，不代表对任意真实资料的重建已通过验收。

## 命令行快速检查

启动器可以从任意当前目录调用：

```sh
SKILL_DIR="/absolute/path/to/travel-handbook-builder-skill"

"$SKILL_DIR/scripts/travel-handbook" --help
"$SKILL_DIR/scripts/travel-handbook" create "/work/trip-state.json" \
  --title "Example trip" --example
"$SKILL_DIR/scripts/travel-handbook" read "/work/trip-state.json"
"$SKILL_DIR/scripts/travel-handbook" check "/work/trip-state.json"
```

创建写请求前阅读 [Caller Guide](travel-handbook-builder-skill/references/CALLER_GUIDE.md)。完整安装、CLI 和 Python API 说明见 [Skill README](travel-handbook-builder-skill/README.md)。

## 关键产物

- **完整 state**：后续续编的唯一无损输入，包含 handle、回执、来源快照和决策元数据。
- **canonical private export**：可由 `import_package` 重新导入的领域包。
- **request journal**：调用方保存的成功原始请求，用于精确重放；它不属于旅行领域 state。
- **reconciliation**：原资料每一项进入 typed 记录、保留为说明或成为明确缺口的对账。

请把旅行 state、导出和来源文件保存在安装目录之外。它们可能包含姓名、日期、位置、订单或其他个人信息，默认应视为私有数据。

## 验证范围

**0.3.1** 修复 URL 接受/显示一致性与预览媒体根恢复，补充地图覆盖只读报告、显式精简 CLI 元数据、分层详情和指南。Web、构建、完整性/隐私及包外公开入口已验；Python 全套中两个过时文案断言修后通过，另两项历史冻结 ZIP 缺失保留原失败门禁，不能称全套全绿。本轮不声明自然 caller 效果或效率提升；真实鉴权 Google SDK、原 in-app browser 环境和远程素材条件仍未复验，发布也不表示本机已安装或既有攻略已更新。

0.3.0 引入有理由的 Task 撤下、显式 Route Stop 遭遇类型及酒店当地入住起始时间等能力。首次到店仅在明确可比较的早到时间下显示“入住·行李寄存”，不推断进房或重排日程。既有独立 caller 在 GuideNote 重复及日期归属仍有部分失败；后续确定性副本修复和指南静态检查不证明自主行为效果。

0.2.0 发布当时的工程验收包括：以已提交开发源构建候选，核对公开仓库与 release ZIP 同一 manifest/字节，检查私有资料和凭据排除、安装或已配置 Python 的 CLI 路径，以及受影响业务回归。此前的外部 Agent 单例与 0.1.0 Kimi 冻结集分别属于其当时的包和题目；**0.2.0 发布当时，其 release asset 尚未完成新会话 Codex 真实旧行程 Markdown 重建**。当时该真实案例安排在0.2.0发布后另报业务结果、页面证据和未测边界；这里保留当时的验收范围，不将后续其他版本的结果归作0.2.0通过，也不由单例推普遍可靠性。若未来某版要声明新的自然发现或跨场景能力，应为该声明冻结相应的新会话行为验收；不能因本版验证方式改变而取消必要的安全、正确性或来源核对。

公开版从开发仓库的已验收实现确定性生成，并把内部 Schema 演进历史收敛为单一稳定数据契约 1.0。公开调用方无需执行版本升级，也不会看到开发阶段的多个 draft Schema 目录。

## 发布与贡献边界

这个仓库只在 Skill 对外版本变化时更新。行为、公开指南、运行依赖、Schema、安装体验或发布元数据的变化应进入 [CHANGELOG](CHANGELOG.md)。内部研究记录和具体旅行材料不会迁入。

维护约定见 [RELEASING.md](RELEASING.md)，贡献范围见 [CONTRIBUTING.md](CONTRIBUTING.md)。

## License

原创内容使用 [MIT License](LICENSE)。第三方依赖与归属见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
