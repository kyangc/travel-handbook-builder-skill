# Release process

本仓库只在 `travel-handbook-builder-skill` Skill 对外版本变化时发布。发布内容由开发仓库生成并同步；不要直接修改生成的 Skill 目录。

## 1. Scope review

- 确认变更仅涉及 Skill 行为、公共指南、运行依赖、Schema、安装或发布维护。
- 移除开发路线图、内部实验、评审原始日志、私有旅行资料和凭据。
- 行为或说明变化须保留未知、不执行现实选择/预订/付款，并继续区分 state、canonical package 和 report。

## 2. Version and changelog in the development repository

- 按 Semantic Versioning 选择版本。
- 先在开发仓库的 `packaging/public-repository/CHANGELOG.md` 把 `Unreleased` 内容移动到带日期的新版本节。
- 同步更新开发仓库中的公开 README、发布说明模板或维护工具。公开仓库根文件和 Skill 目录都是生成结果，不直接编辑。

## 3. Generate from the development repository

在开发仓库运行发布准备命令；它会构建稳定公开契约、同步 Skill 与仓库模板、刷新 manifest 并生成确定性 ZIP：

```sh
python3 scripts/prepare_public_release.py \
  --version 0.3.4 \
  --release-repo /absolute/path/to/travel-handbook-builder-skill
```

生成器会用命令中的版本更新 Skill manifest 与 release tag；任何下一版本的修改仍应先回到开发仓库模板。

## 4. Verify generated files

```sh
python3 tools/refresh_manifest.py --version 0.3.4 --release-tag v0.3.4
python3 travel-handbook-builder-skill/scripts/verify_bundle.py
python3 travel-handbook-builder-skill/scripts/setup_runtime.py
travel-handbook-builder-skill/scripts/travel-handbook --help
python3 travel-handbook-builder-skill/scripts/verify_bundle.py
```

setup 后再次 verify 是必需项，用于确认正常运行没有污染受校验的 bundle。

## 5. Behavioral acceptance

- 仅改发布元数据时，验证 manifest、安装、CLI 和 ZIP 即可。
- 修改 `SKILL.md`、公开指南、运行时或 Schema 时，运行受影响的业务回归。
- 对新行为按风险运行受影响的公开接口、数据保持和预览验证；历史测试与不同候选包的单例不能冒充当前 release asset 的通过结果。
- 当本版**声明**新的自然发现、跨模型或跨场景能力，或该行为是发布阻断风险时，先用与该声明相称的新目录、新会话案例验收；失败保留，不补教或挑成功样本。若真实资料体验明确安排为发布后验，发布说明须写明尚未验收的范围与后续结果入口，不能说已通过。
- 失败记录不得由修复后的成功覆盖；新候选使用新证据目录。

## 6. Build release ZIP

```sh
python3 tools/build_release.py
shasum -a 256 dist/travel-handbook-builder-skill-0.3.4.zip
```

构建器只打包 manifest 声明的文件与 `MANIFEST.json`，使用固定时间戳和文件权限生成确定性 ZIP。

## 7. Publish

```sh
git tag -a v0.3.4 -m "travel-handbook-builder-skill v0.3.4"
git push origin main --follow-tags
gh release create v0.3.4 dist/travel-handbook-builder-skill-0.3.4.zip \
  --title "travel-handbook-builder-skill v0.3.4" \
  --notes-file /path/to/release-notes.md
```

发布后核对仓库可见性、tag、release asset SHA-256 和默认分支 HEAD。
