# CS2 Career

Windows 上的 CS2 生涯模拟器。用 Python 3 即可运行，不需要再装 Python 包。

## 怎么运行

需要 [Python 3](https://www.python.org/downloads/)。安装时勾选 **Add python.exe to PATH**。

在本目录打开终端：

```
py -3 main.py
```

浏览器会打开本地界面（一般是 `http://127.0.0.1:8768/`）。也可以双击打包好的 `CS2Career.exe`。

存档在程序旁边的 `save/`。不要把这个文件夹提交到 Git，也不要公开分享。

玩法见 [游玩说明.txt](游玩说明.txt)。不装任何游戏插件，也能完整玩生涯：建档、推进赛季、按实力结算比赛。

## 可以搭配什么一起用

生涯是外挂在 CS2 外面的模拟器。下面这些是可选配件，装了才能「自己进游戏打」。

### CS2 Bot Improver（人机增强）

- 项目：https://github.com/ed0ard/CS2-Bot-Improver
- 请下载**打包好的发行包**，不要只下源码。解压后应能直接看到 `addons` 和 `overrides`。
- 效果：离线局里的人机更像职业选手；生涯会按难度拷贝它的 botprofile，并把名单写进游戏。
- 不装：不能进 CS2 自己打，仍可用「按实力出战」打完整场生涯。

在 **训练赛** 页填好并保存：

- **steam.exe**：Steam 根目录下的 `steam.exe`
- **csgo 目录**：必须指到 `...\Counter-Strike Global Offensive\game\csgo`
- **人机增强目录**：解压出来的那一层，不要填进 `addons`

点「把人机增强装进游戏」，然后**完全退出 CS2**，再从生涯进对局。步骤和常见问题见 [添加人机增强.txt](添加人机增强.txt)。

进比赛时，本程序会一并写入自己的 **CareerMatch** 插件（已放在 `vendor/`）：自动加 bot、打完回传战绩。

### 换肤（可选）

本仓库自带一份改过的 [Inventory Simulator](https://github.com/ianlucas/cs2-inventory-simulator)，以及辅助插件 InvsimCareer。训练赛页的换肤路径留空即可，不必另下。

- 不装：生涯里照样买皮、开箱、装备，CS2 里还是原皮。
- 装上：经营页打开「游戏内换肤」并填 17 位 SteamID 后，本地局里你的枪、刀、手套会换成库存里的饰品。人机仍用人机增强自带的随机涂装。

先装好人机增强，再点「把换肤插件装进游戏」，完全退出 CS2 后再进。
