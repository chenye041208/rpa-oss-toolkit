"""
阿里云 OSS 库 - 自定义异常

本模块定义库特有的异常类型，继承自 OSSError 基类。
使用自定义异常可以更精确地捕获和处理特定类型的错误。
"""


class OSSError(Exception):
    """
    异常基类

    所有本库自定义异常的父类，继承自 Python 内置 Exception。
    可用于捕获所有本库相关的异常。
    """
    pass

class ValidationError(OSSError):
    """
    参数校验失败

    当传入的参数不符合要求时抛出此异常。
    例如：AK/SK 为空、endpoint 格式错误、session_name 不合法等。
    """
    pass

class SessionError(OSSError):
    """
    会话创建或验证失败

    当创建会话时连接验证失败，或会话状态异常时抛出此异常。
    例如：AK/SK 错误、无法连接到 OSS、Bucket 不存在等。
    """
    pass

class SessionExpiredError(SessionError):
    """
    会话已过期

    当会话超过有效期后尝试使用会抛出此异常。
    """
    pass

class OperationError(OSSError):
    """
    操作执行失败（基类）

    当 OSS 操作执行失败时抛出此异常。
    具体操作失败请使用以下子类。
    """
    pass

class UploadError(OperationError):
    """
    上传失败

    当文件上传到 OSS 失败时抛出此异常。
    可能原因：网络中断、权限不足、文件不存在等。
    """
    pass

class DownloadError(OperationError):
    """
    下载失败

    当从 OSS 下载文件失败时抛出此异常。
    可能原因：文件不存在、网络中断、磁盘空间不足等。
    """
    pass

class DeleteError(OperationError):
    """
    删除失败

    当删除 OSS 上的文件失败时抛出此异常。
    可能原因：文件不存在、权限不足等。
    """
    pass

class ListError(OperationError):
    """
    列举失败

    当列举 OSS 上的文件失败时抛出此异常。
    可能原因：目录不存在、网络中断等。
    """
    pass

class CopyError(OperationError):
    """
    复制失败

    当复制 OSS 上的文件失败时抛出此异常。
    可能原因：源文件不存在、目标路径不合法、权限不足等。
    """
    pass

class MetadataError(OSSError):
    """
    元数据验证失败

    当设置的元数据不符合 OSS 规范时抛出此异常。
    可能原因：Content-Type 错误、Cache-Control 格式错误、总大小超过 8KB 等。
    """
    pass

class LogError(OSSError):
    """
    日志操作失败

    当日志写入 OSS 失败时抛出此异常。
    可能原因：网络中断、权限不足等。
    """
    pass
