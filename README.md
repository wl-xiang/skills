# WorkBuddy Skills

一个 WorkBuddy Agent 技能（Skills）合集仓库。每个 Skill 是一个独立目录，内含 `SKILL.md` 与可选的 `scripts/`、`references/`、`assets/`。

## 目录结构

```
skills-repo/
├── README.md              # 本文件
├── .gitignore
├── .github/
│   └── workflows/
│       └── package-skill.yml   # GitHub Action：选择压缩格式，打包全部 Skill
└── skills/                # 所有 Skill 统一存放在此目录下
    ├── sync_upstream.py   # 上游同步脚本：丢弃本地修改，拉平上游内容
    ├── sync_config.json   # 哪些 Skill 需要同步上游 + 上游地址与仓库内子目录
    └── <skill-name>/      # 每个 Skill 一个目录，目录名即技能名
        ├── SKILL.md       # 必须：技能定义 + frontmatter
        ├── scripts/       # 可选：可复用脚本
        ├── references/    # 可选：参考资料
        ├── assets/        # 可选：静态资源
        └── .upstream.json # 同步型 Skill 专属：上游来源与 commit 记录（脚本生成）
```

## 收录的 Skills

| Skill | 说明 |
|-------|------|
| `ship-repo-offline` | 通过 Docker Compose 部署任意 Git 仓库，并把构建出的镜像 + 源码打包成可离线还原的 TGZ 归档（带 SHA256 校验）。固定 5 阶段 SOP 与目录/命名规范。 |
| `docker-images-tgz-action` | 为任意仓库生成 GitHub Action workflow（**Agent 只在本地生成 `.github/workflows/docker-images.yml` 这一个 YAML 文件作为交付物；实际的 build / pull / pack 全部由用户在 GitHub Actions 云端触发执行，Agent 绝不在本地跑 Docker**）：按目标平台（`linux/amd64` / `linux/arm64`）以 **Build**（Dockerfile，默认 `./Dockerfile`）或 **Pull**（docker compose，默认 `./docker-compose.yml`，pull+build 混合：`image:` 服务按平台 pull、纯 `build:` 服务实时构建并自动填充 `仓库名:latest`，重名加 `-1/-2` 后缀）产出全部 Docker 镜像，打包成**单一 TGZ** Artifact（附独立 SHA256 Artifact），并生成完整 Action Summary（配置、服务分类、镜像清单与大小、校验值、离线恢复指南）。先只读探测仓库上下文并报告发现，再与用户确认烘焙进 YAML 的默认值，最后由内置脚本渲染 workflow；所有配置同时作为 `workflow_dispatch` 输入参数，云端运行时可改。 |
| `init-linux` | Linux 装机指南生成器（DEB 系 + RPM 系）。**不代替用户执行安装命令**（因多数步骤需 sudo，Agent 无法获取会卡住），改为：只读探测本机真实环境（发行版/包管理器/架构/桌面/已装组件）→ 联网核实最新版本与真实官方下载直链 → 生成一份单文件、离线可打开的个性化 HTML 装机指南，每个命令代码块自带「复制」按钮，用户一键复制即可执行，无需自行搜索链接。覆盖基础工具、Python/Node/Docker 运行时、Ruff 与 bash-language-server 等 LSP 工具、AI CLI 工具、Oracle Instant Client、GUI 应用（含 Desktop 条目）、主题与字体、Python 库、Cron 任务，以及 Mint 专属主题。Go / Rust / Vue / React 为可选组件，生成前会先询问用户勾选，未勾选则不写入。支持 Ubuntu / Debian / Linux Mint（apt）与 Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux（dnf/yum）。 |
| `git-commit` | **同步型 Skill（来自上游，非本仓库原创）**：内容整体取自 [`github/awesome-copilot`](https://github.com/github/awesome-copilot) 的 `skills/git-commit`（Conventional Commits 提交规范，MIT）。目录内文件是上游原文，**不要手动改**，需要更新时用 `skills/sync_upstream.py git-commit` 重新拉取（会丢弃本地修改）。 |

> 新增 Skill 后，请在本表补充一行。

## GitHub Action 自动打包

仓库内置 GitHub Action（`.github/workflows/package-skill.yml`），可将 `skills/` 下所有 Skill 一键打包成单个归档文件并作为 Artifact 输出。

**使用方式：**
1. 进入仓库的 **Actions** 标签页，选择 **Package Skills** 工作流。
2. 点击 **Run workflow**。
3. 在**格式下拉菜单**中选择压缩格式：`tgz`（推荐，体积更小）或 `zip`。
4. 运行完成后，在 workflow 运行记录的 **Artifacts** 区域下载 `wl-xiang_skills.tgz`（或 `.zip`）。

**产物结构示例（选 tgz 时）：**

```
wl-xiang_skills.tgz
├── init-linux.tgz
│   └── init-linux/
│       ├── SKILL.md
│       └── scripts/
├── ship-repo-offline.tgz
│   └── ship-repo-offline/
│       ├── SKILL.md
│       └── scripts/
└── ...
```

> 打包产物仅作为 Artifact 提供下载，不会写回仓库。

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
cp -r skills/ship-repo-offline ~/.workbuddy/skills/
#    或软链（便于跟随仓库更新，推荐）：
ln -s "$(pwd)/skills/ship-repo-offline" ~/.workbuddy/skills/ship-repo-offline

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

## 同步上游 Skill（`skills/sync_upstream.py`）

仓库里有些 Skill 是**从第三方仓库整体搬进来**的（目前是 `git-commit`）。这类 Skill 的更新方式不是手改，
而是跑同步脚本：**清空该 Skill 目录的本地修改 → 原样写入上游目标目录的全部文件**。

登记信息写在 `skills/sync_config.json`：

```json
{
  "defaults": { "ref": null },
  "skills": {
    "git-commit": {
      "enabled": true,
      "upstream": {
        "repo": "https://github.com/github/awesome-copilot",  // 上游仓库
        "ref": "main",                                        // 分支 / tag / commit，null = 上游默认分支
        "path": "skills/git-commit"                           // 上游仓库内的子目录（大仓库通常装了很多 Skill）
      },
      "keep": [".upstream.json"]                              // 清空目录时保留的文件
    }
  }
}
```

常用命令：

```bash
python skills/sync_upstream.py --list                 # 看哪些 Skill 登记了、上次同步时间
python skills/sync_upstream.py git-commit             # 同步单个（会先列出 +/~/- 变化并确认）
python skills/sync_upstream.py git-commit -y          # 跳过确认（脚本 / CI 用）
python skills/sync_upstream.py --all -y               # 同步全部 enabled 的 Skill
python skills/sync_upstream.py git-commit --dry-run   # 只预览会改什么，不落盘
python skills/sync_upstream.py git-commit --ref <sha> # 临时指定 ref
```

要点：

- **`keep` 之外的本地文件会被删除**，本地对 `SKILL.md` 的改动会被覆盖——想保留定制请复制成新目录并改名。
- 每次同步后在该 Skill 目录写入 `.upstream.json`（来源、ref、commit、时间、文件清单），可提交进仓库做溯源。
- 上游是 GitHub 时走 API 按目录递归抓取（不拉全仓库 tree）；非 GitHub 时退回 `git clone --sparse`。
- 抓取遇到限流或私有仓库，设置环境变量 `GITHUB_TOKEN` / `GH_TOKEN` 即可。

## 约定

- 每个 Skill 独立成目录，目录名 = `SKILL.md` 的 `name` 字段值。
- `SKILL.md` 文件名固定，WorkBuddy 仅识别该文件名来加载技能。
- 脚本、参考、资源按用途分目录，保持仓库整洁。

## .gitignore 说明

已忽略构建产物（`dist/`、`*.zip`）、系统文件、编辑器配置、Python/Node 临时文件等，避免把本地产物误提交进仓库。
