"""
阿里云 OSS 库 - 元数据验证器

本模块提供元数据验证功能，用于校验 Content-Type、Content-Disposition、
Cache-Control 等 HTTP 头信息是否符合阿里云 OSS 规范。

主要功能：
    - 验证元数据总大小（不超过 8KB）
    - 验证元数据键数量（不超过 100 个）
    - 验证元数据键名是否允许
    - 验证 Content-Type 是否与文件扩展名匹配
    - 验证 Content-Disposition 格式
    - 验证 Cache-Control 指令及互斥规则
    - 生成默认元数据（根据文件扩展名自动推断 Content-Type）
"""

import os
import re
from typing import Tuple, Optional
from urllib.parse import quote


class MetadataValidator:
    """
    阿里云 OSS 文件元信息验证器

    提供完整的元数据验证功能，支持：
        - Content-Type 验证
        - Content-Disposition 验证
        - Cache-Control 验证
        - 自定义元数据（x-oss-meta-）支持

    使用示例：
        validator = MetadataValidator()
        is_valid, message = validator.validate(metadata, "file.txt")
        if not is_valid:
            print(f"验证失败: {message}")
    """

    # 文件扩展名到 Content-Type 的映射表
    EXTENSION_TO_CONTENT_TYPE = {
        # 通用类型
        '': 'application/octet-stream',

        # 图片类型
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'bmp': 'image/bmp',
        'webp': 'image/webp',
        'svg': 'image/svg+xml',
        'tif': 'image/tiff',
        'tiff': 'image/tiff',
        'ico': 'image/x-icon',

        # 文档类型
        'pdf': 'application/pdf',
        'doc': 'application/msword',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'xls': 'application/vnd.ms-excel',
        'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'ppt': 'application/vnd.ms-powerpoint',
        'pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
        'txt': 'text/plain',
        'rtf': 'application/rtf',
        'csv': 'text/csv',
        'html': 'text/html',
        'htm': 'text/html',
        'xml': 'text/xml',
        'json': 'application/json',

        # 音频/视频类型
        'mp3': 'audio/mpeg',
        'wav': 'audio/wav',
        'ogg': 'audio/ogg',
        'mp4': 'video/mp4',
        'mov': 'video/quicktime',
        'avi': 'video/x-msvideo',
        'mkv': 'video/x-matroska',
        'flv': 'video/x-flv',
        'webm': 'video/webm',

        # 压缩文件
        'zip': 'application/zip',
        'rar': 'application/x-rar-compressed',
        '7z': 'application/x-7z-compressed',
        'tar': 'application/x-tar',
        'gz': 'application/gzip',

        # 可执行文件
        'exe': 'application/x-msdownload',
        'msi': 'application/x-msdownload',
        'dmg': 'application/x-apple-diskimage',

        # 编程相关
        'js': 'application/javascript',
        'css': 'text/css',
        'py': 'text/x-python',
        'java': 'text/x-java-source',

        # 字体类型
        'ttf': 'font/ttf',
        'otf': 'font/otf',
        'woff': 'font/woff',
        'woff2': 'font/woff2',
    }

    # 允许存在的元数据键名
    ALLOWED_KEYS = {
        'content-type', 'cache-control', 'content-disposition', 'content-length',
        'content-encoding', 'expires', 'content-language', 'last-modified'
    }

    # Cache-Control 互斥组
    # no-cache 和 no-store 互斥
    # public 和 private 互斥
    CONFLICT_GROUPS = [
        {'no-cache', 'no-store'},
        {'public', 'private'},
    ]

    def validate(self, metadata: dict, key: str) -> Tuple[bool, str]:
        """
        验证元数据是否合法

        验证规则：
            - 键和值必须是字符串
            - 总大小不得超过 8KB
            - 键数量不得超过 100 个
            - 不允许重复键名
            - 键名必须是允许的（x-oss-meta- 开头的自定义键除外）
            - 值长度不得超过 1024 字节
            - Content-Type 必须与文件扩展名匹配
            - Content-Disposition 格式必须正确
            - Cache-Control 指令必须合法且无冲突

        :param metadata: 元数据字典
        :param key: OSS 文件键名（用于推断正确的 Content-Type）
        :return: (是否通过验证, 错误信息)

        示例：
            metadata = {
                'Content-Type': 'text/plain',
                'Content-Disposition': 'attachment; filename="test.txt"',
                'Cache-Control': 'private, max-age=3600'
            }
            is_valid, msg = validator.validate(metadata, "test.txt")
        """
        checks = [
            (self._check_keys_and_values_type, (metadata,)),
            (self._check_total_size, (metadata,)),
            (self._check_key_count, (metadata,)),
            (self._check_keys_conflict, (metadata,)),
            (self._check_allowed_keys, (metadata,)),
            (self._check_values_length, (metadata,)),
            (self._check_content_type, (metadata, key)),
            (self._check_content_disposition, (metadata,)),
            (self._check_cache_control, (metadata,))
        ]

        for func, args in checks:
            is_valid, message = func(*args)
            if not is_valid:
                return False, message

        return True, ""

    def generate_basic_metadata(
        self,
        key: str,
        download_filename: str,
        cache_max_age: int = 3600
    ) -> dict:
        """
        生成基本的元数据

        根据文件扩展名自动推断 Content-Type，并生成符合规范的
        Content-Disposition 和 Cache-Control。

        :param key: 阿里云 OSS 文件键名
        :param download_filename: 下载时的文件名
                                - "__inline__" 表示内联显示
                                - 空字符串表示 attachment（不指定文件名）
                                - 其他值表示attachment并使用指定文件名
        :param cache_max_age: 缓存时间（秒），默认 3600 秒
        :return: 元数据字典

        示例：
            # 生成下载时显示为 "report.pdf" 的元数据
            metadata = validator.generate_basic_metadata(
                "files/report.pdf",
                "report.pdf",
                cache_max_age=3600
            )
        """
        # Content-Type：根据扩展名推断
        _, ext = os.path.splitext(key)
        ext = ext.lstrip('.').lower() if ext else ''
        content_type = self.EXTENSION_TO_CONTENT_TYPE.get(
            ext,
            'application/octet-stream'
        )

        # Content-Disposition
        if download_filename == "__inline__":
            content_disposition = 'inline'
        elif not download_filename:
            content_disposition = 'attachment'
        else:
            # 处理文件名编码
            base_name = os.path.splitext(download_filename)[0]
            file_ext = os.path.splitext(download_filename)[1]

            # 确保文件有正确的扩展名
            if not file_ext and ext:
                download_filename = f"{download_filename}.{ext}"
                base_name = os.path.splitext(download_filename)[0]
                file_ext = f".{ext}"

            # URL 编码文件名
            encoded_base = quote(base_name)
            encoded_full = quote(download_filename)

            content_disposition = (
                f"attachment; filename=\"{encoded_base}{file_ext}\"; "
                f"filename*=UTF-8''{encoded_full}"
            )

        # Cache-Control
        cache_control = f"private, max-age={cache_max_age}"

        return {
            'Content-Type': content_type,
            'Content-Disposition': content_disposition,
            'Cache-Control': cache_control
        }

    # ==================== 私有验证方法 ====================

    def _check_keys_and_values_type(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查元数据的键和值必须是字符串
        """
        for key, value in metadata.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return False, f"元数据的键和值必须是字符串: {key}:{value}"
        return True, ""

    def _check_total_size(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查元数据总大小不得超过 8KB
        """
        total_size = 0
        for key, value in metadata.items():
            key_size = len(key.encode('utf-8'))
            value_size = len(value.encode('utf-8'))
            total_size += key_size + value_size
        if total_size > 8 * 1024:
            return False, f"元信息总大小超过8KB限制（当前 {total_size} 字节）"
        return True, ""

    def _check_key_count(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查元数据键数量不得超过 100 个
        """
        count = len(metadata)
        if count > 100:
            return False, f"元数据键数量超过100个限制（当前 {count} 个）"
        return True, ""

    def _check_keys_conflict(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查是否有重复的键名
        """
        seen_keys = set()
        for key in metadata.keys():
            key_lower = key.lower()
            if key_lower in seen_keys:
                return False, f"元数据键名重复: '{key}'"
            seen_keys.add(key_lower)
        return True, ""

    def _check_allowed_keys(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查元数据键名必须是允许的（x-oss-meta- 开头除外）
        """
        for key in metadata.keys():
            key_lower = key.lower()
            if key_lower not in self.ALLOWED_KEYS and not key_lower.startswith('x-oss-meta-'):
                return False, f"不允许存在的元数据键名: {key}"
        return True, ""

    def _check_values_length(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查元数据值长度不得超过 1024 字节，且不能包含控制字符
        """
        for key, value in metadata.items():
            if any(ord(char) < 32 for char in value):
                return False, f"元数据值包含控制字符: '{key}'"
            value_size = len(value.encode('utf-8'))
            if value_size > 1024:
                return False, f"元数据值长度超过1024字节限制: {key}"
        return True, ""

    def _check_content_type(self, metadata: dict, key: str) -> Tuple[bool, str]:
        """
        检查 Content-Type 是否与文件扩展名匹配
        """
        content_type = self._get_metadata_value('content-type', metadata)
        if content_type is None:
            return False, "Content-Type 不能为空"

        # 验证格式
        if not re.match(r'^[a-z]+\/[a-z0-9\-\+\._]+$', content_type, re.IGNORECASE):
            return False, f"无效的 Content-Type 格式: '{content_type}'"

        # 验证与扩展名是否匹配
        _, ext = os.path.splitext(key)
        ext = ext.lstrip('.').lower() if ext else ''
        expected_type = self.EXTENSION_TO_CONTENT_TYPE.get(ext, 'application/octet-stream')

        if content_type.lower() != expected_type.lower():
            return False, (
                f"Content-Type 错误，应为 {expected_type}，"
                f"实际为 {content_type}，请检查文件后缀"
            )

        return True, ""

    def _check_content_disposition(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查 Content-Disposition 格式是否正确

        允许的格式：
            - inline
            - attachment
            - attachment; filename="yourFileName"
            - attachment; filename="base"; filename*=UTF-8''encoded（RFC 5987）
        """
        content_disposition = self._get_metadata_value('content-disposition', metadata)
        if content_disposition is None:
            return True, ""  # Content-Disposition 是可选的

        value = content_disposition.strip().lower()

        if value == 'inline' or value == 'attachment':
            return True, ""

        # attachment; filename="xxx"
        pattern1 = r'^attachment;\s*filename\s*=\s*"([^"]*)"$'
        if re.match(pattern1, value, re.IGNORECASE):
            return True, ""

        # RFC 5987 格式
        pattern2 = r'^attachment;\s*filename\s*=\s*"[^"]*";\s*filename\*\s*=\s*UTF-8\'\'[^\s]*$'
        if re.match(pattern2, value, re.IGNORECASE):
            return True, ""

        return False, (
            f"无效的 Content-Disposition 格式: '{content_disposition}'。"
            f"允许: inline, attachment, attachment; filename=\"name\""
        )

    def _check_cache_control(self, metadata: dict) -> Tuple[bool, str]:
        """
        检查 Cache-Control 是否合法

        规则：
            - no-cache 和 no-store 互斥
            - public 和 private 互斥
            - max-age 必须赋值（如果存在）
            - max-age 值必须是非负整数
        """
        cache_control = self._get_metadata_value('cache-control', metadata)
        if cache_control is None:
            return True, ""  # Cache-Control 是可选的

        allowed_directives = {'no-cache', 'no-store', 'public', 'private', 'max-age'}

        # 分割指令
        directives = [d.strip() for d in cache_control.split(',')]

        seen_directives = set()
        found_conflict_groups = set()

        for directive in directives:
            parts = directive.split('=', 1)
            directive_name = parts[0].strip().lower()

            # 检查重复
            if directive_name in seen_directives:
                return False, f"重复的 Cache-Control 指令: '{directive_name}'"
            seen_directives.add(directive_name)

            # 检查是否有效指令
            if directive_name not in allowed_directives:
                return False, f"无效的 Cache-Control 指令: '{directive_name}'"

            # 检查互斥组
            for group in self.CONFLICT_GROUPS:
                if directive_name in group:
                    if found_conflict_groups & group:
                        conflict = found_conflict_groups & group
                        return False, f"Cache-Control 指令冲突: '{directive_name}' 与 '{conflict}' 互斥"
                    found_conflict_groups.add(directive_name)

            # 检查 max-age
            if directive_name == 'max-age':
                if len(parts) != 2:
                    return False, "max-age 必须赋值"
                if not parts[1].strip().isdigit():
                    return False, f"max-age 必须是整数: '{parts[1]}'"
                if int(parts[1].strip()) < 0:
                    return False, f"max-age 不能为负数: {parts[1]}"
        return True, ""

    def _get_metadata_value(self, key: str, metadata: dict) -> Optional[str]:
        """
        获取元数据中指定键的值（忽略大小写）

        :param key: 键名
        :param metadata: 元数据字典
        :return: 键值，如果不存在返回 None
        """
        key_lower = key.lower()
        for meta_key, meta_value in metadata.items():
            if meta_key.lower() == key_lower:
                return meta_value
        return None
