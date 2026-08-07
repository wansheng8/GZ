"""测试下载器模块 - 覆盖 ETag 提取与持久化"""

import asyncio
import json
import os
import tempfile
import unittest.mock

from src.config import SourceConfig
from src.downloader import (
    DownloadResult,
    load_etags,
    save_etags,
    download_single,
    _extract_etag,
)


def make_source(name="TestSource", priority=1):
    return SourceConfig(name=name, url="http://example.com/filter.txt", priority=priority)


def make_result(src, status_code=200, changed=True, error=None, etag=None):
    return DownloadResult(
        source=src,
        content="" if changed else "",
        rule_count=0,
        status_code=status_code,
        changed=changed,
        error=error,
        etag=etag,
    )


def test_save_etags_persists_successful_only():
    """测试 save_etags 只持久化成功且带令牌的源"""
    with tempfile.TemporaryDirectory() as tmpdir:
        src = make_source()
        results = {
            "TestSource": make_result(src, etag='"v1"'),
            "FailedSource": make_result(
                src, status_code=0, changed=False, error="timeout", etag=None
            ),
        }

        save_etags(tmpdir, "etags.json", results)

        with open(os.path.join(tmpdir, "etags.json"), "r", encoding="utf-8") as f:
            etags = json.load(f)
        assert etags == {"TestSource": '"v1"'}


def test_save_etags_preserves_old_on_failure():
    """测试下载失败的源保留旧缓存值"""
    with tempfile.TemporaryDirectory() as tmpdir:
        etag_path = os.path.join(tmpdir, "etags.json")
        with open(etag_path, "w", encoding="utf-8") as f:
            json.dump({"OldSource": '"old"', "TestSource": '"stale"'}, f)

        src = make_source()
        results = {
            "TestSource": make_result(src, etag='"new"'),
            "OldSource": make_result(
                src, status_code=0, changed=False, error="HTTP 500", etag=None
            ),
        }

        save_etags(tmpdir, "etags.json", results)

        with open(etag_path, "r", encoding="utf-8") as f:
            etags = json.load(f)
        assert etags["TestSource"] == '"new"'
        assert etags["OldSource"] == '"old"'


def test_load_etags_missing_file():
    """测试缓存文件不存在时返回空字典"""
    assert load_etags("/nonexistent", "etags.json") == {}


def test_extract_etag_prefers_etag():
    """测试优先提取 ETag"""
    resp = unittest.mock.MagicMock()
    resp.headers = {"ETag": '"etag1"', "Last-Modified": "Mon, 01 Jan 2026 00:00:00 GMT"}
    assert _extract_etag(resp, None) == '"etag1"'


def test_extract_etag_fallback_last_modified():
    """测试无 ETag 时回退 Last-Modified"""
    resp = unittest.mock.MagicMock()
    resp.headers = {"Last-Modified": "Mon, 01 Jan 2026 00:00:00 GMT"}
    assert _extract_etag(resp, None) == "Mon, 01 Jan 2026 00:00:00 GMT"


def test_extract_etag_304_fallback_old():
    """测试 304 且响应无令牌时保留旧值"""
    resp = unittest.mock.MagicMock()
    resp.headers = {}
    assert _extract_etag(resp, '"old"') == '"old"'


class MockResponse:
    """模拟 aiohttp.ClientResponse"""

    def __init__(self, status=200, headers=None, body="||example.com^\n"):
        self.status = status
        self.headers = headers or {}
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def text(self, encoding="utf-8", errors="strict"):
        return self._body


def test_download_single_200_extracts_etag():
    """测试 200 响应提取 ETag 并标记 changed"""
    src = make_source()
    session = unittest.mock.MagicMock()
    session.get.return_value = MockResponse(200, {"ETag": '"v1"'})

    result = asyncio.run(
        download_single(src, session, etag=None, timeout=30, retry_delay=1)
    )

    assert result.status_code == 200
    assert result.changed is True
    assert result.etag == '"v1"'
    assert result.rule_count == 1


def test_download_single_sends_conditional_headers():
    """测试携带上次令牌发起条件请求"""
    src = make_source()
    session = unittest.mock.MagicMock()
    session.get.return_value = MockResponse(200, {"ETag": '"v2"'})

    asyncio.run(download_single(src, session, etag='"v1"', timeout=30, retry_delay=1))

    session.get.assert_called_once()
    headers = session.get.call_args.kwargs["headers"]
    assert headers["If-None-Match"] == '"v1"'
    assert headers["If-Modified-Since"] == '"v1"'


def test_download_single_304_not_changed():
    """测试 304 响应不更新内容但提取新令牌"""
    src = make_source()
    session = unittest.mock.MagicMock()
    session.get.return_value = MockResponse(304, {"ETag": '"v2"'})

    result = asyncio.run(
        download_single(src, session, etag='"v1"', timeout=30, retry_delay=1)
    )

    assert result.status_code == 304
    assert result.changed is False
    assert result.content == ""
    assert result.etag == '"v2"'


def test_download_single_304_without_etag_keeps_old():
    """测试 304 且响应无令牌时保留旧值"""
    src = make_source()
    session = unittest.mock.MagicMock()
    session.get.return_value = MockResponse(304, {})

    result = asyncio.run(
        download_single(src, session, etag='"v1"', timeout=30, retry_delay=1)
    )

    assert result.changed is False
    assert result.etag == '"v1"'
