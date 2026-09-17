"""
阿里云 OSS 库 - 底层操作实现

本模块封装 oss2 SDK 的底层操作，提供文件上传、下载、删除、列举等核心功能。

主要功能：
    - 普通上传/下载（小文件）
    - 分片上传/下载（大文件，自动分片）
    - 单文件删除/批量删除
    - 文件列举（支持分页）
    - 文件复制
    - 元数据读写

内部使用，通过 Session 对外暴露，不直接被用户调用。
"""

import os
import time
import random
import datetime
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

import oss2
from oss2 import SizedFileAdapter
from oss2.models import PartInfo

from .config import MIN_MULTITHREAD_SIZE, MAX_RETRY_COUNT, RETRY_DELAY
from .exceptions import UploadError, DownloadError, DeleteError, ListError, CopyError, OperationError


class Operations:
    """
    OSS 底层操作类

    封装所有 OSS 文件操作，支持普通传输和分片传输。

    使用示例：
        ops = Operations(bucket)
        ops.upload("local.txt", "remote.txt")
        ops.download("remote.txt", "local.txt")
    """

    def __init__(self, bucket):
        """
        初始化操作类

        :param bucket: oss2.Bucket 实例
        """
        self._bucket = bucket

    # ==================== 上传 ====================

    def upload(self, local_path: str, remote_key: str) -> bool:
        """
        上传文件

        根据文件大小自动选择普通上传或分片上传。

        :param local_path: 本地文件路径
        :param remote_key: OSS 上的键名
        :return: 是否上传成功
        :raises UploadError: 上传失败时抛出
        """
        if not os.path.exists(local_path):
            raise UploadError(f"本地文件不存在: {local_path}")

        if self._bucket.object_exists(remote_key):
            raise UploadError(f"OSS 上已存在相同键名的文件: {remote_key}")

        file_size = os.path.getsize(local_path)

        if file_size > MIN_MULTITHREAD_SIZE:
            return self._multipart_upload(remote_key, local_path, file_size)
        else:
            return self._normal_upload(remote_key, local_path)

    def _normal_upload(self, remote_key: str, local_path: str) -> bool:
        """
        普通上传（小文件）

        :param remote_key: OSS 键名
        :param local_path: 本地文件路径
        :return: 是否成功
        """
        try:
            self._bucket.put_object_from_file(remote_key, local_path)
            return True
        except Exception as e:
            raise UploadError(f"普通上传失败: {str(e)}")

    def _multipart_upload(self, remote_key: str, local_path: str, file_size: int) -> bool:
        """
        分片上传（大文件）

        :param remote_key: OSS 键名
        :param local_path: 本地文件路径
        :param file_size: 文件大小（字节）
        :return: 是否成功
        """
        upload_id = self._bucket.init_multipart_upload(remote_key).upload_id

        try:
            part_size = self._calculate_part_size(file_size)
            part_count = (file_size + part_size - 1) // part_size

            with ThreadPoolExecutor(max_workers=self._calculate_thread_count(file_size)) as executor:
                futures = []
                part_etags = []

                for i in range(part_count):
                    part_number = i + 1
                    start_pos = i * part_size
                    current_part_size = min(part_size, file_size - start_pos)

                    future = executor.submit(
                        self._upload_part_with_retry,
                        remote_key, local_path, upload_id,
                        part_number, start_pos, current_part_size
                    )
                    futures.append((part_number, future))

                for part_number, future in futures:
                    try:
                        etag = future.result()
                        part_etags.append(PartInfo(part_number, etag))
                    except Exception as e:
                        raise UploadError(f"分片 {part_number} 上传失败: {str(e)}")

            self._bucket.complete_multipart_upload(remote_key, upload_id, part_etags)
            return True

        except UploadError:
            self._bucket.abort_multipart_upload(remote_key, upload_id)
            raise
        except Exception as e:
            try:
                self._bucket.abort_multipart_upload(remote_key, upload_id)
            except Exception:
                pass
            raise UploadError(f"分片上传失败: {str(e)}")

    def _upload_part_with_retry(
        self, remote_key: str, local_path: str,
        upload_id: str, part_number: int,
        start_pos: int, part_size: int
    ) -> str:
        """
        分片上传（带重试）

        :return: etag
        """
        retry_count = 0
        base_delay = RETRY_DELAY
        last_error = None

        while retry_count <= MAX_RETRY_COUNT:
            try:
                return self._upload_part(
                    remote_key, local_path, upload_id,
                    part_number, start_pos, part_size
                )
            except oss2.exceptions.OssError as e:
                last_error = e
                if e.status == 500:
                    base_delay *= 2
                elif e.status == 429:
                    base_delay = max(base_delay, 10)

                retry_count += 1
                if retry_count <= MAX_RETRY_COUNT:
                    delay = base_delay * retry_count + random.uniform(0, 1)
                    time.sleep(delay)
            except Exception as e:
                last_error = e
                break

        raise UploadError(f"分片 {part_number} 上传失败: {str(last_error)}")

    def _upload_part(
        self, remote_key: str, local_path: str,
        upload_id: str, part_number: int,
        start_pos: int, part_size: int
    ) -> str:
        """
        单个分片上传

        :return: etag
        """
        with open(local_path, 'rb') as file_obj:
            file_obj.seek(start_pos)
            result = self._bucket.upload_part(
                remote_key, upload_id, part_number,
                SizedFileAdapter(file_obj, part_size)
            )
            return result.etag

    # ==================== 下载 ====================

    def download(self, remote_key: str, local_path: str) -> bool:
        """
        下载文件

        根据文件大小自动选择普通下载或分片下载。

        :param remote_key: OSS 键名
        :param local_path: 本地保存路径
        :return: 是否成功
        :raises DownloadError: 下载失败时抛出
        """
        # 确保本地目录存在
        local_dir = os.path.dirname(local_path)
        if local_dir and not os.path.exists(local_dir):
            os.makedirs(local_dir, exist_ok=True)

        head_info = self._bucket.head_object(remote_key)
        file_size = head_info.content_length

        if file_size > MIN_MULTITHREAD_SIZE:
            return self._multipart_download(remote_key, local_path, file_size)
        else:
            return self._normal_download(remote_key, local_path)

    def _normal_download(self, remote_key: str, local_path: str) -> bool:
        """
        普通下载（小文件）

        :param remote_key: OSS 键名
        :param local_path: 本地文件路径
        :return: 是否成功
        """
        try:
            self._bucket.get_object_to_file(remote_key, local_path)
            return True
        except Exception as e:
            raise DownloadError(f"普通下载失败: {str(e)}")

    def _multipart_download(self, remote_key: str, local_path: str, file_size: int) -> bool:
        """
        分片下载（大文件）

        :param remote_key: OSS 键名
        :param local_path: 本地文件路径
        :param file_size: 文件大小（字节）
        :return: 是否成功
        """
        part_size = self._calculate_part_size(file_size)
        part_count = (file_size + part_size - 1) // part_size

        temp_dir = None
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            temp_dir = os.path.join(os.path.dirname(local_path), f"temp_{os.path.basename(remote_key)}_{timestamp}")
            os.makedirs(temp_dir, exist_ok=True)

            thread_count = self._calculate_thread_count(file_size)

            with ThreadPoolExecutor(max_workers=thread_count) as executor:
                futures = []

                for i in range(part_count):
                    part_number = i + 1
                    start_pos = i * part_size
                    current_part_size = min(part_size, file_size - start_pos)
                    part_file = os.path.join(temp_dir, f"part_{part_number}.part")

                    future = executor.submit(
                        self._download_part_with_retry,
                        remote_key, part_file, start_pos, current_part_size
                    )
                    futures.append((part_number, future))

                for part_number, future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        raise DownloadError(f"分片 {part_number} 下载失败: {str(e)}")

            # 合并分片文件
            with open(local_path, 'wb') as final_file:
                for i in range(1, part_count + 1):
                    part_file = os.path.join(temp_dir, f"part_{i}.part")
                    with open(part_file, 'rb') as part_f:
                        final_file.write(part_f.read())
                    os.remove(part_file)

            return True

        except DownloadError:
            raise
        except Exception as e:
            raise DownloadError(f"分片下载失败: {str(e)}")
        finally:
            if temp_dir and os.path.exists(temp_dir):
                try:
                    os.rmdir(temp_dir)
                except Exception:
                    pass

    def _download_part_with_retry(
        self, remote_key: str, part_file: str,
        start_pos: int, part_size: int
    ):
        """
        分片下载（带重试）
        """
        retry_count = 0
        base_delay = RETRY_DELAY

        while retry_count <= MAX_RETRY_COUNT:
            try:
                return self._download_part(remote_key, part_file, start_pos, part_size)
            except oss2.exceptions.OssError as e:
                if e.status == 500:
                    base_delay *= 2
                elif e.status == 429:
                    base_delay = max(base_delay, 10)

                retry_count += 1
                if retry_count <= MAX_RETRY_COUNT:
                    delay = base_delay * retry_count + random.uniform(0, 1)
                    time.sleep(delay)
            except Exception as e:
                raise DownloadError(f"分片下载失败: {str(e)}")

        raise DownloadError("分片下载失败，已达最大重试次数")

    def _download_part(self, remote_key: str, part_file: str, start_pos: int, part_size: int):
        """
        单个分片下载
        """
        headers = {'Range': f"bytes={start_pos}-{start_pos + part_size - 1}"}
        result = self._bucket.get_object(remote_key, headers=headers)

        with open(part_file, 'wb') as part_f:
            for chunk in result:
                part_f.write(chunk)

    # ==================== 删除 ====================

    def delete(self, remote_key: str) -> bool:
        """
        删除单个文件

        :param remote_key: OSS 键名
        :return: 是否成功
        :raises DeleteError: 删除失败时抛出
        """
        try:
            self._bucket.delete_object(remote_key)
            return True
        except oss2.exceptions.OssError as e:
            if e.status == 404:
                return True  # 文件不存在，视为删除成功
            raise DeleteError(f"删除文件失败: {str(e)}")
        except Exception as e:
            raise DeleteError(f"删除文件失败: {str(e)}")

    def batch_delete(self, remote_keys: List[str]) -> bool:
        """
        批量删除文件

        :param remote_keys: OSS 键名列表
        :return: 是否成功
        :raises DeleteError: 删除失败时抛出
        """
        try:
            self._bucket.batch_delete_objects(remote_keys)
            return True
        except Exception as e:
            raise DeleteError(f"批量删除失败: {str(e)}")

    # ==================== 列举 ====================

    def list(self, prefix: str = "", max_keys: int = 100) -> List[str]:
        """
        列举文件

        :param prefix: 前缀过滤
        :param max_keys: 每次最多返回数量（条）
        :return: 文件键名列表
        :raises ListError: 列举失败时抛出
        """
        try:
            result = self._bucket.list_objects_v2(prefix=prefix, max_keys=max_keys)
            return [obj.key for obj in result.object_list]
        except Exception as e:
            raise ListError(f"列举文件失败: {str(e)}")

    def list_all(self, prefix: str = "") -> List[str]:
        """
        列举所有文件（自动处理分页）

        :param prefix: 前缀过滤
        :return: 所有文件键名列表
        :raises ListError: 列举失败时抛出
        """
        all_keys = []
        continuation_token = None

        try:
            while True:
                if continuation_token:
                    result = self._bucket.list_objects_v2(
                        prefix=prefix,
                        max_keys=1000,
                        continuation_token=continuation_token
                    )
                else:
                    result = self._bucket.list_objects_v2(prefix=prefix, max_keys=1000)

                all_keys.extend([obj.key for obj in result.object_list])

                if result.is_truncated:
                    continuation_token = result.next_continuation_token
                else:
                    break

            return all_keys

        except Exception as e:
            raise ListError(f"列举文件失败: {str(e)}")

    # ==================== 复制 ====================

    def copy(self, src_key: str, dst_key: str) -> bool:
        """
        复制文件

        :param src_key: 源键名
        :param dst_key: 目标键名
        :return: 是否成功
        :raises CopyError: 复制失败时抛出
        """
        try:
            self._bucket.copy_object(
                self._bucket.bucket_name,
                source_key=src_key,
                target_key=dst_key
            )
            return True
        except Exception as e:
            raise CopyError(f"复制文件失败: {str(e)}")

    # ==================== 元数据 ====================

    def get_metadata(self, remote_key: str) -> Dict[str, Any]:
        """
        获取文件元数据

        :param remote_key: OSS 键名
        :return: 元数据字典
        :raises OperationError: 获取失败时抛出
        """
        try:
            result = self._bucket.head_object(remote_key)
            return {
                'content_type': result.content_type,
                'content_length': result.content_length,
                'last_modified': result.last_modified,
                'etag': result.etag
            }
        except Exception as e:
            raise OperationError(f"获取元数据失败: {str(e)}")

    def update_metadata(self, remote_key: str, metadata: Dict[str, str]) -> bool:
        """
        更新文件元数据

        :param remote_key: OSS 键名
        :param metadata: 元数据字典
        :return: 是否成功
        :raises OperationError: 更新失败时抛出
        """
        try:
            self._bucket.update_object_meta(remote_key, metadata)
            return True
        except Exception as e:
            raise OperationError(f"更新元数据失败: {str(e)}")

    # ==================== 工具方法 ====================

    @staticmethod
    def _calculate_part_size(file_size: int) -> int:
        """
        动态计算分片大小
        """
        if file_size <= 10 * 1024 * 1024:
            return 1 * 1024 * 1024
        elif file_size <= 100 * 1024 * 1024:
            return 5 * 1024 * 1024
        elif file_size <= 1024 * 1024 * 1024:
            return 10 * 1024 * 1024
        else:
            return 20 * 1024 * 1024

    @staticmethod
    def _calculate_thread_count(file_size: int) -> int:
        """
        动态计算线程数量
        """
        cpu_count = os.cpu_count() or 4
        base_threads = min(cpu_count * 2, 8)

        if file_size <= 50 * 1024 * 1024:
            return min(base_threads, 4)
        elif file_size <= 500 * 1024 * 1024:
            return min(base_threads, 6)
        else:
            return base_threads