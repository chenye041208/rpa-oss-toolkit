"""
ConfigManager 配置管理器单元测试
"""

import pytest

from rpa_oss_toolkit.config import ConfigManager
from rpa_oss_toolkit.exceptions import ConfigError


class TestConfigManagerInit:
    """测试初始化"""

    def test_default_values(self):
        cfg = ConfigManager()
        assert cfg.get("log_prefix") == "logs/"
        assert cfg.get("log_buffer_size") == 50
        assert cfg.get("min_multithread_size") == 5 * 1024 * 1024
        assert cfg.get("max_retry_count") == 3
        assert cfg.get("retry_delay") == 2
        assert cfg.get("default_expires_in") == 3600
        assert cfg.get("default_cache_max_age") == 3600

    def test_init_with_overrides(self):
        cfg = ConfigManager(log_prefix="custom/", log_buffer_size=100)
        assert cfg.get("log_prefix") == "custom/"
        assert cfg.get("log_buffer_size") == 100
        # 未覆盖的保持默认
        assert cfg.get("max_retry_count") == 3

    def test_init_with_invalid_override(self):
        with pytest.raises(ConfigError):
            ConfigManager(log_buffer_size="abc")


class TestConfigManagerSet:
    """测试 set()"""

    def test_set_valid_value(self):
        cfg = ConfigManager()
        cfg.set("log_buffer_size", 200)
        assert cfg.get("log_buffer_size") == 200

    def test_set_unknown_key(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError, match="未知"):
            cfg.set("unknown_key", "value")

    def test_set_wrong_type(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError, match="类型错误"):
            cfg.set("log_buffer_size", "not_an_int")

    def test_set_value_out_of_range(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError, match="值无效"):
            cfg.set("log_buffer_size", 0)  # 必须 > 0

        with pytest.raises(ConfigError, match="值无效"):
            cfg.set("max_retry_count", -1)  # 必须 >= 0

    def test_set_retry_delay_float(self):
        cfg = ConfigManager()
        cfg.set("retry_delay", 3.5)
        assert cfg.get("retry_delay") == 3.5

    def test_set_expires_in_none(self):
        cfg = ConfigManager()
        cfg.set("default_expires_in", None)
        assert cfg.get("default_expires_in") is None

    def test_set_expires_in_zero(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError):
            cfg.set("default_expires_in", 0)

    @pytest.mark.parametrize("key,value", [
        ("log_prefix", "new/prefix/"),
        ("min_multithread_size", 10 * 1024 * 1024),
        ("part_size", 5 * 1024 * 1024),
        ("default_cache_max_age", 7200),
    ])
    def test_set_various_valid_values(self, key, value):
        cfg = ConfigManager()
        cfg.set(key, value)
        assert cfg.get(key) == value


class TestConfigManagerGet:
    """测试 get()"""

    def test_get_all(self):
        cfg = ConfigManager()
        all_config = cfg.get()
        assert isinstance(all_config, dict)
        assert "log_prefix" in all_config
        assert "log_buffer_size" in all_config
        assert len(all_config) >= 8

    def test_get_all_is_copy(self):
        cfg = ConfigManager()
        all_config = cfg.get()
        all_config["log_prefix"] = "hacked/"
        assert cfg.get("log_prefix") == "logs/"  # 原对象不变

    def test_get_unknown_key(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError, match="未知"):
            cfg.get("unknown_key")


class TestConfigManagerUpdate:
    """测试 update()"""

    def test_update_multiple(self):
        cfg = ConfigManager()
        cfg.update(log_buffer_size=100, max_retry_count=5, retry_delay=3)
        assert cfg.get("log_buffer_size") == 100
        assert cfg.get("max_retry_count") == 5
        assert cfg.get("retry_delay") == 3

    def test_update_with_invalid(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError):
            cfg.update(log_buffer_size=100, max_retry_count=-1)


class TestConfigManagerReset:
    """测试 reset()"""

    def test_reset_single(self):
        cfg = ConfigManager()
        cfg.set("log_buffer_size", 999)
        cfg.reset("log_buffer_size")
        assert cfg.get("log_buffer_size") == 50

    def test_reset_all(self):
        cfg = ConfigManager(log_prefix="custom/", log_buffer_size=999)
        cfg.reset()
        assert cfg.get("log_prefix") == "logs/"
        assert cfg.get("log_buffer_size") == 50

    def test_reset_unknown_key(self):
        cfg = ConfigManager()
        with pytest.raises(ConfigError, match="未知"):
            cfg.reset("unknown_key")
