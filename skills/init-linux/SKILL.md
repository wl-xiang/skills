---
name: init-linux
description: >
  This skill should be used when the user wants to initialize / set up a fresh
  Linux machine, both DEB-based (Debian / Ubuntu / Linux Mint, apt) and
  RPM-based (Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux, dnf or yum),
  e.g. "帮我初始化这台新机器", "一键装机", "init linux", "配置开发环境",
  "装一遍我的常用工具". It DOES NOT execute any install / upgrade / sudo command.
  Instead it (1) runs read-only probes to detect the real machine environment
  (distro, package manager, CPU arch, desktop, already-installed tools),
  (2) uses web search to resolve the latest versions and REAL official download
  links, and (3) generates ONE personalized, copy-ready HTML guide with a
  per-command copy button, covering base tools, Python/Node/Docker runtimes,
  Ruff and bash-language-server, AI CLI tools, Oracle Instant Client, GUI apps
  with Desktop entries, themes & fonts, Python libraries, a Downloads cron job,
  and Mint-specific themes. Go / Rust / Vue / React are OPTIONAL components:
  the skill asks the user to select them (multi-choice) and only writes the
  selected ones into the guide. It should NOT be used for single-package
  installs or unsupported distros (Arch 等；openSUSE 的 zypper 流程未完整覆盖).
agent_created: true
---

# init-linux — Linux 一键装机（生成可复制的个性化装机指南）

本技能不再代替用户执行安装命令，而是：**探测本机真实环境 → 联网核实最新版本与真实下载直链 →
生成一份"可一键复制命令"的个性化 HTML 装机指南**交给用户，由用户自行执行。

## 核心原则（重要变更，必须遵守）

1. **禁止代执行**：本技能**不得**执行任何安装 / 升级 / 初始化命令。
   绝大多数步骤需要 sudo/root，Agent 无法获得权限，强行执行只会卡住。
   严禁出现：`sudo`、`apt/dnf/yum/zypper install`、`npm install -g`、`pip install`、
   `usermod`、`systemctl`、写 `/etc`、改 crontab、克隆后运行 `./install.sh` 等命令。
2. **只读探测**：Agent 只允许执行**只读**命令来采集环境信息（见「允许执行的命令白名单」），
   不得修改系统状态。
3. **联网核实**：所有"最新版本号"与"下载链接"必须通过**联网检索（Web Search / 官方 Releases API
   等）实时核实**得到真实、可访问的官方 URL，**严禁臆造或凭记忆写死链接**。
4. **唯一产物**：本技能最终交付**一份** HTML 文档（单文件、离线可打开）：
   - 路径：`~/init-linux-guide-YYYYMMDD.html`（YYYYMMDD 为当天日期）
   - 每段命令都是一个带「复制」按钮的代码块，用户点一下即可复制到终端执行。
   - 文档中出现的所有下载链接都必须是核实过的真实直链，用户无需再去自行搜索。
5. **个性化**：文档内容按探测结果裁剪——只保留命中的包管理器分支（apt 或 dnf），
   已安装的软件标注"已安装，建议跳过"，未勾选的可选组件直接不写入命令。

## 允许执行的命令白名单（仅只读）

| 目的 | 命令示例 |
|------|----------|
| 发行版信息 | `cat /etc/os-release`、`lsb_release -a` |
| CPU 架构 | `uname -m`、`uname -srv` |
| 桌面环境 | `echo "$XDG_CURRENT_DESKTOP"`、`echo "$DESKTOP_SESSION"` |
| 环境变量 | `echo "$PATH"`、`echo "$HOME"` |
| 已装检测 | `command -v <tool>`、`<tool> --version`、`npm ls -g --depth=0`、`crontab -l` |
| 目录探测 | `ls -d ~/.local/bin ~/Downloads ~/下载 2>/dev/null`、`xdg-user-dir DOWNLOAD` |
| 联网只读核实 | `curl -fsSL https://api.github.com/repos/<owner>/<repo>/releases/latest`、`curl -I <URL>`（校验链接存在） |

> 白名单之外的一律不执行；尤其**任何带 `sudo` 或会写盘/改配置的命令**，只能写进 HTML 文档交给用户。

## 工作流程（4 个阶段）

### 阶段 0 — 环境探测（只读）

用白名单命令采集以下信息，作为文档「本机环境摘要」与内容裁剪依据：

- `/etc/os-release`：`ID`、`ID_LIKE`、`VERSION_ID`、`PRETTY_NAME`。
- 包管理器判定（见下表）。
- CPU 架构 `uname -m`（区分 x86_64 / aarch64，及用于拼 URL 的资产名映射）。
- 桌面环境 `$XDG_CURRENT_DESKTOP`（决定是否写入 Desktop 条目、主题类步骤）。
- 已装情况：`python3 --version`/`python --version`、`node -v`、`docker --version`、
  `command -v go rustc ruff bash-language-server opencode pi yq fd bat` 等，逐项记录。

包管理器判定表（用于裁剪文档，只输出命中的分支）：

| 判定 | 发行版 | 包管理器 |
|------|--------|----------|
| ID 或 ID_LIKE 含 `debian` | Debian / Ubuntu / Linux Mint | `apt` |
| ID 或 ID_LIKE 含 `fedora` / `rhel` / `centos` / `rocky` / `almalinux` | Fedora / RHEL 系 | `dnf`（无 dnf 时 `yum`） |
| ID 或 ID_LIKE 含 `suse` | openSUSE 系 | `zypper`（仅基础工具；第三方源步骤标 ⚠️需手动处理） |

**架构命名映射**（拼下载 URL 时以目标项目实际资产名为准）：
`uname -m` → Go 用 `amd64/arm64`，yq 用 `x86_64/arm64`，Oracle 用 `x64/arm64`，其余以 Releases 资产列表为准。

### 阶段 1 — 可选组件确认（先与用户交互）

在任何内容生成之前，用 AskUserQuestion 让用户**多选**以下可选项，**未勾选的一律不写入文档**：

| 选项 | 内容 | 对应步骤 |
|------|------|----------|
| Go | Golang 最新稳定版运行时 | 2.4 |
| Rust | rustup + rustc/cargo 工具链 | 2.5 |
| Vue | Vue 3 语言服务（`@vue/language-server`、`@vue/typescript-plugin`、`typescript`） | 2.7 |
| React | TypeScript + typescript-language-server（覆盖 TSX 的 LSP） | 2.7 |

说明：`bash-language-server`（2.7 固定部分）与其余所有步骤（含 2.6 Ruff）均为必写章节，不受勾选影响。
展示勾选清单时可附上探测结果（如"检测到已装 Go 1.22"）。

### 阶段 2 — 联网核实版本与真实下载直链（关键步骤）

对文档中每一处"下载 / 从官网获取最新版"的地方，**必须联网检索核实后写入真实链接**，
禁止留空、禁止臆造、禁止让用户自己去搜。至少覆盖：

| 目标 | 需要核实的内容 |
|------|----------------|
| Go | 最新 stable 版本号 + `go<版本>.linux-<arch>.tar.gz` 直链（`https://go.dev/dl/`） |
| yq | 最新版 + `yq_linux_<amd64\|arm64>` 二进制直链（GitHub mikefarah/yq releases） |
| Node.js | NodeSource 24.x 安装脚本 URL（`https://deb.nodesource.com/setup_24.x` / `https://rpm.nodesource.com/setup_24.x`） |
| Docker | 对应发行版官方仓库 URL / `docker-ce.repo` URL 与安装文档页 |
| Ruff | `https://astral.sh/ruff/install.sh` |
| OpenCode / Pi Agent | 官方安装脚本 URL（`https://opencode.ai/install`、`https://pi.dev/install.sh`） |
| Oracle Instant Client | `download.oracle.com/otn_software/linux/instantclient/` 下最新 basic / sqlplus 的 Linux zip 直链（按 `linux.x64`/`linux.arm64`），确认免登录可直下 |
| WindTerm | GitHub kingToolbox/WindTerm 最新 Linux tar.gz 资产直链 |
| Zed | GitHub zed-industries/zed 最新 Linux tar.gz 资产直链（按架构确认资产存在） |
| Ghostty | Ubuntu/Debian deb 源安装脚本 URL；Flatpak 包名 `com.mitchellh.ghostty` |
| Sublime Text | 官方 apt/rpm 仓库配置说明页与 `sublime-text.repo` URL、GPG key URL |
| Dbx | GitHub t8y2/dbx 最新 .deb/.rpm/AppImage 资产直链 |
| Maple Mono 字体 | GitHub subframe7536/maple-font 最新 Release 中 `NF-CN` zip 直链 |
| ayu 主题 / Dracula WindTerm | 仓库地址与安装说明页 |
| WhiteSur / McMojave（Mint） | 仓库地址 |

要求：
- 优先用 GitHub Releases API（`/releases/latest`）或官方下载页解析真实资产名；
- 拼完链接后**用 `curl -I` 校验可访问**（至少校验关键的大文件直链）；不可用则换官方备用链接并在文档中注明；
- 无法核实到真实直链的项，在文档中标注 ⚠️"请前往官方页面获取"并给出**官方页面 URL**（仍须是核实过的真实网址）。

### 阶段 3 — 生成 HTML 文档

以本技能捆绑的 `assets/guide-template.html` 为外壳（已内置样式与"自动给每个 `<pre>` 注入复制按钮"的脚本），
将占位符替换后写出到 `~/init-linux-guide-YYYYMMDD.html`：

- `{{TITLE}}` → 如 `Linux 装机指南 · Ubuntu 24.04 (x86_64)`
- `{{GENERATED_AT}}` → 生成时间
- `{{ENV_SUMMARY}}` → 环境摘要卡片 HTML（见下方结构）
- `{{CONTENT}}` → 各步骤 `<section class="card">…</section>`

**文档结构要求**：

1. **本机环境摘要**：用一个 `.env-grid` 展示发行版/版本、包管理器分支、CPU 架构、桌面环境、
   已装关键组件；必要时附 `table`。
2. **按步骤组织**（对应下文「步骤内容」1–10）：每步一个 `<section class="card">`，
   含：步骤标题 `<h2>`、简短说明、命令代码块、验证命令、需要的下载链接（真实 URL）。
3. **代码块写法**：只用标准 `<pre><code>…</code></pre>`，模板脚本会**自动**为每个 `pre`
   生成右上角「复制」按钮，无需手写按钮；命令中的 `<`、`>`、`&` 需转义。
4. **命令标注**：需要 sudo 的命令保持命令原样书写（用户执行时自行加/带 sudo），
   并在步骤说明中提示该步需要 sudo 权限。
5. **予以提示的风险**：如 `usermod -aG docker` 后需重新登录、
   `rm -rf /usr/local/go` 属官方升级方式、`source ~/.bashrc` 生效范围等。
6. **裁剪规则**：只写命中的包管理器分支命令；已安装项加 `<span class="tag warn">已安装，建议跳过</span>`；
   未勾选的可选组件整段省略（可在摘要中一句话说明"未选择的路由：…"）。
7. **单文件、离线可用**：CSS/JS 全部内联，不引用任何外部资源（字体、CDN 均不用）。

## 步骤内容（写入 HTML 的章节清单）

> 下方为每个步骤应写入文档的内容。代码块中标注 **[apt]** / **[dnf]** 的，
> 只写当前机器命中的那一支；未标注的两种发行版通用。

### 步骤 1：系统基础工具

- **[apt]**：先 `sudo apt update`，再
  `sudo apt install -y vim git curl wget jq ripgrep bat tree zip unzip build-essential openssh-server fd-find`
- **[dnf]**：
  `sudo dnf install -y vim git curl wget jq ripgrep bat tree zip unzip gcc gcc-c++ make openssh-server fd-find`

要点（写入文档的注意事项）：
- **yq 从 GitHub Releases 安装**（mikefarah/yq 的 Go 版二进制，放入 `~/.local/bin` 并 `chmod +x`）；
  不用 apt/dnf 源里的 `yq`（那是 Python 版 kislyuk/yq，语法不兼容）。链接须在阶段 2 核实。
- **[apt]** `fd` 包名是 `fd-find`、`bat` 二进制名为 `batcat`，需软链：
  `ln -sf "$(command -v fdfind)" ~/.local/bin/fd`、`ln -sf "$(command -v batcat)" ~/.local/bin/bat`；
  **[dnf]** 包名与二进制名即 `fd`/`bat`，无需软链。
- 启用 SSH：**[apt]** `sudo systemctl enable --now ssh`；**[dnf]** `sudo systemctl enable --now sshd`。
- 前置：`mkdir -p ~/.local/bin`，并确认其在 PATH 中。

### 步骤 2：开发运行时

**2.1 Python（>= 3.10）** —— 按探测结果给出对应命令：
- 若已有 >= 3.10：写"已满足，跳过"，不写安装命令。
- 若只有 `python3` 无 `python`：**[apt]** `sudo apt install -y python-is-python3`；
  **[dnf]** `sudo dnf install -y python-unversioned-command`；
  RHEL 系无该包时：`sudo dnf install -y python3` 后
  `sudo alternatives --install /usr/bin/python python /usr/bin/python3 1`、
  `sudo alternatives --set python /usr/bin/python3`。
- 若版本 < 3.10 或未安装：
  **[apt]** Ubuntu 用 deadsnakes PPA（`sudo add-apt-repository ppa:deadsnakes/ppa` 后装
  `python3.13 python3.13-venv python3.13-dev`）；Debian 或无 PPA 时从 python.org 源码编译；
  **[dnf]** RHEL 系源码编译前先装
  `sudo dnf install -y gcc make openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel`。
  源码编译需给出 python.org 当前最新 3.13.x 的**真实下载直链**（阶段 2 核实）。
- 提示：不要改动系统默认 `python3` 指向（apt 系系统工具可能依赖旧版）。

**2.2 Node.js（24.x）**：
- **[apt]** `curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash - && sudo apt install -y nodejs`
- **[dnf]** `curl -fsSL https://rpm.nodesource.com/setup_24.x | sudo bash - && sudo dnf install -y nodejs`
- 验证：`node -v`（主版本 24）。

**2.3 Docker 与 Docker Compose**：按官方文档添加对应发行版官方仓库。
- **[apt]**（`download.docker.com/linux/ubuntu` 或 `/debian`）安装
  `docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`。
- **[dnf]** 仓库 URL 按发行版：Fedora → `/linux/fedora`，CentOS/Rocky/Alma → `/linux/centos`，
  RHEL → `/linux/rhel`；先判断 dnf 主版本：
  dnf5 → `sudo dnf config-manager addrepo --from-repofile=<docker-ce.repo URL>`；
  dnf4 → `sudo dnf install -y dnf-plugins-core` 后 `sudo dnf config-manager --add-repo <URL>`。
- 安装后：`sudo usermod -aG docker $USER`（提示需重新登录生效）、
  `sudo systemctl enable --now docker`；验证 `docker --version`、`docker compose version`。

**2.4 Golang（可选，仅勾选时写入）**：
从 go.dev 下载最新 stable 的 `go<版本>.linux-<arch>.tar.gz`（**真实直链**，阶段 2 核实），
`sudo rm -rf /usr/local/go`（官方升级方式，先备份可有可无）、
`sudo tar -C /usr/local -xzf …`；并把 `/usr/local/go/bin` 加入 PATH（先 grep 防重复）。

**2.5 Rust（可选，仅勾选时写入）**：
`command -v rustc` 检测后，`curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y`，
安装后 `source "$HOME/.cargo/env"`，验证 `rustc --version`、`cargo --version`。

**2.6 Ruff（必写）**：`curl -LsSf https://astral.sh/ruff/install.sh | sh`，验证 `ruff --version`。

**2.7 全局 NPM 工具**：
- 固定：`sudo npm install -g bash-language-server`，验证 `bash-language-server --version`。
- 勾选 Vue：`sudo npm install -g @vue/language-server @vue/typescript-plugin typescript`；
- 勾选 React：`sudo npm install -g typescript typescript-language-server`；
- 同时勾选时 `typescript` 只装一次。

### 步骤 3：AI 开发工具
- **OpenCode**：`curl -fsSL https://opencode.ai/install | bash`（`command -v opencode` 检测）。
- **Pi Agent**：`curl -fsSL https://pi.dev/install.sh | sh`（备选 `sudo npm install -g @earendil-works/pi-coding-agent`）。

### 步骤 4：Oracle Instant Client（供 python-oracledb thick 模式）
zip 包方式（两系通用）：
1. 下载最新 instantclient-basic 与 instantclient-sqlplus 的 Linux zip（按架构 `linux.x64`/`linux.arm64`，
   **真实直链**，阶段 2 核实；免登录可直下）。
2. 解压到 `/opt/oracle/instantclient_<版本>`，软链 `/opt/oracle/instantclient`。
3. `echo /opt/oracle/instantclient | sudo tee /etc/ld.so.conf.d/oracle-instantclient.conf` 后 `sudo ldconfig`。
4. 环境变量（写入 `/etc/profile.d/oracle-instantclient.sh`，并追加到 `~/.bashrc`，先 grep 防重复）：
   ```bash
   export ORACLE_HOME=/opt/oracle/instantclient
   export LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
   ```
5. 依赖：**[apt]** `sudo apt install -y libaio1`（或 `libaio1t64`）；**[dnf]** `sudo dnf install -y libaio`。
6. 验证：`python3 -c "import oracledb; oracledb.init_oracle_client(); print(oracledb.clientversion())"`
   （若用 venv 则用该 venv 的解释器路径）。

### 步骤 5：应用软件
统一安装到 `~/software/<软件名>/`；有 GUI 的注册 Desktop 条目
（`~/.local/share/applications/<name>.desktop`：Name/Exec/Icon/Type=Application/Categories），
最后 `update-desktop-database`（属 `desktop-file-utils` 包）。仅探测到桌面环境时写入此段。

1. **WindTerm**：下载 GitHub kingToolbox/WindTerm 最新 Linux `.tar.gz`（真实直链），解压到 `~/software/windterm`，注册 Desktop（图标取安装目录内 png）。
2. **Zed**：下载 GitHub zed-industries/zed 最新 Linux `.tar.gz`（真实直链，按架构确认资产存在），解压到 `~/software/zed`，注册 Desktop。
3. **Ghostty**：
   **[apt]**（Ubuntu/Debian；Mint 亦属 apt 分支但脚本按 Ubuntu 版本检测，失败属预期）
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh)"`；
   **[dnf]** 优先 Flatpak：`flatpak install flathub com.mitchellh.ghostty`（未装 flatpak 时先安装并加 flathub 源）。
4. **Sublime Text**：
   **[apt]** 按官方文档导入 GPG key 并添加 apt 仓库后 `sudo apt install -y sublime-text`；
   **[dnf]** 添加 `https://download.sublimetext.com/rpm/stable/x86_64/sublime-text.repo` 并导入同名 GPG key 后
   `sudo dnf install -y sublime-text`（官方仅 x86_64，**aarch64 机器标注"预期不支持"**）。
   文档中须给出官方仓库配置说明页的真实 URL。
5. **Dbx**：下载 GitHub t8y2/dbx 最新资产——**[apt]** 优先 `.deb`（`sudo apt install ./xxx.deb`）；
   **[dnf]** 优先 `.rpm`（`sudo dnf install ./xxx.rpm`）；均无则用 AppImage 放 `~/software/dbx` 并注册 Desktop。

### 步骤 6：主题与字体（两系通用）
1. **Sublime Text Ayu 主题**：`git clone https://github.com/dempfi/ayu` 到
   `~/.config/sublime-text/Packages/ayu`（先 `mkdir -p`），按其 README 在
   `Preferences.sublime-settings` 启用 dark 方案。
2. **Maple Mono 字体（NF CN 变体）**：下载 GitHub subframe7536/maple-font 最新 Release 中名称含
   `NF-CN` 的 zip（**真实直链**），解压取 `.ttf/.otf/.ttc` 到 `~/.local/share/fonts/maple-mono/`，
   `fc-cache -fv`，`fc-list` 验证。
3. **WindTerm Dracula 主题**：参照 `https://draculatheme.com/windterm` 说明，
   从 github.com/dracula/windterm 下载主题文件，放入 WindTerm 的 `global/themes` 目录并按说明启用。

### 步骤 7：Python 库（清华源）
用 >= 3.10 的解释器：
`pip install -r <清单> -i https://pypi.tuna.tsinghua.edu.cn/simple`。
- 依赖清单：**把本技能捆绑的 `scripts/requirements.txt` 内容原样作为代码块写入文档**
  （用户可一键复制成文件或直接 `pip install … -i …` 逐项安装）。
- 若遇 PEP 668（externally-managed-environment）：优先建 venv `python3 -m venv ~/venvs/main` 后安装
  （**[apt]** 需先 `sudo apt install -y python3-venv`），备选 `--break-system-packages`。
- pyodbc 系统依赖：**[apt]** `sudo apt install -y unixodbc-dev`；**[dnf]** `sudo dnf install -y unixODBC-devel`。
- `basedpyright` 随清单安装，可软链 `ln -sf ~/venvs/main/bin/basedpyright ~/.local/bin/basedpyright`。
- 注意：ruff 不在本清单中（走 2.6），不要重复通过 pip 安装。

### 步骤 8：Cron 定时任务（两系通用）
1. cron 前置：**[apt]** `sudo apt install -y cron && sudo systemctl enable --now cron`；
   **[dnf]** `sudo dnf install -y cronie && sudo systemctl enable --now crond`。
2. `mkdir -p ~/Desktop/Scripts ~/download-history`。
3. **把本技能捆绑的 `scripts/move-download.sh` 内容原样作为代码块写入文档**，
   并给出创建命令（`cat > ~/Desktop/Scripts/move-download.sh <<'EOF' … EOF` 或提示用户用编辑器粘贴后
   `chmod +x ~/Desktop/Scripts/move-download.sh`）。下载目录探测已内置（`xdg-user-dir DOWNLOAD` + 回退）。
4. 注册 crontab（先 `crontab -l` 检查避免重复）：
   ```
   0 1 * * * "$HOME/Desktop/Scripts/move-download.sh" >> "$HOME/Desktop/Scripts/move-download.log" 2>&1
   ```

### 步骤 9：Mint 专属（仅当 ID/ID_LIKE 含 linuxmint 时写入）
1. **WhiteSur GTK 主题**：`git clone https://github.com/vinceliuice/WhiteSur-gtk-theme` 后按其 README 运行 `./install.sh`（需 sassc 等依赖先装）。
2. **McMojave-circle 图标**：`git clone https://github.com/vinceliuice/McMojave-circle` 后运行 install.sh，
   或手动复制图标目录到 `~/.icons/`，再
   `gsettings set org.cinnamon.desktop.interface icon-theme McMojave-circle`。

### 步骤 10：常用 Alias（写入 `~/.bashrc`）
给出追加命令（注意 alias 值末尾空格有意保留），并提示 `source ~/.bashrc`：
```bash
alias oc='opencode '
alias dk='docker '
alias dc='docker compose'
alias fh='free -h'
```
写入文档时用"追加到 ~/.bashrc 末尾、先 grep 防重复"的完整命令块。

## 交付与自查

完成后：
1. 输出文档保存路径，并用 `computer://` 链接交付：`[装机指南](computer:///home/<user>/init-linux-guide-YYYYMMDD.html)`
   （用探测到的实际 `$HOME` 拼绝对路径）。
2. 口头简述：命中的发行版/包管理器分支、勾选了哪些可选组件、哪些步骤需要 sudo、
   哪些链接/资产未能核实为直链（已改为官方页面）。
3. **交付前自查清单**（逐项确认）：
   - [ ] 未执行任何安装/sudo 命令，仅做了只读探测；
   - [ ] 文档为单文件、离线可打开，CSS/JS 全内联；
   - [ ] 每个命令代码块都能出现「复制」按钮（标准 `<pre><code>` 即可，脚本自动注入）；
   - [ ] 只出现命中的包管理器分支命令；
   - [ ] 下载链接均为联网核实过的真实 URL，无臆造、无占位符；
   - [ ] 未勾选的可选组件未写入命令；
   - [ ] 提示了需 sudo / 需重新登录 / 需重启终端等事项。

## 捆绑资源

- `assets/guide-template.html` — HTML 外壳模板（内置样式 + 自动注入复制按钮的脚本）。
  复制该文件，替换 `{{TITLE}}`、`{{GENERATED_AT}}`、`{{ENV_SUMMARY}}`、`{{CONTENT}}` 占位符，
  写出到 `~/init-linux-guide-YYYYMMDD.html`。
- `scripts/requirements.txt` — 步骤 7 的 Python 依赖清单，**内容需原样嵌入 HTML 文档**（代码块）。
- `scripts/move-download.sh` — 步骤 8 的下载目录归档脚本，**内容需原样嵌入 HTML 文档**（代码块）。