"""
工具函数单元测试
"""

import os
import tempfile

import pytest

from rpa_oss_toolkit.utils import (
    generate_session_id,
    format_bytes,
    validate_oss_key,
    validate_local_file,
    get_file_extension,
    ensure_oss_key,
)


class TestGenerateSessionId:
    """测试会话 ID 生成"""

    def test_generates_uuid(self):
        session_id = generate_session_id()
        assert isinstance(session_id, str)
        assert len(session_id) == 36  # UUID 格式长度
        assert session_id.count("-") == 4

    def test_unique_ids(self):
        ids = {generate_session_id() for _ in range(100)}
        assert len(ids) == 100  # 无重复


class TestFormatBytes:
    """测试字节格式化"""

    @pytest.mark.parametrize("input_bytes,expected", [
        (0, "0.00 B"),
        (1024, "1 KB"),
        (1048576, "1 MB"),
        (1073741824, "1 GB"),
        (1099511627776, "1 TB"),
        (512, "512 B"),
        (1536, "1.5 KB"),
        (-1024, "-1 KB"),
    ])
    def test_format(self, input_bytes, expected):
        assert format_bytes(input_bytes) == expected

    def test_custom_decimals(self):
        assert format_bytes(1024, decimals=0) == "1 KB"
        assert format_bytes(1500, decimals=1) == "1.5 KB"
        assert format_bytes(1500, decimals=3) == "1.465 KB"


class TestValidateOssKey:
    """测试 OSS 键名验证"""

    @pytest.mark.parametrize("key", [
        "file.txt",
        "path/to/file.txt",
        "a/b/c/d.jpg",
        "中文文件.txt",
        "file with spaces.txt",
    ])
    def test_valid_keys(self, key):
        is_valid, msg = validate_oss_key(key)
        assert is_valid, f"期望合法，但被拒绝: {key} -> {msg}"

    def test_empty_key(self):
        is_valid, msg = validate_oss_key("")
        assert not is_valid
        assert "不能为空" in msg

    def test_none_key(self):
        is_valid, msg = validate_oss_key(None)
        assert not is_valid

    def test_key_too_long(self):
        is_valid, msg = validate_oss_key("a" * 1024)
        assert not is_valid
        assert "过长" in msg

    def test_control_characters(self):
        is_valid, msg = validate_oss_key("file\t.txt")
        assert not is_valid
        assert "非法字符" in msg

    def test_starts_with_slash(self):
        is_valid, msg = validate_oss_key("/file.txt")
        assert not is_valid
        assert "斜杠开头" in msg

    def test_contains_double_dot(self):
        is_valid, msg = validate_oss_key("file..txt")
        assert not is_valid
        assert ".." in msg

    @pytest.mark.parametrize("key", [
        "a" * 1023,   # 最大合法长度
    ])
    def test_boundary_key_length(self, key):
        is_valid, msg = validate_oss_key(key)
        assert is_valid, f"边界值应合法: {msg}"


class TestValidateLocalFile:
    """测试本地文件验证"""

    def test_valid_file(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name
        try:
            is_valid, msg = validate_local_file(tmp_path)
            assert is_valid, f"合法文件被拒绝: {msg}"
        finally:
            os.unlink(tmp_path)

    def test_nonexistent_file(self):
        is_valid, msg = validate_local_file("/nonexistent/path/file.txt")
        assert not is_valid
        assert "不存在" in msg

    def test_empty_path(self):
        is_valid, msg = validate_local_file("")
        assert not is_valid

    def test_none_path(self):
        is_valid, msg = validate_local_file(None)
        assert not is_valid


class TestGetFileExtension:
    """测试文件扩展名提取"""

    @pytest.mark.parametrize("path,expected", [
        ("file.txt", "txt"),
        ("file.tar.gz", "gz"),
        ("a.b.c.jpg", "jpg"),
        ("no_ext", ""),
        (".hidden", ""),
        ("path/to/file.PDF", "pdf"),  # 转小写
    ])
    def test_extension(self, path, expected):
        assert get_file_extension(path) == expected


class TestEnsureOssKey:
    """测试 OSS 键名规范化"""

    @pytest.mark.parametrize("input_key,expected", [
        ("file.txt", "file.txt"),
        ("/file.txt", "file.txt"),
        ("//path/file.txt", "path/file.txt"),
        ("a/b/c", "a/b/c"),
        ("", ""),
    ])
    def test_normalize(self, input_key, expected):
        assert ensure_oss_key(input_key) == expected
