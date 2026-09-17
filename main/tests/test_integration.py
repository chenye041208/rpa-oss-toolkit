"""
集成测试 - 真实 OSS 操作

运行前准备：
    1. 在 main 目录创建 .env 文件（参考 main/.env.example）
    2. 填入真实的 OSS 凭据

运行（需显式指定 integration 标记，默认被 pytest.ini 排除）：
    cd main && ../venv/bin/python -m pytest -m integration -v

测试内容：
    - create_session 创建与验证
    - upload / download / delete 完整流程
    - list / exists / copy / get_url / metadata
    - 日志自动写入
    - Session 配置修改
"""

import os
import pytest

from .conftest import load_env
from rpa_oss_toolkit import OSSClient
from rpa_oss_toolkit.exceptions import (
    ValidationError, SessionError, ConfigError,
)

pytestmark = pytest.mark.integration

# 从 .env 加载凭据
load_env()

OSS_AK_ID = os.getenv("OSS_AK_ID", "")
OSS_AK_SECRET = os.getenv("OSS_AK_SECRET", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "oss-cn-shenzhen.aliyuncs.com")
OSS_BUCKET = os.getenv("OSS_BUCKET", "")

# 凭据未配置时跳过所有集成测试
needs_credentials = pytest.mark.skipif(
    not all([OSS_AK_ID, OSS_AK_SECRET, OSS_BUCKET]),
    reason="需要 OSS 凭据，请在 .env 中配置 OSS_AK_ID, OSS_AK_SECRET, OSS_BUCKET",
)


# ============================================================
# 夹具
# ============================================================


@pytest.fixture(scope="module")
def session():
    """创建真实 OSS 会话"""
    with OSSClient.create_session(
        access_key_id=OSS_AK_ID,
        access_key_secret=OSS_AK_SECRET,
        endpoint=OSS_ENDPOINT,
        bucket=OSS_BUCKET,
        session_name="pytest_integration",
    ) as sess:
        yield sess


# ============================================================
# 创建会话
# ============================================================


class TestCreateSession:

    def test_create_success(self):
        with OSSClient.create_session(
            access_key_id=OSS_AK_ID,
            access_key_secret=OSS_AK_SECRET,
            endpoint=OSS_ENDPOINT,
            bucket=OSS_BUCKET,
            session_name="pytest_create",
        ) as sess:
            assert sess.is_valid
            assert sess.session_name == "pytest_create"

    def test_invalid_ak(self):
        with pytest.raises(SessionError):
            OSSClient.create_session(
                access_key_id="invalid",
                access_key_secret=OSS_AK_SECRET,
                endpoint=OSS_ENDPOINT,
                bucket=OSS_BUCKET,
                session_name="test",
            )

    def test_empty_params(self):
        with pytest.raises(ValidationError):
            OSSClient.create_session(
                access_key_id="",
                access_key_secret="",
                endpoint="",
                bucket="",
                session_name="",
            )


# ============================================================
# 上传 / 下载 / 删除
# ============================================================


@needs_credentials
class TestUploadDownloadDelete:

    @pytest.fixture(autouse=True)
    def cleanup(self, session):
        yield
        for key in ["pytest/test_upload.txt", "pytest/test_copy.txt"]:
            try:
                session.delete(key)
            except Exception:
                pass
        local_dl = "pytest_downloaded.txt"
        if os.path.exists(local_dl):
            os.remove(local_dl)

    def test_upload_and_download(self, session):
        with open("pytest_upload.txt", "w") as f:
            f.write("Hello OSS")
        try:
            assert session.upload("pytest_upload.txt", "pytest/test_upload.txt")
            assert session.exists("pytest/test_upload.txt")

            assert session.download("pytest/test_upload.txt", "pytest_downloaded.txt")
            with open("pytest_downloaded.txt") as f:
                content = f.read()
            assert content == "Hello OSS"
        finally:
            os.remove("pytest_upload.txt")

    def test_delete(self, session):
        with open("pytest_to_delete.txt", "w") as f:
            f.write("delete me")
        session.upload("pytest_to_delete.txt", "pytest/to_delete.txt")
        os.remove("pytest_to_delete.txt")
        assert session.exists("pytest/to_delete.txt")

        assert session.delete("pytest/to_delete.txt")
        assert not session.exists("pytest/to_delete.txt")


# ============================================================
# 列举和复制
# ============================================================


@needs_credentials
class TestListAndCopy:

    @pytest.fixture(autouse=True)
    def setup(self, session):
        with open("pytest_list_test.txt", "w") as f:
            f.write("list test")
        session.upload("pytest_list_test.txt", "pytest/list_test.txt")
        yield
        os.remove("pytest_list_test.txt")
        for key in ["pytest/list_test.txt", "pytest/list_test_copy.txt"]:
            try:
                session.delete(key)
            except Exception:
                pass

    def test_list(self, session):
        files = session.list("pytest/")
        assert any("pytest/list_test.txt" in f for f in files)

    def test_copy(self, session):
        assert session.copy("pytest/list_test.txt", "pytest/list_test_copy.txt")
        assert session.exists("pytest/list_test_copy.txt")


# ============================================================
# 元数据
# ============================================================


@needs_credentials
class TestMetadata:

    @pytest.fixture(autouse=True)
    def setup(self, session):
        with open("pytest_meta.txt", "w") as f:
            f.write("meta")
        session.upload("pytest_meta.txt", "pytest/meta_test.txt")
        yield
        os.remove("pytest_meta.txt")
        try:
            session.delete("pytest/meta_test.txt")
        except Exception:
            pass

    def test_get_metadata(self, session):
        meta = session.get_metadata("pytest/meta_test.txt")
        assert "content_type" in meta
        assert "content_length" in meta
        assert "last_modified" in meta

    def test_get_url(self, session):
        url = session.get_url("pytest/meta_test.txt", expires=600)
        assert url.startswith("http")


# ============================================================
# 日志和配置
# ============================================================


@needs_credentials
class TestLogAndConfig:

    def test_flush_logs(self, session):
        session.flush_logs()

    def test_get_config(self, session):
        config = session.get_config()
        assert isinstance(config, dict)
        assert "log_prefix" in config

    def test_set_config(self, session):
        session.set_config(log_buffer_size=100)
        assert session.get_config("log_buffer_size") == 100
        session.set_config(log_buffer_size=50)

    def test_set_config_invalid(self, session):
        with pytest.raises(ConfigError):
            session.set_config(log_buffer_size=-1)
