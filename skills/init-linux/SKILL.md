---
name: init-linux
description: >
  This skill should be used when the user wants to initialize / set up a fresh
  Linux machine, both DEB-based (Debian / Ubuntu / Linux Mint, apt) and
  RPM-based (Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux, dnf or yum),
  e.g. "帮我初始化这台新机器", "一键装机", "init linux", "配置开发环境",
  "装一遍我的常用工具". It performs an idempotent, logged, resumable full-stack
  setup: base tools, Python/Node/Docker/Go runtimes, AI CLI tools, Oracle
  Instant Client, GUI apps with Desktop entries, themes & fonts, Python
  libraries, a Downloads cron job, and Mint-specific themes. It should NOT be
  used for single-package installs or unsupported distros (Arch 等；openSUSE
  的 zypper 流程未完整覆盖，仅部分步骤可用).
agent_created: true
---

# init-linux — Linux 一键装机（DEB 系 + RPM 系）

自动化装机助手。用于在全新安装的 Linux 发行版上（DEB 系：Debian / Ubuntu / Linux Mint，基于 apt；
RPM 系：Fedora / RHEL / CentOS Stream / Rocky / AlmaLinux，基于 dnf，旧版回退 yum），
一键完成开发环境初始化。

## 总体执行要求（每一步都必须遵守）

1. **幂等性**：每一步执行前先检测目标是否已存在/已安装，已满足则跳过并记录，严禁重复安装或覆盖用户已有配置。
2. **健壮性**：所有脚本使用 `set -euo pipefail`；单步失败不中断整体流程，记录到日志文件
   `~/init-linux-YYYYMMDD.log`（YYYYMMDD 为当天日期），最后输出成功/失败汇总报告。
3. **权限**：需要 root 的步骤用 sudo；检测到无 sudo 权限时给出明确提示并终止相关步骤。
4. **版本探测**：所有"取最新版本"的步骤，执行时必须实时查询官方源（GitHub Releases API、官网下载页等）
   获取最新版本号，禁止写死版本号。GitHub API 访问不通时降级为解析 `releases/latest` 重定向。
5. **网络**：优先使用官方源；pip 统一使用清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。
6. **验证**：完成后逐项输出验证结果（版本号或安装路径）。
7. **失败跳过与汇总（硬性要求）**：单个软件/包安装失败时重试最多 3 次（网络类操作单次超时 5 分钟），
   重试与超时累计仍失败即把该项标记为 ⚠️跳过、记录失败原因，**继续执行后续流程，严禁整体中断**；
   全部流程结束后，把所有失败/跳过项（含原因与手动修复建议）汇总成 Markdown 报告
   保存为 `~/init-linux-report-YYYYMMDD.md`，并直接向用户口头说明哪些流程失败。

## 包管理器适配（全局规则，先于一切安装步骤执行）

读取 `/etc/os-release`，根据 ID 与 ID_LIKE 判定包管理器，后续所有安装命令按此分支选用：

| 判定 | 发行版 | 包管理器 |
|------|--------|----------|
| ID 或 ID_LIKE 含 `debian` | Debian / Ubuntu / Linux Mint | `apt` |
| ID 或 ID_LIKE 含 `fedora` / `rhel` / `centos` / `rocky` / `almalinux` | Fedora / RHEL 系 | `dnf`（检测不到 dnf 时回退 `yum`） |
| ID 或 ID_LIKE 含 `suse` | openSUSE 系 | `zypper`（仅基础工具可用，第三方仓库步骤需按各官方 openSUSE 文档调整） |

约定：下文用 **[apt]** 与 **[dnf]** 标注两类命令，执行时只运行命中的分支；
未标注的命令（curl 脚本、git、tar、pip 等）两种发行版通用。
openSUSE 不在完整支持范围内：基础工具可尝试 zypper，第三方源相关步骤直接标记 ⚠️跳过并记录原因。

## 执行环境信息（执行前先收集）

- 读取 `/etc/os-release`，确认发行版 ID、VERSION_ID 与包管理器分支（见上表）。
- 检测 CPU 架构（`uname -m`，区分 x86_64 / aarch64）。
  **架构命名映射**：`uname -m` 的输出与各项目发布资产命名不一致，拼下载 URL 前必须以目标项目
  的实际资产名为准做映射（如 Go 用 `amd64`/`arm64`，yq 用 `x86_64`/`arm64`，Oracle 用 `x64`/`arm64`），
  并在下载前先校验资产存在（HTTP HEAD 或 Releases API 资产列表），不存在则按总体要求第 7 条跳过。
- 检测桌面环境是否存在（`$XDG_CURRENT_DESKTOP`），用于决定是否注册 Desktop 条目。
- **统一前置**：`mkdir -p ~/.local/bin` 并确认该目录在 PATH 中（`echo $PATH` 检测，缺失时
  在 `~/.profile` 或 `~/.bashrc` 追加 `export PATH="$HOME/.local/bin:$PATH"`，追加前先 grep 防重复）。
  后续 yq、ruff、fd/bat 软链、basedpyright 软链等都写入此目录。

## 步骤 1：系统基础工具

- **[apt]**：`sudo apt update` 后
  `sudo apt install -y vim git curl wget jq ripgrep bat tree zip unzip build-essential openssh-server fd-find`。
- **[dnf]**：`sudo dnf install -y vim git curl wget jq ripgrep bat tree zip unzip gcc gcc-c++ make openssh-server fd-find`。

注意事项：
- **yq 统一从 GitHub Releases 安装**（mikefarah/yq 的 Go 版二进制，放到 `~/.local/bin` 并 `chmod +x`），
  不要使用 apt/dnf 源中的 `yq` 包——那是 Python 实现（kislyuk/yq），语法与 Go 版不兼容，两系行为会不一致。
  下载时按架构命名映射选择 `linux_amd64` / `linux_arm64` 资产。
- **[apt]** Debian/Ubuntu 上 `fd` 包名是 `fd-find`，`bat` 的二进制名是 `batcat`：安装后建立软链
  `ln -sf "$(command -v fdfind)" ~/.local/bin/fd` 与 `ln -sf "$(command -v batcat)" ~/.local/bin/bat`。
  **[dnf]** 源内包名即 `fd` 与 `bat`，二进制名正确，无需软链。
- `build-essential` 是 apt 包名；dnf 系用 `gcc gcc-c++ make` 等价替代。
- 启用并启动 SSH 服务：**[apt]** `systemctl enable --now ssh`；**[dnf]** `systemctl enable --now sshd`。

## 步骤 2：开发运行时

### 2.1 Python（>= 3.10）

按以下决策树执行：
1. 分别检测 `python --version` 和 `python3 --version`。
2. 若已有任一命令指向 >= 3.10 的版本：直接使用系统内置版本，跳过后续安装。
3. 若只有 `python3` 而没有 `python` 命令：
   **[apt]** `apt install python-is-python3` 建立映射；
   **[dnf]** Fedora 缺失时 `sudo dnf install -y python-unversioned-command` 建立映射；
   RHEL 系无此包时，先 `sudo dnf install -y python3`，再用
   `sudo alternatives --install /usr/bin/python python /usr/bin/python3 1`
   注册 alternatives 组后 `sudo alternatives --set python /usr/bin/python3` 建立映射。
4. 若系统 Python 版本 < 3.10 或完全未安装：
   - 查询 python.org 确定当前最新的 3.13.x 补丁版本号；
   - **[apt]** Ubuntu 优先用 deadsnakes PPA（`add-apt-repository ppa:deadsnakes/ppa` 后安装
     `python3.13 python3.13-venv python3.13-dev`）；Debian 或无 PPA 时，从 python.org 下载源码编译
     安装到 /usr/local（`./configure --enable-optimizations`）；
   - **[dnf]** Fedora 一般已满足版本；RHEL/Rocky/Alma 版本过低时优先从 python.org 源码编译
     （需先 `dnf install -y gcc make openssl-devel bzip2-devel libffi-devel zlib-devel readline-devel sqlite-devel`），
     备选方案按发行版官方文档启用对应软件集（如 EPEL 提供的新版 python3.x）。
   - 安装后验证 `python3.13 --version` >= 3.10。
     **注意**：不要改动系统默认 `python3` 的指向（apt 系的系统工具可能依赖旧版 python3，
     强切会导致 apt 相关脚本损坏）；步骤 7 及后续用到新解释器时，用 `python3.13` 显式路径，
     或用 `python3.13 -m venv` 创建虚拟环境承载。

### 2.2 Node.js（24.x）

- **[apt]** 使用 NodeSource 官方脚本：
  ```bash
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash - && sudo apt install -y nodejs
  ```
- **[dnf]** 使用 NodeSource RPM 源：
  ```bash
  curl -fsSL https://rpm.nodesource.com/setup_24.x | sudo bash - && sudo dnf install -y nodejs
  ```

验证 `node -v` 主版本为 24。

### 2.3 Docker 与 Docker Compose

按 Docker 官方文档添加对应发行版的官方仓库：

- **[apt]**（download.docker.com/linux/ubuntu 或 /debian）：安装 docker-ce、docker-ce-cli、
  containerd.io、docker-buildx-plugin、docker-compose-plugin。
- **[dnf]** 仓库 URL 按发行版选择：Fedora → `download.docker.com/linux/fedora`，
  CentOS/Rocky/Alma → `download.docker.com/linux/centos`，RHEL → `download.docker.com/linux/rhel`。
  添加仓库时先检测 dnf 主版本：
  - dnf5（Fedora 41+ 默认）：`sudo dnf config-manager addrepo --from-repofile=<docker-ce.repo 的 URL>`；
  - dnf4（旧版 Fedora/RHEL 系）：`sudo dnf install -y dnf-plugins-core` 后
    `sudo dnf config-manager --add-repo <docker-ce.repo 的 URL>`。
  然后 `sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin`。

安装后（两系通用）：将当前用户加入 docker 组（`sudo usermod -aG docker $USER`，提醒需重新登录生效），
启用并启动 docker 服务。验证 `docker --version` 与 `docker compose version`。

### 2.4 Golang（最新稳定版）

查询 `https://go.dev/dl/?mode=json` 获取最新 stable 版本号，
下载 `go<版本>.linux-<arch>.tar.gz`（`<arch>` 按架构命名映射取 `amd64`/`arm64`），
解压到 /usr/local/go：**若 `/usr/local/go` 已存在，先 `sudo rm -rf /usr/local/go` 删除旧版再解压**
（官方推荐的升级方式，避免新旧文件混杂；此为运行时目录，不受"严禁覆盖用户配置"约束）。
并将 /usr/local/go/bin 加入 PATH（写入 `~/.profile` 或 `/etc/profile.d/go.sh`），
写入前先 grep 检测是否已存在该 PATH 条目，避免重复追加。
验证 `go version`。（两系通用，无包管理器差异。）

### 2.5 Ruff（Python Linter / Formatter）

1. 先 `command -v ruff` 检测，已安装则跳过；
2. 否则执行官方安装脚本：`curl -LsSf https://astral.sh/ruff/install.sh | sh`；
3. 脚本默认安装到 `~/.local/bin`（需确认该目录在 PATH 中，通常已默认包含）；
4. 验证 `ruff --version`。（两系通用。）

## 步骤 3：AI 开发工具（统一用 curl 拉取脚本 + bash 执行，两系通用）

1. **OpenCode**：先 `command -v opencode` 检测，已安装则跳过；否则执行
   `curl -fsSL https://opencode.ai/install | bash`。
2. **Pi Agent**：先 `command -v pi` 检测，已安装则跳过；否则执行
   `curl -fsSL https://pi.dev/install.sh | sh`（备选：`npm install -g @earendil-works/pi-coding-agent`）。

## 步骤 4：Oracle Instant Client（供 python-oracledb thick 模式使用）

优先使用 zip 包方式（两系通用，避免 rpm/deb 包格式差异）：

1. 从 Oracle 官网（download.oracle.com/otn_software/linux/instantclient/）查询并下载
   当前最新版 instantclient-basic 与 instantclient-sqlplus 的 Linux zip 包
   （按执行环境检测到的 CPU 架构选择 `linux.x64` 或 `linux.arm64` 资产，直链可直接 wget，无需登录）。
2. 解压到 `/opt/oracle/instantclient_<版本>`，并创建软链 `/opt/oracle/instantclient` 指向它。
3. 配置动态链接：向 `/etc/ld.so.conf.d/oracle-instantclient.conf` 写入 `/opt/oracle/instantclient`，执行 `sudo ldconfig`。
4. 设置环境变量（两者都要）：
   - 创建 `/etc/profile.d/oracle-instantclient.sh`，内容：
     ```bash
     export ORACLE_HOME=/opt/oracle/instantclient
     export LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
     ```
   - 同时追加同样的两行 export 到 `~/.bashrc` 末尾（追加前先 grep 检测是否已存在，避免重复写入）。
5. 安装 libaio 系统依赖：**[apt]** `libaio1`（或 libaio1t64，视发行版而定）；**[dnf]** `libaio`。
6. 验证（在步骤 7 的 pip 安装之后执行，**必须使用步骤 7 实际使用的解释器**：
   步骤 7 走了 `~/venvs/main` 虚拟环境时用 `~/venvs/main/bin/python`，否则用系统 `python3`）：
   `<解释器> -c "import oracledb; oracledb.init_oracle_client(); print(oracledb.clientversion())"`

## 步骤 5：应用软件

统一安装到 `~/software/<软件名>/`，并为有 GUI 的软件注册 Desktop 条目
（`~/.local/share/applications/<name>.desktop`，含 Name、Exec、Icon、Type=Application、
Categories），最后 `update-desktop-database`。仅检测到桌面环境时执行 Desktop 注册；
`update-desktop-database` 属 `desktop-file-utils` 包（两系同名），缺失时先用包管理器安装，
装不上则跳过刷新（Desktop 条目通常仍会生效），按总体要求第 7 条记录。

通用规则：每个软件建独立子目录；从 GitHub Releases API 获取最新版本及对应架构的资产下载 URL；
下载前先校验目标架构的资产在 Releases 中确实存在（Zed 等项目已提供 ARM64 构建，仍需按实际资产列表确认），
不存在则按总体要求第 7 条跳过并记录，不得报错中断。

1. **WindTerm**：从 github.com/kingToolbox/WindTerm 下载最新 Linux 版（.tar.gz，两系通用），
   解压到 `~/software/windterm`，注册 Desktop（图标取其安装目录内的 png）。
2. **Zed**：从 github.com/zed-industries/zed 下载最新 Linux 版（.tar.gz，两系通用），
   解压到 `~/software/zed`，注册 Desktop。
3. **Ghostty**：
   **[apt]**（Ubuntu/Debian；Mint 属 apt 分支但该脚本按 Ubuntu 版本检测，失败属预期，
   按总体要求第 7 条跳过即可）执行社区 deb 源安装脚本
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh)"`；
   **[dnf]** 无官方 RPM 仓库：优先尝试 Flatpak（`flatpak install flathub com.mitchellh.ghostty`，
   未装 flatpak 时先安装并添加 flathub 远程源），失败则记录日志标记跳过。
4. **Sublime Text**：添加官方仓库后安装——
   **[apt]** 使用官方 apt 仓库（download.sublimetext.com 的 apt 源，按官方文档导入 GPG key 后安装 sublime-text）；
   **[dnf]** 使用官方 RPM 仓库
   (`https://download.sublimetext.com/rpm/stable/x86_64/sublime-text.repo`，导入同名 GPG key 后
   `dnf install -y sublime-text`)。
5. **Dbx**：从 github.com/t8y2/dbx 下载最新版 Linux 桌面端资产——
   **[apt]** 优先 .deb（`sudo apt install ./xxx.deb`）；**[dnf]** 优先 .rpm（`sudo dnf install ./xxx.rpm`）；
   两者都无对应格式时，用 AppImage 放 `~/software/dbx` 并注册 Desktop。

## 步骤 6：主题与字体（两系通用）

1. **Sublime Text Ayu 主题**：`git clone https://github.com/dempfi/ayu` 到 Sublime 的 Packages 目录
   （`~/.config/sublime-text/Packages/ayu`，目录不存在则先创建），
   并按 ayu 官方 README 说明在 Preferences.sublime-settings 中启用 ayu 配色（dark 方案）。
2. **Maple Mono 字体（NF CN 变体）**：从 github.com/subframe7536/maple-font 的 Releases 下载
   名称含 "NF-CN" 的 zip 包（hinted/unhinted 任选其一），解压后仅取其中的 .ttf/.otf/.ttc 字体文件
   复制到 `~/.local/share/fonts/maple-mono/`，执行 `fc-cache -fv`，并用 `fc-list` 验证安装成功。
3. **WindTerm Dracula 主题**：参照 https://draculatheme.com/windterm 的安装说明，
   从 github.com/dracula/windterm 下载主题文件，放入 WindTerm 安装目录下对应的 global/themes 目录，
   并按说明修改 WindTerm 的 profile/theme 配置使其生效。

## 步骤 7：Python 库（清华源）

用步骤 2.1 确认可用的 Python（>= 3.10）执行：优先用新装的显式解释器（如 `python3.13`），
否则用系统 `python3`。依赖清单直接使用本技能捆绑的 `scripts/requirements.txt`
（`pip install -r <技能目录>/scripts/requirements.txt`），无需复制到临时文件。

注意事项：
- 统一加清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。
- 若系统有 PEP 668 限制（externally-managed-environment，apt 与 dnf 两系均可能强制启用），
  **优先创建 `~/venvs/main` 虚拟环境**后再安装
  （**[apt]** 需先装 python3-venv；**[dnf]** venv 内置于 python3，无需额外包）；
  备选 `pip install --break-system-packages`。
- pyodbc 需要系统 ODBC 依赖：**[apt]** `unixodbc-dev`；**[dnf]** `unixODBC-devel`。
- psycopg[binary] 与 fastparquet 依赖预编译轮子，失败时记录日志不中断。
- `basedpyright`（Python 静态类型检查 / LSP）随清单一起通过 pip 安装；
  若装进了 `~/venvs/main` 虚拟环境，验证时用该 venv 内的路径（`~/venvs/main/bin/basedpyright --version`），
  可按需创建软链 `ln -sf ~/venvs/main/bin/basedpyright ~/.local/bin/basedpyright` 方便全局调用。
  注意：ruff 不在本清单中（它走 2.5 的官方脚本安装），不要重复通过 pip 安装。

## 步骤 8：Cron 定时任务（两系通用）

0. 前置检测：`command -v crontab` 检测 cron 是否可用；**[apt]** 缺失时 `sudo apt install -y cron`
   并 `systemctl enable --now cron`；**[dnf]** 缺失时 `sudo dnf install -y cronie`
   并 `systemctl enable --now crond`。
1. `mkdir -p ~/Desktop/Scripts ~/download-history`。
2. **探测下载目录**：目录名随系统默认语言而异（英文为 `~/Downloads`，中文系统为 `~/下载`）。
   优先用 `xdg-user-dir DOWNLOAD` 获取实际路径（xdg-user-dirs 未安装时用系统包管理器安装它）；
   探测失败时依次回退检测 `~/Downloads`、`~/下载`。
3. 安装 `~/Desktop/Scripts/move-download.sh`（内容见本技能捆绑的 `scripts/move-download.sh`，
   已内置 xdg-user-dir 探测与回退逻辑；复制过去并 `chmod +x`；若目标已存在则跳过，严禁覆盖用户修改）。
4. 注册到当前用户 crontab（先 `crontab -l` 检查是否已有相同条目，避免重复添加）：

```
0 1 * * * "$HOME/Desktop/Scripts/move-download.sh" >> "$HOME/Desktop/Scripts/move-download.log" 2>&1
```

## 步骤 9：Mint 专属（仅当 /etc/os-release 的 ID 或 ID_LIKE 包含 linuxmint 时执行）

1. **WhiteSur GTK 主题**：`git clone https://github.com/vinceliuice/WhiteSur-gtk-theme` 后按其 README
   运行 `./install.sh`（默认安装到 ~/.themes），需要 sassc 等依赖则先 apt 安装。
2. **McMojave-circle 图标**：`git clone https://github.com/vinceliuice/McMojave-circle` 后运行其 install.sh，
   或手动将图标主题目录复制到 `~/.icons/`，然后
   `gsettings set org.cinnamon.desktop.interface icon-theme McMojave-circle`
   （或用 mint-themes 工具）设置为 McMojave-circle。

## 步骤 10：常用 Alias（写入 ~/.bashrc，两系通用）

将以下别名追加到 `~/.bashrc` **末尾**。追加前先逐条 `grep -q` 检测（如 `grep -q "alias oc=" ~/.bashrc`），
已存在的条目跳过，严禁重复写入：

```bash
alias oc='opencode '
alias dk='docker '
alias dc='docker compose'
alias fh='free -h'
```

追加完成后执行 `source ~/.bashrc` 使其在当前会话生效，并提醒用户：新开的终端会自动加载；
注意 alias 值末尾的空格是有意保留的（便于 `oc`/`dk` 后直接接参数），写入时不要丢失。

## 输出要求

全部步骤完成后输出结构化汇总：每步骤状态（✅成功 / ⚠️跳过 / ❌失败）、命中的包管理器分支、
关键版本号或安装路径；对失败的步骤给出失败原因和手动修复建议。

## 捆绑资源

- `scripts/requirements.txt` — 步骤 7 的 Python 依赖清单，直接复制到目标机后 `pip install -r`。
- `scripts/move-download.sh` — 步骤 8 的下载目录归档脚本（自动适配 Downloads/"下载" 目录名），
  直接复制到 `~/Desktop/Scripts/`。
