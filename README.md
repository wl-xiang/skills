# WorkBuddy Skills

一个 WorkBuddy Agent 技能（Skills）合集仓库。每个 Skill 是一个独立目录，内含 `SKILL.md` 与可选的 `scripts/`、`references/`、`assets/`。

## 目录结构

```
skills-repo/
├── README.md              # 本文件
├── .gitignore
├── .github/
│   └── workflows/
│       └── package-skill.yml   # GitHub Action：下拉选择 Skill 并打包为 ZIP
└── skills/                # 所有 Skill 统一存放在此目录下
    └── <skill-name>/      # 每个 Skill 一个目录，目录名即技能名
        ├── SKILL.md       # 必须：技能定义 + frontmatter
        ├── scripts/       # 可选：可复用脚本
        ├── references/    # 可选：参考资料
        └── assets/        # 可选：静态资源
```

## 收录的 Skills

| Skill | 说明 |
|-------|------|
| `repo-deploy-packager` | 通过 Docker Compose 部署任意 Git 仓库，并把构建出的镜像 + 源码打包成可离线还原的 TGZ 归档（带 SHA256 校验）。固定 5 阶段 SOP 与目录/命名规范。 |

> 新增 Skill 后，请在本表补充一行。

## GitHub Action 自动打包

仓库内置 GitHub Action（`.github/workflows/package-skill.yml`），可把指定 Skill 文件夹一键打包成 ZIP 并作为 Artifact 输出。

**使用方式：**
1. 进入仓库的 **Actions** 标签页，选择 **Package Skill** 工作流。
2. 点击 **Run workflow**。
3. 在出现的**下拉菜单**中选择要打包的 Skill（目前可选：`repo-deploy-packager`）。
4. 运行完成后，在 workflow 运行记录的 **Artifacts** 区域下载对应的 `<skill-name>.zip`。

> 所有 Skill 都统一放在仓库的 `skills/` 目录下，工作流会自动打包 `skills/<skill-name>` 这个文件夹。
> 打包产物仅作为 Artifact 提供下载，不会写回仓库（`.gitignore` 已忽略 `*.zip`，保持仓库干净）。

## 如何使用 / 添加某个 Skill

WorkBuddy 会在以下目录中自动发现 Skill：

- **用户级（所有项目通用）**：`~/.workbuddy/skills/<skill-name>/`
- **项目级（仅当前项目）**：`<你的项目>/.workbuddy/skills/<skill-name>/`

只要把 Skill 文件夹放到上述任一位置（目录名需与 `SKILL.md` 里的 `name` 一致），再重启/重新打开 WorkBuddy 会话即可被加载。

### 方法一：命令行（clone + 复制 / 软链）

```bash
# 1. 克隆本仓库
git clone <本仓库地址> workbuddy-skills
cd workbuddy-skills

# 2. 把指定 Skill 复制（或软链）到 WorkBuddy 的 skills 目录
#    复制：
cp -r skills/repo-deploy-packager ~/.workbuddy/skills/
#    或软链（便于跟随仓库更新，推荐）：
ln -s "$(pwd)/skills/repo-deploy-packager" ~/.workbuddy/skills/repo-deploy-packager

# 3. 重启 / 重新打开 WorkBuddy 会话，技能即可自动加载
```

> 软链方式：之后在本仓库执行 `git pull` 更新，WorkBuddy 侧的技能也会同步更新，无需重复复制。

### 方法二：应用内安装器（若已发布到 Marketplace）

若本仓库或某个 Skill 已发布到 WorkBuddy 的 Skills Marketplace，可直接在 WorkBuddy 的 **Skills / 专家** 面板中搜索并一键安装，无需手动复制文件。各发行版的安装器命令形式类似 `npx <installer> add <skill-name>`，请以你使用的 WorkBuddy 发行版文档为准。

## 如何向本仓库新增一个 Skill

1. 在 `skills/` 目录下新建 `<skill-name>/` 文件夹（目录名即技能名，建议小写中划线）。
2. 编写 `SKILL.md`，frontmatter 至少包含：
   ```yaml
   ---
   name: <skill-name>
   description: <一句话描述，说明何时使用该技能>
   ---
   ```
3. 可复用脚本放进 `scripts/`，参考文档放进 `references/`，静态资源放进 `assets/`。
4. 建议用 `skill-creator` 的 `package_skill.py` 校验结构后再提交。
5. 在上方「收录的 Skills」表格补充一行。
6. **同步更新 GitHub Action 下拉菜单**：打开 `.github/workflows/package-skill.yml`，在 `inputs.skill.options:` 列表里追加一行该 Skill 的目录名，否则它不会出现在打包界面的下拉选项中。例如：
   ```yaml
   options:
     - repo-deploy-packager
     - your-new-skill     # ← 新增这一行
   ```

## 约定

- 每个 Skill 独立成目录，目录名 = `SKILL.md` 的 `name` 字段值。
- `SKILL.md` 文件名固定，WorkBuddy 仅识别该文件名来加载技能。
- 脚本、参考、资源按用途分目录，保持仓库整洁。

## .gitignore 说明

已忽略构建产物（`dist/`、`*.zip`）、系统文件、编辑器配置、Python/Node 临时文件等，避免把本地产物误提交进仓库。
