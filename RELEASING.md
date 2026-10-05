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

在开发仓库为本次发行设置一次版本，并运行发布准备命令；它会构建公开 Skill、同步模板、刷新 manifest、校验 bundle 并生成最终确定性 ZIP：

```sh
VERSION=0.3.10  # 替换为本次选定版本；后续命令沿用同一 shell
python3 scripts/prepare_public_release.py \
  --version "$VERSION" \
  --release-repo /absolute/path/to/travel-handbook-builder-skill
```

生成器会用命令中的版本更新 Skill manifest 与 release tag；任何下一版本的修改仍应先回到开发仓库模板。

## 4. Verify generated files

在新生成的公开仓库目录运行；准备命令已刷新 manifest，不需无改动重建：

```sh
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

## 6. Accept the generated ZIP

```sh
ZIP="dist/travel-handbook-builder-skill-${VERSION}.zip"
shasum -a 256 "$ZIP"
unzip -t "$ZIP"
ACCEPT_DIR="$(mktemp -d)"
unzip -q "$ZIP" -d "$ACCEPT_DIR"
python3 "$ACCEPT_DIR/travel-handbook-builder-skill/scripts/verify_bundle.py"
BUNDLE_PYTHON="$(travel-handbook-builder-skill/scripts/python -c 'import sys; print(sys.executable)')"
TRAVEL_HANDBOOK_PYTHON="$BUNDLE_PYTHON" \
  "$ACCEPT_DIR/travel-handbook-builder-skill/scripts/travel-handbook" --help
```

在独立目录继续按第 5 节验证受影响的公开 CLI 路径，并将同一个 `TRAVEL_HANDBOOK_PYTHON` 显式传给解压包；依赖未变时无需再次安装。构建器只打包 manifest 声明的文件与 `MANIFEST.json`，使用固定时间戳和权限。若需要单独验收确定性，可在**未改动候选文件**时运行 `python3 tools/build_release.py --output "$ACCEPT_DIR/rebuilt.zip"`，并用 `cmp "$ZIP" "$ACCEPT_DIR/rebuilt.zip"` 比较；这只是第二次构建验收，不要求重跑准备、刷新 manifest 或安装。

## 7. Publish

```sh
git tag -a "v${VERSION}" -m "travel-handbook-builder-skill v${VERSION}"
git push origin main --follow-tags
gh release create "v${VERSION}" "$ZIP" \
  --title "travel-handbook-builder-skill v${VERSION}" \
  --notes-file /path/to/release-notes.md
```

发布后核对仓库可见性、tag、默认分支 HEAD，并把远端 asset 下载到另一目录核对 SHA-256：

```sh
REMOTE_DIR="$(mktemp -d)"
gh release download "v${VERSION}" --pattern "travel-handbook-builder-skill-${VERSION}.zip" --dir "$REMOTE_DIR"
shasum -a 256 "$ZIP" "$REMOTE_DIR/travel-handbook-builder-skill-${VERSION}.zip"
```
