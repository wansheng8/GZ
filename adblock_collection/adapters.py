"""客户端适配产物生成。

为各受支持客户端生成一对一适配文件，写入 ``dist/adapters/``：只做「引用 + 配置」，
拦截范围完全来自被引用的规范规则集，不新增任何拦截判定，也不改动任何既有产物。
相同配置与相同规范产物在多次构建中产生逐字节一致的文件（无时间戳、无随机标识）。

连接层适配（mihomo / sing-box / Surge / Quantumult X）仅在对应 ``rulesets/`` 规范文件
存在时生成；``--no-rulesets`` 或未生成规则集的离线场景下自动跳过，不影响其余适配。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from .build_pipeline import BuildError
from .writer import HOMEPAGE

LOG = logging.getLogger("adblock_collection")

ADAPTER_DIRNAME = "adapters"
DEFAULT_REPOSITORY = "wansheng8/GZ"
DEFAULT_BRANCH = "main"

# 适配产物引用的规范产物（相对 ``dist/`` 根）
RULESET_CLASH = "rulesets/adblock_clash.yaml"
RULESET_SINGBOX = "rulesets/adblock_singbox.json"
RULESET_SURGE_DOMAIN_SET = "rulesets/adblock_surge_domain_set.txt"
RULESET_QUANX = "rulesets/adblock_quanx.list"
FULL_DOMAINS = "adblock_collection_full_domains.txt"
FULL_DNS = "adblock_collection_full_dns.txt"
FULL_DNS_IPV6 = "adblock_collection_full_dns_ipv6.txt"
FULL_BROWSER = "adblock_collection_full.txt"
FULL_BROWSER_MIRROR = "adblock_collection_full_jsdelivr.txt"
UBO_ENHANCE = "adblock_collection_ubo_enhance.txt"


@dataclass(frozen=True)
class PublishConfig:
    """发布基址配置：仓库、分支与两套等价基址（均以 ``/`` 结尾）。"""

    repository: str
    branch: str
    raw_base: str
    mirror_base: str


def _derive_bases(repository: str, branch: str) -> tuple[str, str]:
    raw = f"https://raw.githubusercontent.com/{repository}/{branch}/dist/"
    mirror = f"https://cdn.jsdelivr.net/gh/{repository}@{branch}/dist/"
    return raw, mirror


def load_publish_config(config_path: Path) -> PublishConfig:
    """从 ``config/sources.yaml`` 顶层 ``publish`` 段读取发布配置。

    缺失或字段为空时回退内置默认仓库与分支，保证夹具构建与离线场景可复现；
    显式提供 ``raw_base`` / ``mirror_base`` 时原样使用（本地镜像或前向分支）。
    """
    import yaml

    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    cfg = data.get("publish") or {}
    if not isinstance(cfg, dict):
        raise BuildError("config 的 publish 段必须是映射")
    repository = str(cfg.get("repository") or DEFAULT_REPOSITORY).strip() or DEFAULT_REPOSITORY
    branch = str(cfg.get("branch") or DEFAULT_BRANCH).strip() or DEFAULT_BRANCH
    default_raw, default_mirror = _derive_bases(repository, branch)
    raw_base = str(cfg.get("raw_base") or default_raw).strip() or default_raw
    mirror_base = str(cfg.get("mirror_base") or default_mirror).strip() or default_mirror
    if not raw_base.endswith("/"):
        raw_base += "/"
    if not mirror_base.endswith("/"):
        mirror_base += "/"
    return PublishConfig(repository, branch, raw_base, mirror_base)


def _join(base: str, rel: str) -> str:
    return base + rel


def _presence(rulesets_dir: Path | None, rel: str) -> bool:
    """连接层适配引用的规范规则集是否已生成。"""
    if rulesets_dir is None:
        return False
    return (rulesets_dir / Path(rel).name).exists()


# ---------------------------------------------------------------------------
# 各客户端适配内容（纯函数，返回完整文件文本）
# ---------------------------------------------------------------------------


def _adapter_mihomo(p: PublishConfig) -> str:
    raw = _join(p.raw_base, RULESET_CLASH)
    mirror = _join(p.mirror_base, RULESET_CLASH)
    return "\n".join(
        [
            "# Adblock Rule Collection — mihomo / Clash Meta 适配",
            "# 用法：把 rule-providers 与 rules 两段合并进你的 config.yaml。",
            "#",
            f"# 规范基址：{raw}",
            f"# 镜像基址：{mirror}",
            f"# 主页：{HOMEPAGE}",
            "",
            "rule-providers:",
            "  adblock:",
            "    type: http",
            "    behavior: domain",
            "    format: yaml",
            f'    url: "{raw}"',
            "    path: ./ruleset/adblock.yaml",
            "    interval: 86400",
            "rules:",
            "  - RULE-SET,adblock,REJECT",
            "",
        ]
    )


def _adapter_singbox(p: PublishConfig) -> str:
    raw = _join(p.raw_base, RULESET_SINGBOX)
    mirror = _join(p.mirror_base, RULESET_SINGBOX)
    payload = {
        "route": {
            "rule_set": [
                {
                    "type": "remote",
                    "tag": "adblock",
                    "format": "source",
                    "url": raw,
                    "update_interval": "1d",
                }
            ],
            "rules": [{"rule_set": "adblock", "action": "reject"}],
        }
    }
    header = "\n".join(
        [
            "// Adblock Rule Collection — sing-box 适配",
            "// 用法：把 route.rule_set 与 route.rules 合并进你的 config.json。",
            "// 采用远端源格式规则集（format: source），需要 sing-box 1.11+，无需手动编译。",
            f"// 规范基址：{raw}",
            f"// 镜像基址：{mirror}",
            f"// 主页：{HOMEPAGE}",
            "",
        ]
    )
    return header + json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def _adapter_surge(p: PublishConfig) -> str:
    raw = _join(p.raw_base, RULESET_SURGE_DOMAIN_SET)
    mirror = _join(p.mirror_base, RULESET_SURGE_DOMAIN_SET)
    return "\n".join(
        [
            "# Adblock Rule Collection — Surge 适配",
            "# 用法：把下面一行加入配置文件的 [Rule] 段。",
            "#",
            f"# 规范基址：{raw}",
            f"# 镜像基址：{mirror}",
            "#",
            f"DOMAIN-SET,{mirror},REJECT",
            "",
        ]
    )


def _adapter_quanx(p: PublishConfig, rulesets_dir: Path | None) -> str:
    base_rel = RULESET_QUANX
    parts = sorted(rulesets_dir.glob("adblock_quanx_part*.list")) if rulesets_dir else []
    lines = [
        "# Adblock Rule Collection — Quantumult X 适配",
        "# 用法：把下列 filter_remote 行加入配置文件的 [filter_remote] 段。",
        "#   force-remote-filter=1 表示由 Quantumult X 解析远端规则。",
        "#",
        f"# 规范基址：{_join(p.raw_base, base_rel)}",
        f"# 镜像基址：{_join(p.mirror_base, base_rel)}",
        "#",
    ]
    lines.append(
        f"filter_remote = {_join(p.mirror_base, base_rel)}, tag=Adblock, force-remote-filter=1"
    )
    for part in parts:
        number = part.stem.rsplit("part", 1)[-1].lstrip("0") or "1"
        lines.append(
            f"filter_remote = {_join(p.mirror_base, 'rulesets/' + part.name)}, "
            f"tag=Adblock-{number}, force-remote-filter=1"
        )
    return "\n".join(lines) + "\n"


def _adapter_adguardhome(p: PublishConfig) -> str:
    url = _join(p.raw_base, FULL_DOMAINS)
    return "\n".join(
        [
            "# Adblock Rule Collection — AdGuard Home 适配",
            "# 用法：把下面 filters 片段合并进 AdGuardHome.yaml 的 filters 段后重启。",
            "# 本片段只含拦截列表，不含放行规则；如需放行，请另行按需导入。",
            "#",
            f"# 主页：{HOMEPAGE}",
            "",
            "filters:",
            "  - enabled: true",
            f"    url: {url}",
            "    name: Adblock Collection (DNS domains)",
            "",
        ]
    )


def _adapter_pihole(p: PublishConfig) -> str:
    return "\n".join(
        [
            "# Adblock Rule Collection — Pi-hole 适配（adlists）",
            "# 用法：把下面一行追加到 adlists.list（或用 Web 界面 Adlists 添加）。",
            "#",
            f"# 主页：{HOMEPAGE}",
            _join(p.raw_base, FULL_DNS),
            "",
        ]
    )


def _adapter_dnsmasq(p: PublishConfig) -> str:
    url = _join(p.raw_base, FULL_DNS)
    return "\n".join(
        [
            "# Adblock Rule Collection — dnsmasq 适配",
            "# dnsmasq 不能直接拉取远程 URL，请先把 hosts 文件下载到本地：",
            f"#   curl -o /etc/dnsmasq.d/adblock_collection_full_dns.txt {url}",
            "#",
            "# 用法：把下面一行加入 dnsmasq 配置（如 /etc/dnsmasq.d/adblock.conf）后重启。",
            "",
            "addn-hosts=/etc/dnsmasq.d/adblock_collection_full_dns.txt",
            "",
        ]
    )


def _adapter_hosts_guide(p: PublishConfig) -> str:
    v4 = _join(p.raw_base, FULL_DNS)
    v4m = _join(p.mirror_base, FULL_DNS)
    v6 = _join(p.raw_base, FULL_DNS_IPV6)
    v6m = _join(p.mirror_base, FULL_DNS_IPV6)
    return "\n".join(
        [
            "# Adblock Rule Collection — 系统 hosts 接入指引",
            "",
            "把下面的 hosts 内容追加到系统 hosts 文件末尾。文件为 `0.0.0.0 domain` 形式，",
            "命中域名被解析到黑洞地址，从而在系统层面拦截。",
            "",
            "## 下载地址",
            "",
            f"- IPv4 规范：{v4}",
            f"- IPv4 镜像：{v4m}",
            f"- IPv6 规范：{v6}",
            f"- IPv6 镜像：{v6m}",
            "",
            "## 各系统 hosts 路径",
            "",
            "- Windows：`C:\\Windows\\System32\\drivers\\etc\\hosts`（需管理员权限编辑）",
            "- macOS / Linux：`/etc/hosts`（`sudo` 编辑）",
            "- Android：需 root，路径 `/system/etc/hosts`（或用支持本地 hosts 的 AdAway 等）",
            "",
            "## 写入命令（Linux / macOS）",
            "",
            "```bash",
            f"curl -o /tmp/adblock_hosts.txt {v4}",
            "cat /tmp/adblock_hosts.txt | sudo tee -a /etc/hosts >/dev/null",
            "```",
            "",
            "写入后刷新 DNS 缓存（macOS：`sudo dscacheutil -flushcache`；",
            "Windows：`ipconfig /flushdns`）。移除时删除追加段落即可。",
            "",
        ]
    )


def _adapter_browsers_guide(p: PublishConfig) -> str:
    full = _join(p.raw_base, FULL_BROWSER)
    fullm = _join(p.mirror_base, FULL_BROWSER_MIRROR)
    enhance = _join(p.raw_base, UBO_ENHANCE)
    enhm = _join(p.mirror_base, UBO_ENHANCE)
    return "\n".join(
        [
            "# Adblock Rule Collection — 浏览器扩展接入指引",
            "",
            "适用于 uBlock Origin、AdGuard（浏览器扩展）、Adblock Plus。",
            "把下面的订阅地址加入扩展的「自定义过滤列表 / 订阅」即可，扩展会每日自动更新。",
            "",
            "## 订阅地址",
            "",
            "完整版（网络拦截 + 元素隐藏）：",
            "",
            f"- 规范：{full}",
            f"- 镜像：{fullm}",
            "",
            "增强层（uBO 专有高级修饰符与脚本/元素规则，可选）：",
            "",
            f"- 规范：{enhance}",
            f"- 镜像：{enhm}",
            "",
            "## 导入步骤",
            "",
            "```text",
            "uBlock Origin   -> 设置 -> 过滤列表 -> 导入 -> 粘贴上面的地址 -> 应用更改",
            "AdGuard(浏览器) -> 设置 -> 过滤器 -> 自定义 -> 添加自定义过滤器 -> 粘贴地址",
            "Adblock Plus    -> 选项 -> 高级 -> 添加过滤列表 -> 粘贴地址",
            "```",
            "",
            "> 同一设备只需导入一个浏览器版本；DNS/路由器侧已启用时无需重复导入完整版。",
            "",
        ]
    )


def write_adapters(
    output_dir: Path,
    publish: PublishConfig,
    manifest: list,
    *,
    rulesets_dir: Path | None = None,
) -> dict[str, int]:
    """生成 ``dist/adapters/`` 下全部适配产物并登记 manifest，返回文件名到字节数。

    连接层适配仅在对应 ``rulesets/`` 规范文件存在时写入；跳过不影响其余适配，
    也不影响构建成功（如 ``--no-rulesets`` 场景）。
    """
    adapters_dir = output_dir / ADAPTER_DIRNAME
    adapters_dir.mkdir(parents=True, exist_ok=True)

    specs: list[tuple[str, str, str]] = [
        ("mihomo", "mihomo.yaml", _adapter_mihomo(publish)),
        ("singbox", "singbox.json", _adapter_singbox(publish)),
        ("surge", "surge.conf", _adapter_surge(publish)),
        ("quanx", "quanx.conf", _adapter_quanx(publish, rulesets_dir)),
        ("adguardhome", "adguardhome.yaml", _adapter_adguardhome(publish)),
        ("pihole", "pihole.txt", _adapter_pihole(publish)),
        ("dnsmasq", "dnsmasq.conf", _adapter_dnsmasq(publish)),
        ("hosts", "hosts.md", _adapter_hosts_guide(publish)),
        ("browsers", "browsers.md", _adapter_browsers_guide(publish)),
    ]

    connection_layer = {
        "mihomo": RULESET_CLASH,
        "singbox": RULESET_SINGBOX,
        "surge": RULESET_SURGE_DOMAIN_SET,
        "quanx": RULESET_QUANX,
    }

    written: dict[str, int] = {}
    for target, fname, text in specs:
        rel = connection_layer.get(target)
        if rel is not None and not _presence(rulesets_dir, rel):
            LOG.warning("适配产物跳过 %s：缺少 %s", fname, rel)
            continue
        path = adapters_dir / fname
        path.write_text(text, encoding="utf-8")
        written[fname] = path.stat().st_size
        manifest.append(
            {
                "name": f"adapter_{target}",
                "file": f"{ADAPTER_DIRNAME}/{fname}",
                "format": "adapter",
                "target": target,
            }
        )
    LOG.info("客户端适配产物: %d 个 -> %s/", len(written), ADAPTER_DIRNAME)
    return written
