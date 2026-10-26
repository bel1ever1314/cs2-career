# 构建与 GitHub 发布

## 1.7.2 · 3D 版

2026-10-25 发布更新：使用已离线核对的 1.4.7 整合运行目录，附带五个生涯补丁、对应应用源码、组件源码与许可。组件来源以 `docs/runtime-sources-147.json` 和 `cs2career/data/cs2_runtime_compat.json` 为准，BotHider 0.6.0 与 BotVision 0.4.0 的二进制另与官方发行包核对一致。旧的组件打包脚本中的历史 SOURCE_PINS 不代表这次发布来源。

主分支正常快进，新增不可变构建标签 `v1.7.2-improver147-20261025`；不移动已有标签。继续更新 v1.7.2 Release 的默认 Windows、源码、组件源码、清单和校验附件。新附件先用临时名上传，服务端 SHA-256 全部一致后再替换默认名；旧附件改名为 `.previous-20261025-improver147` 保留。此次未做实际 CS2 进图和帧率验证，发布说明必须保留这一范围。

以下为此前发布记录：

本版发布完整增强 Windows 包、应用源码与组件源码，按作者要求设置为 GitHub Latest。
本次刷新同一个 1.7.2：适配 CS2 2000933 的战术导航与观察方向，加入 BotAimImprover 的 schema 兼容补丁。
保留 Bot Improver 1.4.6、10 月 12 日首次安装和重复准备修复，以及此前市场、转会、训练和存档更新。
2026-10-16 改为随包离线自动准备；程序文件沿用用户确认可用的测试包，RayTrace 独立插件的已知限制写入发布说明。
不创建带后缀的新版本。
GitHub 的 Latest 使用非 draft、非 prerelease 发布。
主分支保存当前源码；既有 1.6.0-hotfix.1 标签和正式 Release 不修改。

3D 后台入口是 `tools/career3d_backend_main.py`，Godot 项目在
`work/career3d_redesign`。源码运行见 `SOURCE_BUILD.md`。
使用 `tools/package_career3d.py --ordinary-only --version 1.7.2`
重新冻结当前源码并生成普通运行包；不复用旧版后台 EXE。
朋友测试整合包通过 `tools/package_career3d_friends.py` 从这个干净运行包派生，
单独附加已核对的人机增强、许可与对应来源资料，不复制个人存档或游戏目录。

发布整合 Windows ZIP、源码 ZIP、组件源码 ZIP、`BUILD_MANIFEST.json` 和 `SHA256SUMS.txt`。
运行包的 `source/` 必须附带同一份公开应用源码 ZIP，必要的许可证和素材出处保留。
整合包来自已验证的本地测试包，剔除整个 `game/runtime`；保持程序二进制不变，补齐组件对应源码和许可。
外部 SDK 镜像不混入公开源码；依赖获取信息见
`docs/external-runtime-pins.json`，更详细的构建记录见
`docs/3d-preview-packaging.zh-CN.txt`。

Git 推送使用已有仓库的历史，主分支不强推。此次按作者要求替换 1.7.2，
保留 v1.7.2 及已有构建标签，新增 v1.7.2-cs2-2000933-autoready 指向本次提交；不强推已有标签。
不上传用户存档、
账号、私人扩展、原始 Demo、日志和缓存。GitHub Release 的所有附件上传
并核对 SHA-256 后才替换默认下载名；旧附件改名保留作回退。

## 1.6.0 · 桌面版构建记录

使用 Windows、Python 3.12+、.NET 10 SDK（CS2插件）、Node（前端测试）。
桌面依赖安装：`py -3 -m pip install -r requirements-desktop.txt pyinstaller==6.22.2`。
不需要、也不应该把 Steam 或 CS2 安装目录放进仓库。

1. 如需修改 CS2 插件，单独执行 `powershell -ExecutionPolicy Bypass -File tools/build_plugins.ps1`。
   只构建 CareerMatch 和修改后的 BotBuy；普通界面／剧情更新直接复用内置插件，不必重建。
2. 执行 `py -3 tools/run_tests.py`。它在隔离目录运行，禁止真实游戏写入。
   前端测试为 tools/test_*.cjs；纯插件测试为 tools/identity-tests。
3. `py -3 build_exe.py`。
   这是独立窗口程序，默认不会打开浏览器。构建不会扫描或复制玩家 save。
   默认程序位于 `D:/CS2CareerBuilds/v1.6.0/release/CS2Career-160/CS2Career-160.exe`。
   大型构建产物和缓存放 D 盘，可用 `--output-root` 更改。没有 py 命令时使用 Python 3.12 的完整路径。
4. 上一步同时在 `D:/CS2CareerBuilds/v1.6.0/public/时间戳/` 生成源码 ZIP、Windows ZIP、清单和 SHA256SUMS.txt。
   输出已存在会停止；用 `--public-output` 指定另一个空目录。修改文档后单独重新封装可执行：
   `py -3 tools/package_public.py --exe D:/CS2CareerBuilds/v1.6.0/release/CS2Career-160/CS2Career-160.exe --output D:/CS2CareerBuilds/v1.6.0/public/repacked`。
   本版不打包尚未完成的 Bot Lab 数据与实验；核心英文已接入，旧剧情仍可能保留中文。
5. 解压源码 ZIP 到干净目录上传到 GitHub 仓库；不要上传你当前工作目录的整个压缩包。
   把 Windows ZIP 和对应源码 ZIP 一起附加到同一个 Release，勾选 **pre-release**。
   发布说明使用 RELEASE_NOTES.md，保留已知限制，不把自动测试当作实战完成。

根许可证为 AGPL-3.0-only。第三方仍保留自己的版权与许可；详见 THIRD_PARTY_NOTICES.md。
这个流程只准备本地文件，不会替你创建仓库、推送代码或公开你的数据。

源码包用白名单：程序、内置资源、四个插件及源码、扩展模板、测试与文档。
排除 save、私人扩展、缓存、日志、.git/.codex/.agents、.desktop-deps、bin/obj/PDB、临时工具。
Windows包只含指定EXE、说明、许可和扩展模板；启动后才在用户本机建立 save。
解压后用 `Launch-CS2Career.cmd` 启动，临时解压目录放在程序旁，不硬编码开发者路径。
