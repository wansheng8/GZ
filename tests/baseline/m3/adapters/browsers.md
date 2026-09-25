# Adblock Rule Collection — 浏览器扩展接入指引

适用于 uBlock Origin、AdGuard（浏览器扩展）、Adblock Plus。
把下面的订阅地址加入扩展的「自定义过滤列表 / 订阅」即可，扩展会每日自动更新。

## 订阅地址

完整版（网络拦截 + 元素隐藏）：

- 规范：https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_full.txt
- 镜像：https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_full_jsdelivr.txt

增强层（uBO 专有高级修饰符与脚本/元素规则，可选）：

- 规范：https://raw.githubusercontent.com/wansheng8/GZ/main/dist/adblock_collection_ubo_enhance.txt
- 镜像：https://cdn.jsdelivr.net/gh/wansheng8/GZ@main/dist/adblock_collection_ubo_enhance.txt

## 导入步骤

```text
uBlock Origin   -> 设置 -> 过滤列表 -> 导入 -> 粘贴上面的地址 -> 应用更改
AdGuard(浏览器) -> 设置 -> 过滤器 -> 自定义 -> 添加自定义过滤器 -> 粘贴地址
Adblock Plus    -> 选项 -> 高级 -> 添加过滤列表 -> 粘贴地址
```

> 同一设备只需导入一个浏览器版本；DNS/路由器侧已启用时无需重复导入完整版。
