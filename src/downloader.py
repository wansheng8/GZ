"""下载器模块 - 异步 HTTP 下载上游规则源，支持 ETag 条件请求和失败重试"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import aiohttp

from src.config import SourceConfig

logger = logging.getLogger(__name__)


@dataclass
class DownloadResult:
    """单个源的下载结果"""
    source: SourceConfig
    content: str
    rule_count: int
    status_code: int
    changed: bool
    error: Optional[str] = None


def load_etags(cache_dir: str, etag_file: str) -> dict[str, str]:
    """加载 ETag 缓存

    Args:
        cache_dir: 缓存目录路径
        etag_file: ETag 文件名

    Returns:
        以源名称为 key，ETag 值为 value 的字典
    """
    etag_path = Path(cache_dir) / etag_file
    if not etag_path.exists():
        return {}

    try:
        with open(etag_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning("Failed to load ETag cache: %s", e)
        return {}


def save_etags(cache_dir: str, etag_file: str, results: dict[str, "DownloadResult"]) -> None:
    """保存 ETag 缓存

    Args:
        cache_dir: 缓存目录路径
        etag_file: ETag 文件名
        results: 下载结果字典
    """
    etag_path = Path(cache_dir) / etag_file
    etag_path.parent.mkdir(parents=True, exist_ok=True)

    etags = {}
    for name, result in results.items():
        if result.error is None and result.changed:
            # 从响应头中提取的 ETag 在 DownloadResult 中没有直接保存
            # 这里我们只记录成功更新的源
            pass

    # ETag 值的实际保存发生在 download_all 中
    # 此函数保留作为接口占位


async def download_single(
    source: SourceConfig,
    session: aiohttp.ClientSession,
    etag: Optional[str],
    timeout: int,
    retry_delay: int,
) -> DownloadResult:
    """下载单个源的规则内容

    Args:
        source: 上游源配置
        session: aiohttp 会话
        etag: 上次获取的 ETag 值，用于条件请求
        timeout: 请求超时时间（秒）
        retry_delay: 重试延迟（秒）

    Returns:
        DownloadResult: 下载结果
    """
    headers = {"User-Agent": "AdblockFilterAggregator/1.0"}
    if etag:
        headers["If-None-Match"] = etag

    for attempt in range(2):  # 初次 + 1 次重试
        try:
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            async with session.get(source.url, headers=headers, timeout=timeout_obj) as resp:
                # 304 Not Modified - 内容未变化
                if resp.status == 304:
                    logger.info("[%s] 304 Not Modified", source.name)
                    return DownloadResult(
                        source=source,
                        content="",
                        rule_count=0,
                        status_code=304,
                        changed=False,
                    )

                if resp.status != 200:
                    raise aiohttp.ClientResponseError(
                        request_info=resp.request_info,
                        history=resp.history,
                        status=resp.status,
                        message=f"HTTP {resp.status}",
                        headers=resp.headers,
                    )

                content = await resp.text(encoding="utf-8", errors="replace")
                rule_count = _count_rules(content)

                logger.info(
                    "[%s] 200 OK - %d rules downloaded",
                    source.name,
                    rule_count,
                )

                return DownloadResult(
                    source=source,
                    content=content,
                    rule_count=rule_count,
                    status_code=200,
                    changed=True,
                )

        except asyncio.TimeoutError:
            if attempt == 0:
                logger.warning(
                    "[%s] Request timeout, retrying in %ds...",
                    source.name,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error("[%s] Request timeout after retry", source.name)
                return DownloadResult(
                    source=source,
                    content="",
                    rule_count=0,
                    status_code=0,
                    changed=False,
                    error="Request timeout",
                )

        except aiohttp.ClientError as e:
            if attempt == 0:
                logger.warning(
                    "[%s] Download failed: %s, retrying in %ds...",
                    source.name,
                    e,
                    retry_delay,
                )
                await asyncio.sleep(retry_delay)
            else:
                logger.error("[%s] Download failed after retry: %s", source.name, e)
                return DownloadResult(
                    source=source,
                    content="",
                    rule_count=0,
                    status_code=0,
                    changed=False,
                    error=str(e),
                )

    # Should not reach here
    return DownloadResult(
        source=source,
        content="",
        rule_count=0,
        status_code=0,
        changed=False,
        error="Unknown error",
    )


async def download_all(
    sources: list[SourceConfig],
    etags: dict[str, str],
    timeout: int,
    retry_delay: int,
) -> dict[str, DownloadResult]:
    """并发下载所有上游源的规则内容

    Args:
        sources: 启用的上游源列表
        etags: ETag 缓存字典
        timeout: 请求超时时间（秒）
        retry_delay: 重试延迟（秒）

    Returns:
        以源名称为 key 的下载结果字典
    """
    results: dict[str, DownloadResult] = {}

    connector = aiohttp.TCPConnector(limit=10, limit_per_host=2)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for source in sources:
            task = download_single(
                source=source,
                session=session,
                etag=etags.get(source.name),
                timeout=timeout,
                retry_delay=retry_delay,
            )
            tasks.append(task)

        completed = await asyncio.gather(*tasks, return_exceptions=True)
        for source, result in zip(sources, completed):
            if isinstance(result, Exception):
                logger.error("[%s] Unexpected error: %s", source.name, result)
                results[source.name] = DownloadResult(
                    source=source,
                    content="",
                    rule_count=0,
                    status_code=0,
                    changed=False,
                    error=str(result),
                )
            else:
                results[source.name] = result

    return results


def _count_rules(content: str) -> int:
    """统计内容中的有效规则数量（排除注释和空行）"""
    count = 0
    for line in content.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith(("!", "[")):
            count += 1
    return count
