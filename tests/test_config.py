"""测试配置加载模块"""

import os
import tempfile

import pytest

from src.config import load_config, get_enabled_sources, get_lite_sources, AppConfig, SourceConfig

VALID_CONFIG = """sources:
  - name: EasyList
    url: https://easylist-downloads.adblockplus.org/easylist.txt
    priority: 1
    lite: true
    enabled: true
  - name: EasyPrivacy
    url: https://easylist-downloads.adblockplus.org/easyprivacy.txt
    priority: 2
    lite: true
    enabled: true
  - name: DisabledSource
    url: https://example.com/disabled.txt
    priority: 3
    lite: false
    enabled: false

settings:
  output_dir: dist
  output_file: filter.txt
  request_timeout: 30
"""


def test_load_valid_config():
    """测试加载有效配置"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(VALID_CONFIG)
        temp_path = f.name

    try:
        config = load_config(temp_path)

        assert isinstance(config, AppConfig)
        assert len(config.sources) == 3
        assert config.sources[0].name == "EasyList"
        assert config.sources[0].priority == 1
        assert config.sources[0].enabled is True
        assert config.sources[2].name == "DisabledSource"
        assert config.sources[2].enabled is False
        assert config.output_dir == "dist"
        assert config.request_timeout == 30
    finally:
        os.unlink(temp_path)


def test_load_config_not_found():
    """测试加载不存在的配置"""
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")


def test_get_enabled_sources():
    """测试获取启用的源并按优先级排序"""
    config = AppConfig(
        sources=[
            SourceConfig(name="Low", url="http://low.com", priority=3, enabled=True),
            SourceConfig(name="High", url="http://high.com", priority=1, enabled=True),
            SourceConfig(name="Disabled", url="http://disabled.com", priority=2, enabled=False),
            SourceConfig(name="Medium", url="http://medium.com", priority=2, enabled=True),
        ]
    )

    enabled = get_enabled_sources(config)

    assert len(enabled) == 3
    assert enabled[0].name == "High"   # priority 1
    assert enabled[1].name == "Medium"  # priority 2
    assert enabled[2].name == "Low"     # priority 3

    # 确认 disabled 不在列表中
    names = [s.name for s in enabled]
    assert "Disabled" not in names
