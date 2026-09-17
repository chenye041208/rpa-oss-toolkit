"""
Session 配置方法单元测试

Session 的正常 OSS 操作需要真实连接，这里仅测试与 OSS 无关的配置接口。
"""

import pytest
from unittest.mock import patch, MagicMock

from rpa_oss_toolkit.client import Session
from rpa_oss_toolkit.config import ConfigManager
from rpa_oss_toolkit.exceptions import ConfigError


@pytest.fixture
def mock_session():
    """创建一个 Mock Session（绕过真实 OSS 连接）"""
    with patch("rpa_oss_toolkit.client.oss2.Bucket") as mock_bucket:
        session = Session(
            access_key_id="test_key",
            access_key_secret="test_secret",
            endpoint="oss-cn-test.aliyuncs.com",
            bucket="test-bucket",
            session_name="test_session",
            log_prefix="logs/",
            expires_in=3600,
        )
        yield session


class TestSessionGetConfig:
    """测试 get_config()"""

    def test_get_single(self, mock_session):
        val = mock_session.get_config("log_prefix")
        assert val == "logs/"

    def test_get_all(self, mock_session):
        config = mock_session.get_config()
        assert isinstance(config, dict)
        assert config["log_prefix"] == "logs/"
        assert config["log_buffer_size"] == 50

    def test_get_all_isolation(self, mock_session):
        """返回的字典修改不应影响内部配置"""
        config = mock_session.get_config()
        config["log_prefix"] = "modified/"
        assert mock_session.get_config("log_prefix") == "logs/"

    def test_get_unknown_key(self, mock_session):
        with pytest.raises(ConfigError, match="未知"):
            mock_session.get_config("nonexistent")


class TestSessionSetConfig:
    """测试 set_config()"""

    def test_set_single(self, mock_session):
        mock_session.set_config(log_buffer_size=200)
        assert mock_session.get_config("log_buffer_size") == 200

    def test_set_multiple(self, mock_session):
        mock_session.set_config(max_retry_count=5, retry_delay=3)
        assert mock_session.get_config("max_retry_count") == 5
        assert mock_session.get_config("retry_delay") == 3

    def test_set_invalid_key(self, mock_session):
        with pytest.raises(ConfigError, match="未知"):
            mock_session.set_config(invalid_key=123)

    def test_set_wrong_type(self, mock_session):
        with pytest.raises(ConfigError, match="类型错误"):
            mock_session.set_config(log_buffer_size="abc")

    def test_set_invalid_value(self, mock_session):
        with pytest.raises(ConfigError, match="值无效"):
            mock_session.set_config(log_buffer_size=0)

    def test_set_log_prefix_updates_logger(self, mock_session):
        mock_session.set_config(log_prefix="new/logs/")
        assert mock_session._logger._log_prefix == "new/logs/"

    def test_set_buffer_size_updates_logger(self, mock_session):
        mock_session.set_config(log_buffer_size=100)
        assert mock_session._logger._buffer_size == 100
