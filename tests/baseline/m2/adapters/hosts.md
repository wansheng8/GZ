# Adblock Rule Collection — 系统 hosts 接入指引

把下面的 hosts 内容追加到系统 hosts 文件末尾。文件为 `0.0.0.0 domain` 形式，
命中域名被解析到黑洞地址，从而在系统层面拦截。

## 下载地址

- IPv4 规范：https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
- IPv4 镜像：https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns.txt
- IPv6 规范：https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns_ipv6.txt
- IPv6 镜像：https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_dns_ipv6.txt

## 各系统 hosts 路径

- Windows：`C:\Windows\System32\drivers\etc\hosts`（需管理员权限编辑）
- macOS / Linux：`/etc/hosts`（`sudo` 编辑）
- Android：需 root，路径 `/system/etc/hosts`（或用支持本地 hosts 的 AdAway 等）

## 写入命令（Linux / macOS）

```bash
curl -o /tmp/adblock_hosts.txt https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full_dns.txt
cat /tmp/adblock_hosts.txt | sudo tee -a /etc/hosts >/dev/null
```

写入后刷新 DNS 缓存（macOS：`sudo dscacheutil -flushcache`；
Windows：`ipconfig /flushdns`）。移除时删除追加段落即可。
