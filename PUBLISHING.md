# 构建与 GitHub 发布

使用 Windows、Python 3.12+、.NET 10 SDK（CS2插件）、Node（前端测试）。
桌面依赖安装：`py -3 -m pip install -r requirements-desktop.txt pyinstaller==6.22.2`。
不需要、也不应该把 Steam 或 CS2 安装目录放进仓库。

1. 从源码根目录执行 `powershell -ExecutionPolicy Bypass -File tools/build_plugins.ps1`。
   只构建 CareerMatch 和修改后的 BotBuy；历史换肤 DLL 与可重编译恢复源码均保留。
2. 执行 `py -3 tools/run_tests.py`。它在隔离目录运行，禁止真实游戏写入。
   前端测试为 tools/test_*.cjs；纯插件测试为 tools/identity-tests。
3. `py -3 build_desktop_preview.py --integration --name CS2Career-150-rc-20260910-4`。
   这是独立窗口程序，默认不会打开浏览器。构建不会扫描或复制玩家 save。
4. `py -3 tools/package_public.py --exe release/CS2Career-150-rc-20260910-4/CS2Career-150-rc-20260910-4.exe`。
   默认输出到 publish/1.5.0-rc.20260910.4；输出已存在会停止，避免覆盖。
   生成源码ZIP、WindowsZIP、逐文件清单和 SHA256SUMS.txt。
5. 解压源码 ZIP 到干净目录上传到 GitHub 仓库；不要上传你当前工作目录的整个压缩包。
   把 Windows ZIP 和对应源码 ZIP 一起附加到同一个 Release，勾选 **pre-release**。
   发布说明使用 RELEASE_NOTES.md，保留已知限制，不把自动测试当作实战完成。

根许可证为 AGPL-3.0-only。第三方仍保留自己的版权与许可；详见 THIRD_PARTY_NOTICES.md。
这个流程只准备本地文件，不会替你创建仓库、推送代码或公开你的数据。

源码包用白名单：程序、内置资源、四个插件及源码、扩展模板、测试与文档。
排除 save、私人扩展、缓存、日志、.git/.codex/.agents、.desktop-deps、bin/obj/PDB、临时工具。
Windows包只含指定EXE、说明、许可和扩展模板；启动后才在用户本机建立 save。
