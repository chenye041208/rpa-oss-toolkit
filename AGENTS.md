# AGENTS.md — rpa-oss-toolkit 项目约束

## 项目概述

阿里云 OSS 工具包（`rpa-oss-toolkit`），基于会话机制的 OSS 操作库，专为 RPA 流程设计。

- **⚠️ 非官方包**：个人开发，底层基于 `oss2` 封装
- Python 3，依赖 `oss2>=2.18.0`，MIT 许可
- 项目路径（WSL）：`/home/chenye/code/sdk/阿里云OSS库`
- GitHub：`https://github.com/chenye041208/rpa-oss-toolkit`
- PyPI：`https://pypi.org/project/rpa-oss-toolkit/`

## 项目结构

```
rpa-oss-toolkit/
├── .github/workflows/
│   ├── ci.yml                          # 单元测试 CI（push/PR 到 master）
│   └── pypi-publish.yml                # tag 触发自动发布到 PyPI
├── .gitattributes                      # 统一 LF 换行
├── .gitignore                          # 根白名单模式
├── AGENTS.md                           # 本文件（项目约束）
├── README.md                           # 项目入口文档（概览）
├── LICENSE                             # MIT
└── main/                               # 源码与打包目录
    ├── setup.py                        # 包配置（setuptools-scm 版本）
    ├── requirements.txt                # 运行依赖
    ├── requirements-dev.txt            # 开发依赖（-r requirements.txt + pytest）
    ├── pytest.ini                      # 测试配置（默认排除 integration）
    ├── .env.example                    # OSS 凭据模板（复制为 main/.env）
    ├── .gitignore                      # main 内忽略规则（.env/构建产物/缓存）
    ├── docs/使用文档.md                 # 唯一完整使用手册
    ├── rpa_oss_toolkit/                # 源码包（import 名）
    │   ├── __init__.py                 # 入口，importlib.metadata 获取版本
    │   ├── client.py                   # OSSClient + Session
    │   ├── operations.py               # OSS 底层操作
    │   ├── logger.py                   # 操作日志器
    │   ├── config.py                   # 配置管理器
    │   ├── exceptions.py               # 异常体系
    │   └── utils.py                    # 工具函数
    └── tests/                          # 测试
```

版本文档（`v*.md`）机制已废除，版本历史以 git tag 与提交记录为准。

## 开发环境（WSL）

- 虚拟环境：`venv/bin/python`（WSL 内重建，勿用 Windows 布局的 `venv/Scripts/`）
- WSL 系统 Python：`python3`（3.14，无 pip，pip 从 `/usr/share/python-wheels/pip-*.whl` 引导）
- venv 重建方法：`python3 -m venv --without-pip venv && venv/bin/python /usr/share/python-wheels/pip-*.whl/pip install pip`
- 开发依赖安装：`venv/bin/pip install -r main/requirements-dev.txt && venv/bin/pip install -e main/`
- pip 一律走国内镜像直连（如 `https://mirrors.aliyun.com/pypi/simple/`），禁止走代理；GitHub 直连可用

## 代码规范

- **无注释原则**：只写 WHY 不写 WHAT，函数名自解释
- **异常体系**：所有自定义异常继承 `OSSError`，精确到操作类型
- **配置管理**：`ConfigManager` 集中管理
- **日志**：操作日志缓冲写入 OSS（50 条阈值），不自留本地日志文件
- **换行符**：统一 LF（`.gitattributes` 已强制 `eol=lf`）

## 版本管理

版本号由 **git tag** 管理（`setuptools-scm`），不再硬编码，也没有版本文档。

- 版本号格式：`v{major}.{minor}.{patch}`
- `main/setup.py`：`use_scm_version=True`，不写 version
- `__init__.py`：`importlib.metadata.version("rpa-oss-toolkit")` 动态获取

### 发版步骤

```bash
# 1. 提交代码
git add -A
git commit -m "feat: xxxxx"

# 2. 打 tag 并推送（触发自动发布）
git tag v1.x.x
git push origin v1.x.x
```

打 tag 推送到 GitHub 后，**Actions 自动构建并上传到 PyPI**，无需手动操作。

## Git 工作流

- **白名单模式**：根 `.gitignore` 用 `/*` + `!/main/` 等放行行只跟踪必要文件；新增顶层需跟踪文件时同步加白名单
- **提交信息格式**：`type: 简短描述`（feat/fix/docs/refactor/test/chore）
- **分支策略**：直接推送 master（单人项目）

## GitHub Actions

### CI（单元测试）

工作流：`.github/workflows/ci.yml`，push / PR 到 master 时触发：

1. checkout（`fetch-depth: 0`，editable 安装靠 setuptools-scm 从 git tag 推版本）
2. 安装 `main/requirements-dev.txt`，再 `pip install -e .`
3. `pytest -v`（默认排除 integration）

### 自动发布到 PyPI

触发条件：推送 `v*` 格式的 tag

工作流：`.github/workflows/pypi-publish.yml`
1. checkout 代码（含 tags）
2. 安装 build + twine + setuptools-scm
3. `python -m build main/`（自动从 git tag 获取版本）
4. `twine upload main/dist/*` 到 PyPI（使用 `PYPI_API_TOKEN` 密钥）

需要在 GitHub 仓库 Settings → Secrets 中配置 `PYPI_API_TOKEN`。

## 推送到 GitHub（SSH deploy key）

remote 已配置为 SSH 别名 `git@github.com-rpa-oss`，直接 `git push` 即可（直连，无需代理）。

- 密钥：`.ssh/rpa-oss-deploy-key`（仓库 deploy key，带写权限，被 .gitignore 忽略不入库）
- 别名定义：`~/.ssh/config` 的 `Host github.com-rpa-oss`，IdentityFile 指向上述密钥
- 密钥失效时：GitHub 仓库 Settings → Deploy keys 重新添加 `.ssh/rpa-oss-deploy-key.pub`

## 测试

- **安装开发依赖**：`venv/bin/pip install -r main/requirements-dev.txt`（含 pytest）
- **单元测试**：`cd main && ../venv/bin/python -m pytest -v`（`main/pytest.ini` 默认 `-m "not integration"`，集成测试被 deselect）
- **集成测试**：需 `main/.env` 中的真实 OSS 凭据（参考 `main/.env.example`），`cd main && ../venv/bin/python -m pytest -m integration -v`
- **测试范围**：utils / config / exceptions / client(mock) / integration

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-28 | 包重命名 aliyunoss_rpa → rpa-oss-toolkit |
| 2026-04-28 | GitHub 仓库重命名 aliyunoss_rpa → rpa-oss-toolkit |
| 2026-04-28 | 改用 setuptools-scm + git tag 版本管理 |
| 2026-04-28 | 添加 GitHub Actions 自动发布到 PyPI |
| 2026-04-28 | 添加 long_description，PyPI 显示项目描述 |
| 2026-07-30 | 项目迁移至 WSL（`~/code/sdk/`），venv 重建，统一 LF 换行 |
| 2026-09-17 | 仓库结构调整：main/ 单体布局，测试入库，CI 分层，废除版本文档，新增 MIT LICENSE |
