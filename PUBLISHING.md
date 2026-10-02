# 构建与 GitHub 发布

## 1.7.0-preview.1 · 3D 版

本版发布普通 Windows 包与对应源码，GitHub 标记为 pre-release。
主分支保存当前源码；既有 1.6.0-hotfix.1 标签和正式 Release 不修改。

3D 后台入口是 `tools/career3d_backend_main.py`，Godot 项目在
`work/career3d_redesign`。源码运行见 `SOURCE_BUILD.md`。
本地候选构建见 `tools/package_career3d.py`；公开归档使用
`tools/package_career3d_public.py` 从已核对的源码/普通运行 ZIP 重封装。
公开树、有限文档覆盖和最终哈希由该工具生成，不直接上传工作目录。

发布普通 Windows ZIP、源码 ZIP、`BUILD_MANIFEST.json` 和 `SHA256SUMS.txt`。
普通包的 `source/` 必须附带同一份公开源码 ZIP，必要的许可证和素材出处保留。
整合候选的外部 SDK 附件不在本次公开分发中；依赖获取信息见
`docs/external-runtime-pins.json`，更详细的构建记录见
`docs/3d-preview-packaging.zh-CN.txt`。

Git 推送使用已有仓库的历史，不强推、不改旧标签，也不上传用户存档、
账号、私人扩展、原始 Demo、日志和缓存。GitHub Release 的所有附件上传
并核对完毕后才从 draft 发布，以免玩家下载到缺少源码或文件的版本。

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
