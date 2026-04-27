"""
阿里云 OSS 库 - 运行时配置

本文件包含所有可调整的运行时参数，以及 ConfigManager 配置管理器。
OSS连接参数（AK/SK/endpoint/bucket）请在创建会话时通过参数传入。
"""

from typing import Any, Dict, Optional, overload

from .exceptions import ConfigError

# ============================================================================
# 日志配置
# ============================================================================

# 日志文件存储路径前缀（OSS上的目录）
LOG_PREFIX = "logs/"

# 日志缓冲区大小（条）
LOG_BUFFER_SIZE = 50

# ============================================================================
# 文件传输配置
# ============================================================================

# 分片上传/下载阈值（字节），超过该值自动使用分片传输
MIN_MULTITHREAD_SIZE = 5 * 1024 * 1024

# 分片大小（字节）
PART_SIZE = 10 * 1024 * 1024

# 最大重试次数
MAX_RETRY_COUNT = 3

# 重试延迟（秒）
RETRY_DELAY = 2

# ============================================================================
# 会话配置
# ============================================================================

# 会话默认有效期（秒），None 表示不过期
DEFAULT_EXPIRES_IN = 3600

# ============================================================================
# 元数据配置
# ============================================================================

# 下载文件时默认的缓存时间（秒）
DEFAULT_CACHE_MAX_AGE = 3600


class ConfigManager:
    """
    配置管理器

    负责所有运行时可调配置参数的存储、类型检查与值校验。
    每个配置项都有预定义的默认值、类型约束和可选的校验规则。

    使用示例：
        cfg = ConfigManager(log_prefix="logs/backup/")
        cfg.get("log_prefix")              # -> "logs/backup/"
        cfg.set("log_buffer_size", 100)    # 修改配置
        cfg.update(max_retry_count=5, retry_delay=3)  # 批量修改
        cfg.reset("log_prefix")            # 重置单项为默认值
        cfg.reset()                         # 重置全部为默认值
    """

    # 配置项定义：名称 -> (默认值, 合法类型, 校验函数或None, 说明)
    _definitions = {
        "log_prefix": (
            LOG_PREFIX,
            str,
            None,
            "日志文件存储路径前缀",
        ),
        "log_buffer_size": (
            LOG_BUFFER_SIZE,
            int,
            lambda v: v > 0,
            "日志缓冲区大小（条）",
        ),
        "min_multithread_size": (
            MIN_MULTITHREAD_SIZE,
            int,
            lambda v: v > 0,
            "分片传输阈值（字节）",
        ),
        "part_size": (
            PART_SIZE,
            int,
            lambda v: v > 0,
            "分片大小（字节）",
        ),
        "max_retry_count": (
            MAX_RETRY_COUNT,
            int,
            lambda v: v >= 0,
            "最大重试次数",
        ),
        "retry_delay": (
            RETRY_DELAY,
            (int, float),
            lambda v: v >= 0,
            "重试延迟（秒）",
        ),
        "default_expires_in": (
            DEFAULT_EXPIRES_IN,
            (int, type(None)),
            lambda v: v is None or v > 0,
            "会话默认有效期（秒），None 为不过期",
        ),
        "default_cache_max_age": (
            DEFAULT_CACHE_MAX_AGE,
            int,
            lambda v: v > 0,
            "默认缓存时间（秒）",
        ),
    }

    def __init__(self, **kwargs):
        """
        初始化配置管理器

        :param kwargs: 初始覆盖的配置项，不传则全部使用默认值
        """
        self._config = {}
        for name, (default, _, _, _) in self._definitions.items():
            self._config[name] = default
        if kwargs:
            self.update(**kwargs)

    def set(self, key: str, value):
        """
        设置单个配置项

        :param key: 配置项名称
        :param value: 配置值
        :raises ConfigError: 未知配置项、类型错误或值校验失败

        使用示例：
            cfg.set("log_buffer_size", 100)
            cfg.set("retry_delay", 3.0)
        """
        if key not in self._definitions:
            raise ConfigError(f"未知配置项: '{key}'")

        _, expected_type, validator, _ = self._definitions[key]

        # 类型检查
        if isinstance(expected_type, tuple):
            if not isinstance(value, expected_type):
                raise ConfigError(
                    f"配置项 '{key}' 类型错误，期望 {expected_type}，实际 {type(value).__name__}"
                )
        else:
            if not isinstance(value, expected_type):
                raise ConfigError(
                    f"配置项 '{key}' 类型错误，期望 {expected_type.__name__}，实际 {type(value).__name__}"
                )

        # 值校验
        if validator is not None and not validator(value):
            raise ConfigError(f"配置项 '{key}' 值无效: {value}")

        self._config[key] = value

    @overload
    def get(self, key: str) -> Any: ...

    @overload
    def get(self, key: None = None) -> Dict[str, Any]: ...

    def get(self, key: Optional[str] = None) -> Any:
        """
        获取配置项

        :param key: 配置项名称，为 None 时返回全部配置的副本
        :return: 单个配置值，或包含全部配置的字典
        :raises ConfigError: 未知配置项

        使用示例：
            cfg.get("log_prefix")      # -> "logs/"
            cfg.get()                   # -> {"log_prefix": "logs/", ...}
        """
        if key is None:
            return dict(self._config)
        if key not in self._definitions:
            raise ConfigError(f"未知配置项: '{key}'")
        return self._config[key]

    def update(self, **kwargs):
        """
        批量更新配置

        :param kwargs: 配置项名称和值的键值对
        :raises ConfigError: 任一配置项不合法

        使用示例：
            cfg.update(log_buffer_size=100, max_retry_count=5)
        """
        for key, value in kwargs.items():
            self.set(key, value)

    def reset(self, key=None):
        """
        重置配置项到默认值

        :param key: 配置项名称，为 None 时重置全部
        :raises ConfigError: 未知配置项

        使用示例：
            cfg.reset("log_prefix")   # 重置单项
            cfg.reset()                # 重置全部
        """
        if key is None:
            for name, (default, _, _, _) in self._definitions.items():
                self._config[name] = default
        else:
            if key not in self._definitions:
                raise ConfigError(f"未知配置项: '{key}'")
            default, _, _, _ = self._definitions[key]
            self._config[key] = default
