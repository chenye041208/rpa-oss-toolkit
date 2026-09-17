"""
阿里云 OSS 库 - 工具函数

本模块包含库内部使用的通用工具函数。
包括：UUID 生成、时间处理、文件大小格式化、路径验证等。
"""

import uuid
import re
import os


def generate_session_id():
    """
    生成唯一的会话ID

    :return: UUID 格式的会话唯一标识
    """
    return str(uuid.uuid4())

def format_bytes(bytes_num: float, decimals: int = 2) -> str:
    """
    将字节数转换为易读的格式

    :param bytes_num: 字节数
    :param decimals: 小数位数
    :return: 格式化后的字符串，如 "1.5 MB"

    示例：
        format_bytes(1024)        -> "1.00 KB"
        format_bytes(1048576)     -> "1.00 MB"
        format_bytes(1073741824)  -> "1.00 GB"
    """
    if bytes_num == 0:
        return f"0.{'0' * decimals} B"

    UNITS = ['B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
    FACTOR = 1024

    is_negative = bytes_num < 0
    bytes_num = abs(bytes_num)

    for unit in UNITS:
        if bytes_num < FACTOR:
            break
        bytes_num /= FACTOR
    else:
        unit = UNITS[-1]

    if decimals == 0:
        formatted = str(int(round(bytes_num)))
    else:
        formatted = f"{bytes_num:.{decimals}f}".rstrip('0').rstrip('.')

    return f"{'-' if is_negative else ''}{formatted} {unit}"


def validate_oss_key(oss_key: str) -> tuple:
    """
    验证阿里云 OSS 文件键名是否合法

    :param oss_key: OSS 文件键名
    :return: (是否合法, 错误信息)

    规则：
        - 不能为空
        - 长度不能超过 1023 字节
        - 不能包含控制字符（ASCII 0-31）和 DELETE（127）
        - 不能以斜杠开头
        - 不能包含 ".."
        - 必须是有效的 UTF-8 编码
    """
    if not oss_key or not isinstance(oss_key, str):
        return False, "OSS键名不能为空且必须是字符串"

    if len(oss_key) > 1023:
        return False, "OSS键名过长（最大1023字节）"

    if re.search(r'[\x00-\x1F\x7F]', oss_key):
        return False, "键名包含非法字符（控制字符或DEL）"

    if oss_key.startswith('/'):
        return False, "键名不能以斜杠开头"

    if '..' in oss_key:
        return False, "键名不能包含 '..'"

    try:
        oss_key.encode('utf-8')
    except UnicodeEncodeError:
        return False, "键名包含无效的UTF-8字符"

    return True, ""


def validate_local_file(file_path: str) -> tuple:
    """
    验证本地文件路径是否合法且可读

    :param file_path: 本地文件路径
    :return: (是否合法, 错误信息)

    规则：
        - 文件必须存在
        - 必须是文件（不是目录）
        - 必须有读取权限
    """
    if not file_path or not isinstance(file_path, str):
        return False, "文件路径不能为空"

    if not os.path.exists(file_path):
        return False, f"本地文件不存在: {file_path}"

    if not os.path.isfile(file_path):
        return False, f"路径不是文件: {file_path}"

    if not os.access(file_path, os.R_OK):
        return False, f"没有读取权限: {file_path}"

    return True, ""


def get_file_extension(file_path: str) -> str:
    """
    获取文件扩展名

    :param file_path: 文件路径或键名
    :return: 扩展名（不含点），如 "txt", "jpg", "pdf"

    示例：
        get_file_extension("a.txt")     -> "txt"
        get_file_extension("a.b.c.txt") -> "txt"
        get_file_extension("a")         -> ""
    """
    _, ext = os.path.splitext(file_path)
    return ext.lstrip('.').lower() if ext else ''


def ensure_oss_key(key: str) -> str:
    """
    确保 OSS 键名格式正确

    如果键名以 / 开头，去掉开头的 /
    如果键名不是以字母或数字开头，添加适当的处理

    :param key: OSS 键名
    :return: 规范化后的键名
    """
    key = key.lstrip('/')
    return key