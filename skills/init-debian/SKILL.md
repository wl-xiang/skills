---
name: init-debian
description: >
  This skill should be used when the user wants to initialize / set up a fresh
  Debian-based Linux machine (Ubuntu / Debian / Linux Mint, apt-based), e.g.
  "帮我初始化这台新机器", "一键装机", "init debian", "配置开发环境", "装一遍我的常用工具".
  It performs an idempotent, logged, resumable full-stack setup: base tools,
  Python/Node/Docker/Go runtimes, AI CLI tools, Oracle Instant Client, GUI apps
  with Desktop entries, themes & fonts, Python libraries, a Downloads cron job,
  and Mint-specific themes. It should NOT be used for single-package installs
  or non-Debian distros (RHEL/Fedora/Arch).
agent_created: true
---

# init-debian — Debian 系 Linux 一键装机

自动化装机助手。用于在全新安装的 Debian 系 Linux（Ubuntu / Debian / Linux Mint，基于 apt）上，
一键完成开发环境初始化。

## 总体执行要求（每一步都必须遵守）

1. **幂等性**：每一步执行前先检测目标是否已存在/已安装，已满足则跳过并记录，严禁重复安装或覆盖用户已有配置。
2. **健壮性**：所有脚本使用 `set -euo pipefail`；单步失败不中断整体流程，记录到日志文件
   `~/init-debian-YYYYMMDD.log`（YYYYMMDD 为当天日期），最后输出成功/失败汇总报告。
3. **权限**：需要 root 的步骤用 sudo；检测到无 sudo 权限时给出明确提示并终止相关步骤。
4. **版本探测**：所有"取最新版本"的步骤，执行时必须实时查询官方源（GitHub Releases API、官网下载页等）
   获取最新版本号，禁止写死版本号。GitHub API 访问不通时降级为解析 `releases/latest` 重定向。
5. **网络**：优先使用官方源；pip 统一使用清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。
6. **验证**：完成后逐项输出验证结果（版本号或安装路径）。

## 执行环境信息（执行前先收集）

- 读取 `/etc/os-release`，确认发行版 ID、VERSION_ID（区分 ubuntu / debian / linuxmint）。
- 检测 CPU 架构（`uname -m`，区分 x86_64 / aarch64）。
- 检测桌面环境是否存在（`$XDG_CURRENT_DESKTOP`），用于决定是否注册 Desktop 条目。

## 步骤 1：系统基础工具（apt 安装）

`apt update` 后安装：vim、git、curl、wget、jq、yq、ripgrep、bat、tree、zip、unzip、
build-essential、openssh-server、fd-find。

注意事项：
- Debian/Ubuntu 上 `fd` 包名是 `fd-find`，安装后建立软链 `ln -sf $(which fdfind) ~/.local/bin/fd`。
- `bat` 的二进制名为 `batcat`，同样软链为 `bat`（`ln -sf $(which batcat) ~/.local/bin/bat`）。
- 安装后启用并启动 ssh 服务（`systemctl enable --now ssh`）。

## 步骤 2：开发运行时

### 2.1 Python（>= 3.10）

按以下决策树执行：
1. 分别检测 `python --version` 和 `python3 --version`。
2. 若已有任一命令指向 >= 3.10 的版本：直接使用系统内置版本，跳过后续安装。
3. 若只有 `python3` 而没有 `python` 命令：`apt install python-is-python3` 建立映射。
4. 若系统 Python 版本 < 3.10 或完全未安装：
   - 查询 python.org 确定当前最新的 3.13.x 补丁版本号；
   - Ubuntu 优先用 deadsnakes PPA（`add-apt-repository ppa:deadsnakes/ppa` 后安装
     `python3.13 python3.13-venv python3.13-dev`）；
   - Debian 或无 PPA 时，从 python.org 下载源码编译安装到 /usr/local（`./configure --enable-optimizations`）。
   - 安装后验证 `python3.13 --version` >= 3.10，并保证 `python3` 命令指向可用的 >= 3.10 版本。

### 2.2 Node.js（24.x）

使用 NodeSource 官方脚本安装 Node.js 24：

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash - && sudo apt install -y nodejs
```

验证 `node -v` 主版本为 24。

### 2.3 Docker 与 Docker Compose

按 Docker 官方文档添加 apt 仓库（download.docker.com），安装 docker-ce、docker-ce-cli、
containerd.io、docker-buildx-plugin、docker-compose-plugin。
安装后：将当前用户加入 docker 组（`sudo usermod -aG docker $USER`，提醒需重新登录生效），
启用并启动 docker 服务。验证 `docker --version` 与 `docker compose version`。

### 2.4 Golang（最新稳定版）

查询 `https://go.dev/dl/?mode=json` 获取最新 stable 版本号，
下载 `go<版本>.linux-<arch>.tar.gz` 解压到 /usr/local/go，
并将 /usr/local/go/bin 加入 PATH（写入 `~/.profile` 或 `/etc/profile.d/go.sh`）。
验证 `go version`。

## 步骤 3：AI 开发工具（统一用 curl 拉取脚本 + bash 执行）

1. **OpenCode**：先 `command -v opencode` 检测，已安装则跳过；否则执行
   `curl -fsSL https://opencode.ai/install | bash`。
2. **Pi Agent**：先 `command -v pi` 检测，已安装则跳过；否则执行
   `curl -fsSL https://pi.dev/install.sh | sh`（备选：`npm install -g @earendil-works/pi-coding-agent`）。

## 步骤 4：Oracle Instant Client（供 python-oracledb thick 模式使用）

1. 从 Oracle 官网（download.oracle.com/otn_software/linux/instantclient/）查询并下载
   当前最新版 instantclient-basic 与 instantclient-sqlplus 的 Linux x64 zip 包
   （官网直链可直接 wget，无需登录）。
2. 解压到 `/opt/oracle/instantclient_<版本>`，并创建软链 `/opt/oracle/instantclient` 指向它。
3. 配置动态链接：向 `/etc/ld.so.conf.d/oracle-instantclient.conf` 写入 `/opt/oracle/instantclient`，执行 `ldconfig`。
4. 设置环境变量（两者都要）：
   - 创建 `/etc/profile.d/oracle-instantclient.sh`，内容：
     ```bash
     export ORACLE_HOME=/opt/oracle/instantclient
     export LD_LIBRARY_PATH=$ORACLE_HOME:$LD_LIBRARY_PATH
     ```
   - 同时追加同样的两行 export 到 `~/.bashrc` 末尾（追加前先 grep 检测是否已存在，避免重复写入）。
5. 安装系统依赖 libaio1（或 libaio1t64，视发行版而定）。
6. 验证（在步骤 6 的 pip 安装之后执行）：
   `python3 -c "import oracledb; oracledb.init_oracle_client(); print(oracledb.clientversion())"`

## 步骤 5：应用软件

统一安装到 `~/software/<软件名>/`，并为有 GUI 的软件注册 Desktop 条目
（`~/.local/share/applications/<name>.desktop`，含 Name、Exec、Icon、Type=Application、
Categories），最后 `update-desktop-database`。仅检测到桌面环境时执行 Desktop 注册。

通用规则：每个软件建独立子目录；从 GitHub Releases API 获取最新版本及对应架构的资产下载 URL。

1. **WindTerm**：从 github.com/kingToolbox/WindTerm 下载最新 Linux 版（.tar.gz），
   解压到 `~/software/windterm`，注册 Desktop（图标取其安装目录内的 png）。
2. **Zed**：从 github.com/zed-industries/zed 下载最新 Linux 版（.tar.gz，内含 zed 可执行文件与图标），
   解压到 `~/software/zed`，注册 Desktop。
3. **Ghostty**：执行社区 deb 源安装脚本
   `/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/mkasberg/ghostty-ubuntu/HEAD/install.sh)"`。
4. **Sublime Text**：添加 Sublime 官方 apt 仓库后安装（官方提供 deb 仓库）。
5. **Dbx**：从 github.com/t8y2/dbx 下载最新版 Linux 桌面端资产（优先 .deb，用 `apt install ./xxx.deb` 安装；
   无 deb 则用 AppImage 放 `~/software/dbx` 并注册 Desktop）。

## 步骤 6：主题与字体

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

用步骤 2.1 确认可用的 python3（>= 3.10）执行。依赖清单见本技能捆绑的
`scripts/requirements.txt`，写入临时文件后 `pip install -r`。

注意事项：
- 统一加清华镜像 `-i https://pypi.tuna.tsinghua.edu.cn/simple`。
- 若系统有 PEP 668 限制（externally-managed-environment），**优先创建 `~/venvs/main` 虚拟环境**
  后再安装（需先装 python3-venv）；备选 `pip install --break-system-packages`。
- pyodbc 需要系统依赖 `unixodbc-dev`；psycopg[binary] 与 fastparquet 依赖预编译轮子，失败时记录日志不中断。

## 步骤 8：Cron 定时任务

1. `mkdir -p ~/Desktop/Scripts ~/download-history`。
2. **探测下载目录**：目录名随系统默认语言而异（英文为 `~/Downloads`，中文系统为 `~/下载`）。
   优先用 `xdg-user-dir DOWNLOAD` 获取实际路径（xdg-user-dirs 未安装时 apt 安装它）；
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

## 步骤 10：常用 Alias（写入 ~/.bashrc）

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

全部步骤完成后输出结构化汇总：每步骤状态（✅成功 / ⚠️跳过 / ❌失败）、关键版本号或安装路径；
对失败的步骤给出失败原因和手动修复建议。

## 捆绑资源

- `scripts/requirements.txt` — 步骤 7 的 Python 依赖清单，直接复制到目标机后 `pip install -r`。
- `scripts/move-download.sh` — 步骤 8 的下载目录归档脚本（自动适配 Downloads/"下载" 目录名），
  直接复制到 `~/Desktop/Scripts/`。
