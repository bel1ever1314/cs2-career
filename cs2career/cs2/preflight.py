"""Read-only checks before a career launch changes the CS2 environment."""
from pathlib import Path


def require_installation_files(csgo: Path) -> None:
    """Detect an interrupted Steam update, without interpreting its manifest.

    Steam can leave a valid gameinfo.gi and mod tree while replacing the game
    binaries. Check the installed files themselves before arming any mounts.
    """
    required = (
        (csgo / "steam.inf", "game/csgo/steam.inf"),
        (csgo / "bin/win64/server.dll", "game/csgo/bin/win64/server.dll"),
        (csgo.parent / "bin/win64/cs2.exe", "game/bin/win64/cs2.exe"),
    )
    missing = [label for path, label in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(
            "CS2 安装文件不完整，暂未准备或启动比赛。缺少：" + "、".join(missing)
            + "。请先在 Steam 完成 CS2 更新／下载；如果更新已完成，"
            "请在 CS2 属性 → 已安装文件 → 验证游戏文件的完整性，然后重试。"
            "若游戏装在其他位置，请检查设置中的 CS2 目录。"
        )
