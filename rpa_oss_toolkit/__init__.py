"""
阿里云 OSS 库

基于会话机制的阿里云 OSS 操作库，支持操作日志自动写入 OSS 远程存储。
专为 RPA 流程设计，提供简单易用的文件操作接口。

主要功能：
    - 会话机制：先创建会话验证连接，后续操作通过会话执行
    - 操作日志：所有操作记录实时写入 OSS 日志文件
    - CRUD 完整：上传、下载、删除、列举、复制、元数据操作
    - 分片传输：大文件自动分片上传/下载
    - 元数据验证：支持 Content-Type、Content-Disposition、Cache-Control 校验

使用示例：
    from rpa_oss_toolkit import OSSClient

    # 创建会话
    session = OSSClient.create_session(
        access_key_id="your_ak",
        access_key_secret="your_sk",
        endpoint="oss-cn-hangzhou.aliyuncs.com",
        bucket="your_bucket",
        session_name="RPA流程A"
    )

    # 上传文件
    session.upload("本地文件.txt", "上传路径/文件.txt")

    # 下载文件
    session.download("下载路径/文件.txt", "本地保存.txt")

    # 列举文件
    files = session.list("prefix/")

    # 获取下载链接
    url = session.get_url("文件.txt", expires=3600)

    # 删除文件
    session.delete("文件.txt")

    # 关闭会话
    session.close()

或使用上下文管理器：
    with OSSClient.create_session(
        access_key_id="your_ak",
        access_key_secret="your_sk",
        endpoint="oss-cn-hangzhou.aliyuncs.com",
        bucket="your_bucket",
        session_name="RPA流程A"
    ) as session:
        session.upload("本地文件.txt", "上传路径/文件.txt")
"""

__version__ = "1.1.4"

# 客户端与会话
from .client import OSSClient, Session

# 异常
from .exceptions import (
    OSSError,
    ValidationError,
    SessionError,
    SessionExpiredError,
    OperationError,
    UploadError,
    DownloadError,
    DeleteError,
    ListError,
    CopyError,
    MetadataError,
    LogError,
    ConfigError,
)

# 公共接口
__all__ = [
    # 版本
    "__version__",
    # 客户端
    "OSSClient",
    "Session",
    # 异常
    "OSSError",
    "ValidationError",
    "SessionError",
    "SessionExpiredError",
    "OperationError",
    "UploadError",
    "DownloadError",
    "DeleteError",
    "ListError",
    "CopyError",
    "MetadataError",
    "LogError",
    "ConfigError",
]
