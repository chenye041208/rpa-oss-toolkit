# RPA OSS Toolkit

> ⚠️ **非官方工具包**：本库是个人开发的阿里云 OSS 工具包，并非阿里云官方出品。底层基于 `oss2` 封装。

基于会话机制的阿里云 OSS 操作库，专为 RPA 流程设计，支持操作日志自动写入 OSS 远程存储。

## 核心特性

- **会话机制**：先创建会话验证连接，后续操作通过会话执行
- **操作日志**：所有操作记录实时写入 OSS 日志文件
- **CRUD 完整**：上传、下载、删除、列举、复制、元数据操作
- **分片传输**：大文件自动分片上传/下载
- **RPA 兼容**：Session 对象可直接传递给 RPA 组件

---

## 快速开始

### 安装

```bash
pip install rpa-oss-toolkit
```

依赖：`oss2>=2.0.0`

### 基本使用

```python
from rpa_oss_toolkit import OSSClient

# 1. 创建会话
session = OSSClient.create_session(
    access_key_id="你的AccessKey ID",
    access_key_secret="你的AccessKey Secret",
    endpoint="oss-cn-shenzhen.aliyuncs.com",
    bucket="你的Bucket名称",
    session_name="RPA流程A"
)

# 2. 上传文件
session.upload("本地文件.txt", "上传路径/文件.txt")

# 3. 下载文件
session.download("下载路径/文件.txt", "本地保存.txt")

# 4. 列举文件
files = session.list("prefix/")
for f in files:
    print(f)

# 5. 获取下载链接
url = session.get_url("文件.txt", expires=3600)

# 6. 判断文件存在
if session.exists("文件.txt"):
    print("文件存在")

# 7. 删除文件
session.delete("文件.txt")

# 8. 关闭会话
session.close()
```

或使用上下文管理器（推荐）：

```python
with OSSClient.create_session(
    access_key_id="your_ak",
    access_key_secret="your_sk",
    endpoint="oss-cn-shenzhen.aliyuncs.com",
    bucket="your_bucket",
    session_name="RPA流程A"
) as session:
    session.upload("test.pdf", "docs/test.pdf")
    url = session.get_url("docs/test.pdf")
    print(url)
# 会话自动关闭
```

---

## API 列表

### OSSClient.create_session()

创建会话，验证连接后返回 Session 对象。

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| access_key_id | str | 是 | 阿里云 AccessKey ID |
| access_key_secret | str | 是 | 阿里云 AccessKey Secret |
| endpoint | str | 是 | OSS 地域节点，如 oss-cn-shenzhen.aliyuncs.com |
| bucket | str | 是 | Bucket 名称 |
| session_name | str | 是 | 会话名称（用于日志文件名标识） |

### Session 方法

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| upload | local_path, remote_key | bool | 上传文件 |
| download | remote_key, local_path | bool | 下载文件 |
| delete | remote_key | bool | 删除文件 |
| list | prefix | list | 列举文件 |
| copy | src_key, dst_key | bool | 复制文件 |
| exists | remote_key | bool | 判断文件存在 |
| get_url | remote_key, expires | str | 获取签名下载链接 |
| get_metadata | remote_key | dict | 获取文件元数据 |
| set_metadata | remote_key, metadata | bool | 设置文件元数据 |
| flush_logs | - | - | 手动刷新日志 |
| get_config | key | dict / 值 | 获取当前配置（key 为空返回全部） |
| set_config | **kwargs | - | 修改配置项（如 buffer_size=100） |
| close | - | - | 关闭会话 |

---

## 日志机制

### 日志文件位置

```
{log_prefix}{yyyy-mm-dd}.log
例如：logs/2026-04-22.log
```

### 日志内容格式

每行一个操作记录：

```
[20260422-10:30:00.123][RPA流程A]：操作 upload 文件 docs/test.pdf 成功
[20260422-10:31:00.456][RPA流程A]：操作 delete 文件 docs/test.pdf 成功
```

### 工作原理

```
操作产生 → 内存缓冲区(50条) → 追加写入OSS日志文件
```

- 攒够 50 条日志后自动写入 OSS
- 关闭会话时自动刷新剩余日志
- 使用 `append_object` 追加写入，不覆盖旧日志
- 多会话并发时通过 lock 文件防冲突

---

## 目录结构

```
rpa_oss_toolkit/
├── __init__.py      # 包入口
├── client.py        # OSSClient 工厂类 + Session 会话类
├── operations.py    # OSS 底层操作
├── logger.py        # 操作日志器
├── config.py        # 配置管理器
├── exceptions.py    # 异常类
├── utils.py         # 工具函数
└── v1.1.1.md        # 当前版本文档

docs/                # 各版本发布说明
├── v1.0.0.md
├── v1.1.0.md
└── v1.1.1.md

requirements.txt     # 依赖
setup.py             # 包配置
```

---

## 异常处理

```python
from rpa_oss_toolkit import OSSClient, UploadError, SessionError

try:
    session = OSSClient.create_session(...)
    session.upload("test.pdf", "docs/test.pdf")
except SessionError as e:
    print(f"会话错误: {e}")
except UploadError as e:
    print(f"上传错误: {e}")
```

完整异常体系见 `rpa_oss_toolkit/exceptions.py`。

---

## 配置项

通过 `ConfigManager` 集中管理，支持运行时动态修改：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `log_prefix` | `"logs/"` | 日志文件 OSS 路径前缀 |
| `log_buffer_size` | `50` | 日志缓冲区大小（条） |
| `min_multithread_size` | `5242880` (5MB) | 分片传输阈值 |
| `max_retry_count` | `3` | 分片传输最大重试次数 |
| `retry_delay` | `2s` | 首次重试延迟（指数退避） |
| `default_expires_in` | `3600` (1小时) | 会话默认有效期 |

运行时修改配置：

```python
# 查看当前配置
session.get_config()
# -> {"log_prefix": "logs/", "log_buffer_size": 50, ...}

# 修改单条
session.set_config(log_buffer_size=100)

# 批量修改
session.set_config(max_retry_count=5, retry_delay=3)
```

完整默认值见 `rpa_oss_toolkit/config.py`。
