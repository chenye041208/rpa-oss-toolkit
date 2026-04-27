"""
阿里云 OSS 库 - 操作日志器

本模块负责记录所有 OSS 操作日志，并将日志追加写入 OSS 远程存储。

设计原理：
    操作产生 → 内存缓冲区(Buffer) → 定期/定量 → 追加写入OSS

日志文件存储在 OSS，格式：{LOG_PREFIX}{date}_{session_name}.log
每条日志为 JSON Lines 格式，便于解析和检索。

主要功能：
    - 操作日志缓冲（内存缓冲区，减少网络 IO）
    - 追加写入 OSS（使用 append_object）
    - 缓冲区自动刷新（达到阈值时）
    - 手动刷新（flush）
    - 显式关闭时刷新（close）
"""

import oss2
import datetime
from typing import List

from .config import LOG_BUFFER_SIZE, LOG_PREFIX
from .exceptions import LogError


class OperationLogger:
    """
    操作日志器

    将 OSS 操作日志追加写入 OSS 远程存储，不在本地保存。
    使用内存缓冲区减少网络 IO，攒够一定数量后自动写入。

    使用示例：
        logger = OperationLogger(bucket, "logs/")
        logger.log("upload", {"file": "a.txt", "status": "success"})
        logger.log("download", {"file": "b.txt", "status": "success"})
        logger.flush()  # 手动刷新
        logger.close() # 关闭时刷新剩余日志
    """

    def __init__(
        self,
        bucket,
        session_name: str,
        log_prefix: str = LOG_PREFIX,
        buffer_size: int = LOG_BUFFER_SIZE
    ):
        """
        初始化操作日志器

        :param bucket: oss2.Bucket 实例
        :param session_name: 会话名称（用于日志文件名）
        :param log_prefix: 日志路径前缀，默认 "logs/"
        :param buffer_size: 缓冲区大小（条），达到该数量自动刷新到OSS，默认 50 条
        """
        self._bucket = bucket
        self._session_name = session_name
        self._log_prefix = log_prefix
        self._buffer_size = buffer_size

        # 内存缓冲区
        self._buffer: List[str] = []

        # 日志文件名
        self._log_filename = self._generate_log_filename()

        # OSS 上文件的当前 position（用于追加写入）
        self._next_position = self._get_existing_file_length()

    @property
    def log_filename(self) -> str:
        """
        获取日志文件名

        :return: 日志文件名，格式 {date}.log
        """
        return self._log_filename

    @property
    def lock_filename(self) -> str:
        """
        获取 lock 文件名

        :return: 固定为 "lock"
        """
        return "lock"

    def log(self, content: str):
        """
        记录一条日志文本

        :param content: 日志文本内容

        示例：
            logger.log("这是一条日志")
        """
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y%m%d-%H:%M:%S") + f".{now.microsecond // 1000:03d}"
        entry = f"[{timestamp}][{self._session_name}]：{content}\n"
        self._buffer.append(entry)

        # 达到阈值自动刷新
        if len(self._buffer) >= self._buffer_size:
            self.flush()

    def flush(self):
        """
        将缓冲区中的日志刷新到 OSS

        使用 append_object 追加写入，不覆盖已有内容。
        写入前检查 lock 文件，写入成功后清空缓冲区。
        """
        if not self._buffer:
            return

        # 检查 lock 文件是否存在
        self._check_lock()

        # 合并所有日志条目
        content = "".join(self._buffer)
        content_bytes = content.encode('utf-8')

        # 创建 lock
        self._create_lock()

        # 追加写入 OSS
        self._append_to_oss(content_bytes)

        # 删除 lock
        self._delete_lock()

        # 清空缓冲区
        self._buffer.clear()

    def close(self):
        """
        关闭日志器，刷新剩余日志到 OSS

        确保所有缓冲区中的日志都被写入 OSS。
        调用后日志器不能再使用。

        注意：不推荐依赖 __del__ 自动调用，请显式调用 close()。
        Session 关闭时会自动调用此方法。
        """
        if self._buffer:
            self.flush()

    def _generate_log_filename(self) -> str:
        """
        生成日志文件名

        格式：{yyyy-mm-dd}.log
        例如：2026-04-22.log

        :return: 日志文件名
        """
        now = datetime.datetime.now()
        date_str = f"{now.year}-{now.month:02d}-{now.day:02d}"
        return f"{date_str}.log"

    def _get_existing_file_length(self) -> int:
        """
        获取 OSS 上已存在日志文件的长度

        如果文件不存在则返回 0（从头开始写）。

        :return: 文件字节长度，不存在则返回 0
        """
        key = f"{self._log_prefix}{self._log_filename}"
        try:
            meta = self._bucket.head_object(key)
            return meta.content_length
        except oss2.exceptions.NoSuchKey:
            return 0
        except Exception:
            return 0

    def _check_lock(self):
        """
        检查 lock 文件是否存在

        :raises LogError: lock 文件存在时被占用
        """
        key = f"{self._log_prefix}{self.lock_filename}"
        if self._bucket.object_exists(key):
            # 读取 lock 文件内容
            try:
                result = self._bucket.get_object(key)
                content = result.read().decode('utf-8')
                raise LogError(f"日志文件被占用，当前占用者：{content}")
            except LogError:
                raise
            except Exception as e:
                raise LogError(f"日志文件被占用，读取 lock 文件失败：{str(e)}")

    def _create_lock(self):
        """
        创建 lock 文件

        lock 文件内容：{session_name}|using
        """
        key = f"{self._log_prefix}{self.lock_filename}"
        content = f"{self._session_name}|using".encode('utf-8')
        try:
            self._bucket.put_object(key, content)
        except Exception as e:
            raise LogError(f"创建 lock 文件失败: {str(e)}")

    def _delete_lock(self):
        """
        删除 lock 文件
        """
        key = f"{self._log_prefix}{self.lock_filename}"
        try:
            self._bucket.delete_object(key)
        except Exception:
            pass

    def _append_to_oss(self, content_bytes: bytes):
        """
        追加写入 OSS 日志文件

        :param content_bytes: 要写入的字节内容
        :raises LogError: 写入失败时抛出
        """
        key = f"{self._log_prefix}{self._log_filename}"

        # 获取当前文件长度作为 position
        position = self._get_existing_file_length()

        try:
            result = self._bucket.append_object(key, position, content_bytes)
            self._next_position = result.next_position
        except Exception as e:
            raise LogError(f"日志写入OSS失败: {str(e)}")

    def __del__(self):
        """
        析构时自动刷新缓冲区（不推荐依赖）

        由于 Python 的垃圾回收机制不保证在所有情况下都能执行此方法，
        请务必显式调用 close() 方法来确保日志被刷新。
        """
        if hasattr(self, '_buffer') and self._buffer:
            try:
                self.flush()
            except Exception:
                pass  # 忽略析构时的错误

def main(args):
    pass
