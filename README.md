# CS2 Career

Windows 上的 CS2 生涯模拟器。用 Python 3 即可运行，无需额外依赖。

不安装任何游戏插件也能完整游玩生涯：创建档案、推进赛季、按实力结算比赛。若要在 CS2 中亲自上场，必须另行安装人机增强，见下文。玩法与系统说明见 [游玩说明.txt](游玩说明.txt)。

## 运行

```
py -3 main.py
```

或双击已打包的 `CS2Career.exe`。浏览器会打开本地界面。存档在程序目录的 `save/`，请勿提交到 Git 或公开分享。

## 添加人机增强

不安装人机增强，无法进入 CS2。仅使用「按实力出战」时可以跳过。

人机增强不是本项目，请从其发行页下载**打包好的发行包**（不要只下源码）：

https://github.com/ed0ard/CS2-Bot-Improver

解压后的根目录一般叫 `CS2B` 或 `CS2-Bot-Improver`，里面应能直接看到 `addons` 和 `overrides`。路径要填这一层，不要填到 `addons` 里面。

然后打开本程序的 **训练赛** 页，填好并保存：

- **steam.exe**：Steam 根目录下的 `steam.exe`
- **csgo 目录**：必须指到 `...\Counter-Strike Global Offensive\game\csgo`
- **人机增强目录**：上一步解压出的那个文件夹

点击「把人机增强装进游戏」。完成后必须完全退出 CS2，再从生涯进入对局。进比赛插件 CareerMatch 会在此时一并写入；本版本不安装换肤。

每次从生涯进入 CS2 时，会按当前难度拷贝人机增强的 botprofile，并把生涯里尚缺档案的选手名追加到 `game\csgo\overrides\botprofile.vpk`。不会改人机增强目录里原来的 Low / Medium / High 三份文件。若游戏已经开着，补完名字后需要完全退出再开。

更完整的步骤与常见问题见 [添加人机增强.txt](添加人机增强.txt)。
