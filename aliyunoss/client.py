"""
阿里云 OSS 库 - 客户端与会话

本模块包含两个核心类：
    - OSSClient：工厂类，用于创建会话
    - Session：会话类，提供所有文件操作接口

会话机制：
    1. 通过 OSSClient.create_session() 创建会话（验证连接）
    2. 通过 Session 对象执行所有 OSS 操作
    3. 操作自动记录日志到 OSS
    4. 调用 session.close() 关闭会话，刷新剩余日志
"""

from datetime import datetime, timedelta, timezone as tz
from typing import Optional

import oss2

from .config import LOG_PREFIX, DEFAULT_EXPIRES_IN, ConfigManager
from .exceptions import ValidationError, SessionError, ConfigError
from .utils import generate_session_id
from .operations import Operations
from .logger import OperationLogger


class OSSClient:
    """
    OSS 客户端工厂类

    提供静态方法 create_session() 用于创建会话。
    不需要实例化，直接通过类名调用。

    使用示例：
        session = OSSClient.create_session(
            access_key_id="your_ak",
            access_key_secret="your_sk",
            endpoint="oss-cn-hangzhou.aliyuncs.com",
            bucket="your_bucket",
            session_name="RPA流程A"
        )
    """

    @staticmethod
    def create_session(
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket: str,
        session_name: str,
    ) -> 'Session':
        """
        创建会话

        验证 OSS 连接后返回一个 Session 对象，所有后续操作都通过 Session 执行。

        :param access_key_id: AccessKey ID
        :param access_key_secret: AccessKey Secret
        :param endpoint: OSS endpoint（如 oss-cn-hangzhou.aliyuncs.com）
        :param bucket: Bucket 名称
        :param session_name: 会话名称（用于日志文件名）

        :return: Session 实例

        :raises ValidationError: 参数校验失败
        :raises SessionError: 连接验证失败

        使用示例：
            session = OSSClient.create_session(
                access_key_id="your_ak",
                access_key_secret="your_sk",
                endpoint="oss-cn-hangzhou.aliyuncs.com",
                bucket="your_bucket",
                session_name="RPA流程A"
            )
            session.upload("local.txt", "remote.txt")
            session.close()
        """
        # 参数校验
        if not all([access_key_id, access_key_secret, endpoint, bucket]):
            raise ValidationError("access_key_id、access_key_secret、endpoint、bucket 都不能为空")

        if not session_name or not isinstance(session_name, str):
            raise ValidationError("session_name 不能为空")

        # 创建认证
        auth = oss2.Auth(access_key_id, access_key_secret)

        # 创建 Bucket 连接
        try:
            bucket_conn = oss2.Bucket(auth, endpoint, bucket)
            # 验证连接：尝试获取 Bucket 信息
            bucket_conn.get_bucket_info()
        except oss2.exceptions.OssError as e:
            raise SessionError(f"OSS 连接失败: {str(e)}")
        except Exception as e:
            raise SessionError(f"创建会话失败: {str(e)}")

        # 创建会话
        session = Session(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
            endpoint=endpoint,
            bucket=bucket,
            session_name=session_name,
            log_prefix=LOG_PREFIX,
            expires_in=DEFAULT_EXPIRES_IN,
        )

        return session

class Session:
    """
    OSS 会话类

    持有 OSS 连接和日志器，提供所有文件操作接口。
    操作自动记录日志到 OSS。

    使用示例：
        session = OSSClient.create_session(...)
        session.upload("local.txt", "remote.txt")
        session.download("remote.txt", "local.txt")
        session.list("prefix/")
        session.close()
    """

    def __init__(
        self,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str,
        bucket: str,
        session_name: str,
        log_prefix: str,
        expires_in: int,
    ):
        """
        初始化会话（不直接调用，通过 OSSClient.create_session 创建）

        :param access_key_id: AccessKey ID
        :param access_key_secret: AccessKey Secret
        :param endpoint: OSS endpoint
        :param bucket: Bucket 名称
        :param session_name: 会话名称
        :param log_prefix: 日志路径前缀
        :param expires_in: 会话有效期（秒），None 表示不过期
        """
        self._access_key_id = access_key_id
        self._access_key_secret = access_key_secret
        self._endpoint = endpoint
        self._bucket_name = bucket
        self._session_name = session_name

        # 创建 OSS 连接
        auth = oss2.Auth(access_key_id, access_key_secret)
        self._bucket = oss2.Bucket(auth, endpoint, bucket)

        # 会话信息
        # 创建配置管理器
        self._config = ConfigManager(
            log_prefix=log_prefix,
            default_expires_in=expires_in,
        )

        # 会话信息
        self._session_id = generate_session_id()
        self._created_at = datetime.now(tz.utc)
        expires_in_val = self._config.get("default_expires_in")
        if expires_in_val is not None:
            self._expires_at = self._created_at + timedelta(seconds=expires_in_val)
        else:
            self._expires_at = None
        self._is_valid = True

        # 初始化操作类和日志器
        self._operations = Operations(self._bucket)
        self._logger = OperationLogger(
            self._bucket, session_name,
            self._config.get("log_prefix"),
            self._config.get("log_buffer_size"),
        )

    # ==================== 属性 ====================

    @property
    def session_id(self) -> str:
        """
        获取会话 ID

        :return: UUID 格式的会话唯一标识
        """
        return self._session_id

    @property
    def session_name(self) -> str:
        """
        获取会话名称

        :return: 会话名称
        """
        return self._session_name

    @property
    def log_filename(self) -> str:
        """
        获取日志文件名

        :return: 日志文件名，格式 {date}_{session_name}.log
        """
        return self._logger.log_filename

    @property
    def is_valid(self) -> bool:
        """
        检查会话是否有效

        :return: 会话是否有效
        """
        if not self._is_valid:
            return False
        if self._expires_at and datetime.now(tz.utc) > self._expires_at:
            self._is_valid = False
            return False
        return True

    # ==================== 配置管理 ====================

    def get_config(self, key: Optional[str] = None):
        """
        获取会话配置

        :param key: 配置项名称，为 None 时返回全部配置
        :return: 单个配置值，或全部配置的字典

        使用示例：
            val = session.get_config("log_buffer_size")  # 单条
            all = session.get_config()                    # 全部
        """
        return self._config.get(key)

    def set_config(self, **kwargs):
        """
        修改会话配置

        :param kwargs: 配置项键值对
        :raises ConfigError: 配置项名称、类型或值不合法

        使用示例：
            session.set_config(log_prefix="logs/new/")
            session.set_config(log_buffer_size=100, max_retry_count=5)
        """
        self._config.update(**kwargs)

        # 同步更新相关组件
        if "log_prefix" in kwargs:
            self._logger.update_log_prefix(kwargs["log_prefix"])
        if "log_buffer_size" in kwargs:
            self._logger.update_buffer_size(kwargs["log_buffer_size"])

    @property
    def created_at(self) -> datetime:
        """
        获取会话创建时间

        :return: 创建时间
        """
        return self._created_at

    @property
    def expires_at(self) -> Optional[datetime]:
        """
        获取会话过期时间

        :return: 过期时间，如果不过期则返回 None
        """
        return self._expires_at

    # ==================== 内部方法 ====================

    def _validate(self):
        """
        验证会话状态

        :raises SessionError: 会话无效时抛出
        """
        if not self.is_valid:
            raise SessionError("会话已失效")

    def log_operation(self, content: str):
        """
        记录日志文本

        将文本内容追加到内存缓冲区，达到阈值后自动写入 OSS。
        也可通过 flush_logs() 手动刷新。

        :param content: 日志文本内容

        使用示例：
            session.log_operation("这是一条日志")
        """
        self._logger.log(content)
        return True

    # ==================== 文件操作 ====================

    def upload(self, local_path: str, remote_key: str) -> bool:
        """
        上传文件

        :param local_path: 本地文件路径
        :param remote_key: OSS 上的键名
        :return: 是否成功

        使用示例：
            session.upload("本地文件.txt", "上传路径/文件.txt")
        """
        self._validate()
        return self._operations.upload(local_path, remote_key)

    def download(self, remote_key: str, local_path: str) -> bool:
        """
        下载文件

        :param remote_key: OSS 键名
        :param local_path: 本地保存路径
        :return: 是否成功

        使用示例：
            session.download("下载路径/文件.txt", "本地保存路径.txt")
        """
        self._validate()
        return self._operations.download(remote_key, local_path)

    def delete(self, remote_key: str) -> bool:
        """
        删除文件

        :param remote_key: OSS 键名
        :return: 是否成功

        使用示例：
            session.delete("要删除的文件.txt")
        """
        self._validate()
        return self._operations.delete(remote_key)

    def list(self, prefix: str = "") -> list:
        """
        列举文件

        :param prefix: 前缀过滤
        :return: 文件键名列表

        使用示例：
            files = session.list("prefix/")
            for f in files:
                print(f)
        """
        self._validate()
        return self._operations.list_all(prefix)

    def copy(self, src_key: str, dst_key: str) -> bool:
        """
        复制文件

        :param src_key: 源键名
        :param dst_key: 目标键名
        :return: 是否成功

        使用示例：
            session.copy("源文件.txt", "目标文件.txt")
        """
        self._validate()
        return self._operations.copy(src_key, dst_key)

    def exists(self, remote_key: str) -> bool:
        """
        判断文件是否存在

        :param remote_key: OSS 键名
        :return: 是否存在

        使用示例：
            if session.exists("文件.txt"):
                print("文件存在")
        """
        self._validate()
        return self._bucket.object_exists(remote_key)

    def get_url(self, remote_key: str, expires: int = 3600) -> str:
        """
        获取文件访问签名 URL

        :param remote_key: OSS 键名
        :param expires: 有效期（秒），默认 3600 秒
        :return: 签名 URL

        使用示例：
            url = session.get_url("文件.txt", expires=3600)
            print(url)
        """
        self._validate()
        return self._bucket.sign_url('GET', remote_key, expires)

    def get_metadata(self, remote_key: str) -> dict:
        """
        获取文件元数据

        :param remote_key: OSS 键名
        :return: 元数据字典

        使用示例：
            meta = session.get_metadata("文件.txt")
            print(meta)
        """
        self._validate()
        return self._operations.get_metadata(remote_key)

    def set_metadata(self, remote_key: str, metadata: dict) -> bool:
        """
        设置文件元数据

        :param remote_key: OSS 键名
        :param metadata: 元数据字典
        :return: 是否成功

        使用示例：
            session.set_metadata("文件.txt", {
                "Content-Type": "application/pdf",
                "Cache-Control": "private, max-age=3600"
            })
        """
        self._validate()
        return self._operations.update_metadata(remote_key, metadata)

    # ==================== 日志和关闭 ====================

    def flush_logs(self):
        """
        手动刷新日志到 OSS

        使用示例：
            session.flush_logs()
        """
        self._validate()
        self._logger.flush()

    def close(self):
        """
        关闭会话

        刷新剩余日志到 OSS，关闭后会话不能再使用。
        建议使用 try...finally 或 with 语句确保调用。

        使用示例：
            session = OSSClient.create_session(...)
            try:
                session.upload("a.txt", "b.txt")
            finally:
                session.close()
        """
        if self._is_valid:
            self._is_valid = False
            self._logger.close()

    def __enter__(self):
        """
        上下文管理器入口

        使用示例：
            with OSSClient.create_session(...) as session:
                session.upload("a.txt", "b.txt")
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        上下文管理器出口

        确保会话关闭并刷新日志。
        """
        self.close()
        return False  # 不抑制异常
