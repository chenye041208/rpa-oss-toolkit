"""
测试共享夹具和工具函数
"""

import os
from pathlib import Path


def load_env(env_file=".env"):
    """
    从 main 目录加载 .env 文件

    简单的 .env 解析器，不依赖 python-dotenv。
    支持格式：
        KEY=VALUE
        # 注释
        空行跳过
        引号会自动去除

    :param env_file: .env 文件名
    :return: None（设置 os.environ）
    """
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / env_file

    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key:
                os.environ.setdefault(key, value)
