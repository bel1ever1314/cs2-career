from pathlib import Path
import unittest

from cs2career.cs2.launch import mod_runtime_file


class ModPersonalConfigTests(unittest.TestCase):
    def test_downloaded_package_cannot_supply_someone_elses_personal_settings(self):
        for path in ('cfg/autoexec.cfg', 'cfg/CONFIG.cfg', 'cfg/cs2_user_convars_0_slot0.vcfg',
                     'cfg/cs2_user_keys_0_slot0.vcfg', 'cfg/cs2_machine_convars.vcfg',
                     'cfg/pwa_userconfig123.cfg', 'cfg/cs2_video.txt', 'cfg/video.txt',
                     'userdata/123/730/local/cfg/config.cfg'):
            with self.subTest(path=path):
                self.assertFalse(mod_runtime_file(Path(path)))

    def test_server_buy_and_behavior_configs_remain_installable(self):
        for path in ('cfg/bot_buy.cfg', 'cfg/gamemode_competitive.cfg',
                     'cfg/my_bot_normal_config.cfg', 'addons/BotHider/config.json',
                     'addons/counterstrikesharp/dotnet/dotnet.exe'):
            with self.subTest(path=path):
                self.assertTrue(mod_runtime_file(Path(path)))
