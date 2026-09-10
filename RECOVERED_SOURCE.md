# 旧换肤插件的源码恢复记录

2026-09-10 发布整理时发现，本项目原有 InventorySimulator 与 InvsimCareer 只有 DLL。
为使接手者能够阅读、修改和构建，使用 ILSpy 11.0.0.9375 从原有程序集恢复源码：

- `vendor/InvsimCareer/source/`：生涯配置桥接。仅反射设置本地 InventorySimulator 配置。
- `vendor/InventorySimulator/source/`：本地修改版 InventorySimulator，原作者 Ian Lucas（MIT）。
  原项目：https://github.com/ianlucas/cs2-css-inventory-simulator

这不是作者原始工程，也不是从最新上游下载后冒充相同版本。
机械整理包括：用固定版本 NuGet PackageReference 替代本机 HintPath；
把反编译的临时 InlineArray 还原为等效数组；去掉已经生成实现上的重复 GeneratedRegex 属性。
没有为此更新游戏中的换肤 DLL 或 gamedata。

两个恢复工程均通过 .NET 10 目标的编译检查。InventorySimulator 仍有反编译产生的
可空注释和原生结构未赋值警告。它们尚未通过“重编译 DLL 与旧 DLL 实战等价”验收。
发布包仍保留原有换肤 DLL；各原 DLL 的 SHA-256 见发布源码清单。
可以重新编译作进一步验证，但不承诺字节级相同。不要自动替换玩家正在使用的版本。

构建：`dotnet build vendor/InvsimCareer/source/InvsimCareer.csproj -c Release`，
以及 `dotnet build vendor/InventorySimulator/source/InventorySimulator.csproj -c Release`。
第三方授权继续保留，详见 THIRD_PARTY_NOTICES.md。
