"""
异常体系单元测试
"""

import pytest

from rpa_oss_toolkit.exceptions import (
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


class TestExceptionHierarchy:
    """验证异常继承关系"""

    @pytest.mark.parametrize("exc_cls,expected_parent", [
        (ValidationError, OSSError),
        (SessionError, OSSError),
        (SessionExpiredError, SessionError),
        (OperationError, OSSError),
        (UploadError, OperationError),
        (DownloadError, OperationError),
        (DeleteError, OperationError),
        (ListError, OperationError),
        (CopyError, OperationError),
        (MetadataError, OSSError),
        (LogError, OSSError),
        (ConfigError, OSSError),
    ])
    def test_inheritance(self, exc_cls, expected_parent):
        assert issubclass(exc_cls, expected_parent), f"{exc_cls.__name__} 应继承 {expected_parent.__name__}"

    def test_all_subclass_of_oss_error(self):
        """所有自定义异常都应继承 OSSError"""
        exc_classes = [
            ValidationError, SessionError, SessionExpiredError,
            OperationError, UploadError, DownloadError,
            DeleteError, ListError, CopyError,
            MetadataError, LogError, ConfigError,
        ]
        for exc_cls in exc_classes:
            assert issubclass(exc_cls, OSSError), f"{exc_cls.__name__} 不是 OSSError 的子类"

    def test_catch_by_parent(self):
        """捕获 OSSError 应能捕获所有子类异常"""
        exceptions_to_test = [
            ValidationError("test"),
            SessionError("test"),
            SessionExpiredError("test"),
            OperationError("test"),
            UploadError("test"),
            DownloadError("test"),
            DeleteError("test"),
            ListError("test"),
            CopyError("test"),
            MetadataError("test"),
            LogError("test"),
            ConfigError("test"),
        ]
        for exc in exceptions_to_test:
            assert isinstance(exc, OSSError), f"{type(exc).__name__} 不是 OSSError 实例"


class TestConfigError:
    """ConfigError 专项测试"""

    def test_default_message(self):
        exc = ConfigError()
        assert isinstance(exc, OSSError)

    def test_custom_message(self):
        exc = ConfigError("自定义错误信息")
        assert str(exc) == "自定义错误信息"

    def test_catch_specific(self):
        """应能精确捕获 ConfigError"""
        with pytest.raises(ConfigError):
            raise ConfigError("test")

    def test_catch_general(self):
        """OSSError 也应能捕获 ConfigError"""
        try:
            raise ConfigError("test")
        except OSSError:
            pass
        else:
            pytest.fail("OSSError 未能捕获 ConfigError")
