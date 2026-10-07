from application_double import ApplicationDouble
"""Data/API/deployment fixtures only: no real saves, CS2, or network services."""
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from cs2career import tactics
from cs2career.cs2 import launch
from cs2career.web.server import create_server


QA_ROOT = Path("D:/CS2CareerBuilds/v1.6.0/tactics-multimap-20261001/qa")
RESOURCE_FILE = tactics.data_file


def isolated_temp():
    QA_ROOT.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(prefix="tactics-", dir=QA_ROOT)


def example_source(path):
    return patch.object(tactics, "data_file", side_effect=lambda name: path if name == "tactical_playbook.json" else RESOURCE_FILE(name))


def tactic(ident="test_a", name="沙二夹 A", side="t"):
    return {"id": ident, "name": name, "side": side, "slots": [
        {"slot": index, "steps": [{"position": [-1000, 2000], "level": "auto", "wait": 2,
                                   "look_at": [-900, 2000]}] if index == 1 else []}
        for index in range(1, 6)]}


def pack(*rows):
    return {"schema_version": 1, "map": "de_dust2", "tactics": list(rows)}


def map_tactic(map_code, ident="shared", name="地图路线"):
    value = tactic(ident, name)
    step = value["slots"][0]["steps"][0]
    step["position"] = tactics.pixel_to_world([320, 320], map_code)
    step["look_at"] = tactics.pixel_to_world([360, 320], map_code)
    return value


def movement_tactic(map_code="de_dust2", ident="movement"):
    value = map_tactic(map_code, ident)
    first = value["slots"][0]["steps"][0]
    first["wait"] = 0
    value["slots"][0]["steps"] = [first, {**first, "movement": "walk"},
                                   {**first, "movement": "run", "wait": 15}]
    return value


class TacticalDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = isolated_temp()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.environment = patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root / "save")})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        examples = example_source(self.root / "examples.json")
        examples.start()
        self.addCleanup(examples.stop)

    def test_missing_library_is_read_only_and_independent(self):
        career = self.root / "save" / "career.json"
        career.parent.mkdir()
        career.write_bytes(b"career-sentinel")
        self.assertEqual([], tactics.public_library()["tactics"])
        self.assertFalse(tactics.library_path().exists())
        tactics.save_tactic(tactic())
        self.assertEqual(b"career-sentinel", career.read_bytes())
        self.assertEqual({"schema_version", "map", "tactics"}, set(json.loads(tactics.library_path().read_bytes())))

    def test_standard_projection_round_trips_edges_and_fractional_points(self):
        for pixel in ([0, 0], [1024, 1024], [512, 512], [183.125, 827.5]):
            world = tactics.pixel_to_world(pixel)
            result = tactics.world_to_pixel(world)
            for actual, expected in zip(result, pixel):
                self.assertAlmostEqual(expected, actual, places=10)
        self.assertEqual([-2476.0, 3239.0], tactics.pixel_to_world([0, 0]))
        self.assertAlmostEqual(2029.6, tactics.pixel_to_world([1024, 0])[0])
        self.assertAlmostEqual(-1266.6, tactics.pixel_to_world([0, 1024])[1])
        for value in ([1025, 0], [0, -1], [float("inf"), 1], [True, 0]):
            with self.assertRaises(ValueError):
                tactics.pixel_to_world(value)

    def test_bundled_examples_are_read_only_until_first_local_edit(self):
        examples = self.root / "examples.json"
        examples.write_text(json.dumps(pack(tactic("example"))), encoding="utf-8")
        before = examples.read_bytes()
        self.assertEqual("example", tactics.public_library()["tactics"][0]["id"])
        self.assertFalse(tactics.library_path().exists())
        tactics.save_tactic(tactic("custom"))
        self.assertEqual(["example", "custom"], [t["id"] for t in tactics.load_library()["tactics"]])
        self.assertEqual(before, examples.read_bytes())
        tactics.delete_tactic("example")
        tactics.delete_tactic("custom")
        self.assertEqual([], tactics.load_library()["tactics"])
        self.assertEqual(before, examples.read_bytes())

    def test_validation_canonicalizes_only_slot_order_and_name(self):
        value = tactic(name="  战术  ")
        value["slots"].reverse()
        clean = tactics.validate_tactic(value)
        self.assertEqual("战术", clean["name"])
        self.assertEqual([1, 2, 3, 4, 5], [s["slot"] for s in clean["slots"]])
        self.assertEqual([-1000.0, 2000.0], clean["slots"][0]["steps"][0]["position"])
        self.assertEqual([-900.0, 2000.0], clean["slots"][0]["steps"][0]["look_at"])
        self.assertEqual(5, value["slots"][0]["slot"])

    def test_assignment_fields_are_optional_and_legacy_shape_is_preserved(self):
        legacy = tactic()
        self.assertEqual(set(legacy), set(tactics.validate_tactic(legacy)))
        self.assertTrue(all(set(slot) == {"slot", "steps"} for slot in tactics.validate_tactic(legacy)["slots"]))
        value = tactic()
        value.update(assignment="ability", human_slot=4)
        for slot, duty in zip(value["slots"], ("awp", "awp", "entry", "auto", "igl")):
            slot["duty"] = duty
        clean = tactics.validate_tactic(value)
        self.assertEqual("ability", clean["assignment"])
        self.assertEqual(4, clean["human_slot"])
        self.assertEqual(["awp", "awp", "entry", "auto", "igl"], [slot["duty"] for slot in clean["slots"]])
        for assignment in ("roster", "ability"):
            explicit_defaults = {**tactic(), "assignment": assignment, "human_slot": 1}
            explicit_defaults["slots"][0]["duty"] = "auto"
            tactics.save_tactic(explicit_defaults)
            stored = tactics.load_library()["tactics"][0]
            self.assertEqual(assignment, stored["assignment"])
            self.assertEqual(1, stored["human_slot"])
            self.assertEqual("auto", stored["slots"][0]["duty"])
        result = tactics.import_tactics({**value, "id": "direct_ability"})
        self.assertEqual("ability", result["tactics"][-1]["assignment"])
        self.assertEqual(4, result["tactics"][-1]["human_slot"])

    def test_route_ending_round_trips_without_rewriting_old_routes(self):
        legacy = tactic(side="ct")
        self.assertNotIn("finish", tactics.validate_tactic(legacy)["slots"][0])
        for finish in ("auto", "hold", "native"):
            value = tactic(ident="finish_" + finish, side="ct")
            value["slots"][0]["finish"] = finish
            tactics.save_tactic(value)
            stored = next(t for t in tactics.load_library()["tactics"] if t["id"] == value["id"])
            self.assertEqual(finish, stored["slots"][0]["finish"])
            imported = tactics.validate_tactic(json.loads(json.dumps(stored)))
            self.assertEqual(stored, imported)
        for invalid in (None, "", "rush", True, 1, [], {}):
            value = tactic()
            value["slots"][0]["finish"] = invalid
            with self.subTest(finish=invalid), self.assertRaises(ValueError):
                tactics.validate_tactic(value)

    def test_rejects_invalid_assignment_human_slot_and_duty(self):
        for invalid in (None, "captain", "ABILITY", True, 1, {}, []):
            with self.subTest(assignment=invalid), self.assertRaises(ValueError):
                tactics.validate_tactic({**tactic(), "assignment": invalid})
        for invalid in (None, True, 0, 6, 1.0, "1"):
            with self.subTest(human_slot=invalid), self.assertRaises(ValueError):
                tactics.validate_tactic({**tactic(), "assignment": "ability", "human_slot": invalid})
        for value in ({**tactic(), "human_slot": 2}, {**tactic(), "assignment": "roster", "human_slot": 5}):
            with self.assertRaisesRegex(ValueError, "名单分配"):
                tactics.validate_tactic(value)
        for invalid in (None, "support", "sniper", True, 1, {}, []):
            value = tactic()
            value["slots"][0]["duty"] = invalid
            with self.subTest(duty=invalid), self.assertRaises(ValueError):
                tactics.validate_tactic(value)

    def test_movement_is_optional_run_by_default_and_preserves_legacy_shape(self):
        legacy = tactic()
        clean = tactics.validate_tactic(legacy)
        self.assertEqual(legacy, clean)
        step = clean["slots"][0]["steps"][0]
        self.assertEqual("run", step.get("movement", "run"))
        self.assertNotIn("movement", step)
        for map_code in tactics.SUPPORTED_MAPS:
            with self.subTest(map=map_code):
                value = movement_tactic(map_code)
                before = json.dumps(value)
                clean = tactics.validate_tactic(value, map_code)
                steps = clean["slots"][0]["steps"]
                self.assertNotIn("movement", steps[0])
                self.assertEqual(["run", "walk", "run"], [step.get("movement", "run") for step in steps])
                self.assertEqual([0, 0, 15], [step["wait"] for step in steps])
                self.assertEqual(before, json.dumps(value))

    def test_rejects_invalid_movement_values_without_replacing_library(self):
        tactics.save_tactic(movement_tactic())
        before = tactics.library_path().read_bytes()
        for invalid in (None, "", "RUN", "Walk", "sprint", True, False, 0, 1, 1.0, {}, []):
            value = movement_tactic(ident="invalid")
            value["slots"][0]["steps"][1]["movement"] = invalid
            with self.subTest(movement=invalid):
                for operation in (tactics.validate_tactic, tactics.save_tactic):
                    with self.assertRaisesRegex(ValueError, "移动方式"):
                        operation(value)
                with self.assertRaisesRegex(ValueError, "移动方式"):
                    tactics.import_tactics(pack(tactic("must_not_import"), value))
                self.assertEqual(before, tactics.library_path().read_bytes())

    def test_movement_survives_save_export_and_all_import_shapes(self):
        map_code = "de_nuke"
        value = movement_tactic(map_code)
        value.update(assignment="ability", human_slot=4)
        value["slots"][1]["duty"] = "awp"
        expected = tactics.validate_tactic(value, map_code)
        self.assertEqual(expected, tactics.save_tactic(value, map_code)["tactic"])
        package = tactics.load_library(map_code)
        exported = tactics.encode_library(package)
        decoded = tactics.decode_json(exported)
        self.assertEqual(package, tactics.validate_library(decoded, map_code))
        self.assertEqual(1, decoded["schema_version"])
        for index, payload in enumerate((value, {"tactic": value}, {"map": map_code, "tactic": value}, decoded)):
            with self.subTest(import_shape=index), patch.dict(os.environ, {
                "CS2CAREER_SAVE_DIR": str(self.root / f"import_{index}")
            }):
                result = tactics.import_tactics(payload, map_code)
                self.assertEqual([expected], result["tactics"])
                self.assertEqual([expected], tactics.load_library(map_code)["tactics"])
                self.assertEqual([expected], tactics.public_library(map_code)["tactics"])
        self.assertEqual(exported, tactics.library_path(map_code).read_bytes())

    def test_rejects_invalid_identifiers_names_side_slots_and_extra_commands(self):
        patches = [
            {"id": "../outside"}, {"id": "Upper"}, {"id": "a" * 33}, {"id": ""},
            {"id": "中文"}, {"name": ""}, {"name": "a" * 41}, {"name": "x\n"},
            {"name": "x\u202e"}, {"side": "both"}, {"script": "do.cfg"},
            {"slots": []}, {"slots": [{"slot": 1, "steps": []}] * 5},
        ]
        for patch_data in patches:
            with self.subTest(patch=patch_data), self.assertRaises(ValueError):
                tactics.validate_tactic({**tactic(), **patch_data})
        for index in (True, 0, 6, 1.0):
            value = tactic()
            value["slots"][0]["slot"] = index
            with self.assertRaises(ValueError):
                tactics.validate_tactic(value)

    def test_rejects_nonfinite_boolean_outside_map_and_invalid_steps(self):
        patches = [
            {"position": [float("nan"), 0]}, {"position": [0, float("inf")]},
            {"position": [True, 0]}, {"position": [10 ** 1000, 0]}, {"position": [-2477, 0]},
            {"position": [0, 3240]}, {"position": [0, -1267]}, {"position": [0, 0, 0]},
            {"level": "basement"}, {"wait": -1}, {"wait": 31}, {"wait": True},
            {"wait": "2"}, {"look_at": [99999, 0]}, {"look_at": "exec.cfg"}, {"exec": "cfg"},
        ]
        for patch_data in patches:
            value = tactic()
            value["slots"][0]["steps"][0].update(patch_data)
            with self.subTest(patch=patch_data), self.assertRaises(ValueError):
                tactics.validate_tactic(value)
        value = tactic()
        value["slots"][0]["steps"] *= 13
        with self.assertRaises(ValueError):
            tactics.validate_tactic(value)
        for wait in (0, 30, 2.5):
            value = tactic()
            value["slots"][0]["steps"][0]["wait"] = wait
            self.assertEqual(wait, tactics.validate_tactic(value)["slots"][0]["steps"][0]["wait"])

    def test_save_overwrite_delete_and_directory_isolation(self):
        tactics.save_tactic(tactic())
        result = tactics.save_tactic(tactic(name="新版"))
        self.assertEqual(["test_a"], result["overwritten_ids"])
        self.assertIn("覆盖", result["msg"])
        with patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root / "other")}):
            self.assertEqual([], tactics.load_library()["tactics"])
            tactics.save_tactic(tactic("other"))
        self.assertEqual(["test_a"], [r["id"] for r in tactics.load_library()["tactics"]])
        self.assertEqual([], tactics.delete_tactic("test_a")["tactics"])
        with self.assertRaises(ValueError):
            tactics.delete_tactic("missing")

    def test_import_is_transactional_and_reports_overwrites_without_dropping_rows(self):
        tactics.save_tactic(tactic())
        before = tactics.library_path().read_bytes()
        invalid = tactic("bad")
        invalid["slots"][0]["steps"][0]["wait"] = 31
        for value in (pack(tactic("new"), invalid), pack(tactic("dup"), tactic("dup")),
                      {**pack(), "map": "de_unknown"}, {**pack(), "schema_version": True},
                      pack(*(tactic(f"many_{i}") for i in range(21)))):
            with self.assertRaises(ValueError):
                tactics.import_tactics(value)
            self.assertEqual(before, tactics.library_path().read_bytes())
        result = tactics.import_tactics(pack(tactic(name="覆盖"), tactic("new")))
        self.assertEqual(2, result["imported_count"])
        self.assertEqual(["test_a"], result["overwritten_ids"])
        self.assertEqual(["test_a", "new"], [r["id"] for r in result["tactics"]])
        tactics.import_tactics({"tactic": tactic("wrapped")})
        tactics.import_tactics(tactic("direct"))
        self.assertEqual(4, len(tactics.load_library()["tactics"]))

    def test_combined_import_capacity_rejects_whole_transaction(self):
        tactics.import_tactics(pack(*(tactic(f"many_{i}") for i in range(20))))
        before = tactics.library_path().read_bytes()
        with self.assertRaises(ValueError):
            tactics.import_tactics(pack(tactic("new"), tactic("many_0", name="must not replace")))
        self.assertEqual(before, tactics.library_path().read_bytes())

    def test_invalid_storage_is_not_silently_reset_and_atomic_failure_keeps_old_file(self):
        path = tactics.library_path()
        path.write_bytes(b"{invalid")
        with self.assertRaises(ValueError):
            tactics.load_library()
        self.assertEqual(b"{invalid", path.read_bytes())
        path.unlink()
        tactics.save_tactic(tactic())
        before = path.read_bytes()
        with patch('cs2career.storage.transaction._replace', side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                tactics.save_tactic(tactic("new"))
        self.assertEqual(before, path.read_bytes())
        self.assertFalse(list(path.parent.glob("*.tmp")))

    def test_json_rejects_size_duplicate_keys_constants_and_depth(self):
        for blob in (b" " * (tactics.MAX_BYTES + 1), b'{"id":"a","id":"b"}', b'{"wait":NaN}',
                     b"[" * 2000 + b"0" + b"]" * 2000, b"\xff"):
            with self.assertRaises(ValueError):
                tactics.decode_json(blob)
        tactics.library_path().write_bytes(b" " * (tactics.MAX_BYTES + 1))
        with self.assertRaises(ValueError):
            tactics.load_library()


class TacticalMultiMapTests(unittest.TestCase):
    def setUp(self):
        self.temp = isolated_temp()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        environment = patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root / "save")})
        environment.start()
        self.addCleanup(environment.stop)
        examples = example_source(self.root / "missing_examples.json")
        examples.start()
        self.addCleanup(examples.stop)

    def test_all_maps_use_bundled_projection_and_public_metadata(self):
        available = tactics.available_maps()
        self.assertEqual(list(tactics.SUPPORTED_MAPS), [row["map"] for row in available])
        for code in tactics.SUPPORTED_MAPS:
            with self.subTest(map=code):
                meta = tactics.map_metadata(code)
                self.assertEqual(f"/tactical_maps/{code}.png", meta["image"])
                self.assertTrue(meta["name"])
                self.assertTrue(meta["layers"])
                self.assertEqual(code, tactics.public_library(code)["map"])
                self.assertEqual(meta, tactics.public_library(code)["map_meta"])
                for pixel in ([0, 0], [meta["width"], meta["height"]], [315.25, 726.5]):
                    world = tactics.pixel_to_world(pixel, code)
                    actual = tactics.world_to_pixel(world, code)
                    for got, expected in zip(actual, pixel):
                        self.assertAlmostEqual(expected, got, places=10)
                with self.assertRaises(ValueError):
                    tactics.validate_position([meta["pos_x"] - 1, meta["pos_y"]], map_code=code)
                self.assertFalse(tactics.library_path(code).exists())

    def test_map_files_and_same_ids_are_independent(self):
        dust = tactics.save_tactic(map_tactic("de_dust2", name="沙二"))
        dust_bytes = tactics.library_path().read_bytes()
        mirage = tactics.save_tactic(map_tactic("de_mirage", name="荒漠"), "de_mirage")
        self.assertEqual("tactics.json", tactics.library_path().name)
        self.assertEqual("tactics_de_mirage.json", tactics.library_path("de_mirage").name)
        self.assertEqual("de_dust2", dust["map"])
        self.assertEqual("de_mirage", mirage["map"])
        self.assertEqual([], mirage["overwritten_ids"])
        self.assertEqual(dust_bytes, tactics.library_path().read_bytes())
        self.assertEqual("荒漠", tactics.load_library("de_mirage")["tactics"][0]["name"])
        tactics.delete_tactic("shared", "de_mirage")
        self.assertEqual([], tactics.load_library("de_mirage")["tactics"])
        self.assertEqual(dust_bytes, tactics.library_path().read_bytes())

    def test_package_header_controls_validation_and_selected_map_must_match(self):
        code = "de_inferno"
        value = map_tactic(code)
        meta = tactics.map_metadata(code)
        value["slots"][0]["steps"][0]["position"] = [meta["pos_x"], meta["pos_y"]]
        package = {"schema_version": 1, "map": code, "tactics": [value]}
        clean = tactics.validate_library(package)
        self.assertEqual(code, clean["map"])
        with self.assertRaises(ValueError):
            tactics.validate_tactic(value)
        result = tactics.import_tactics(package)
        self.assertEqual(code, result["map"])
        before = tactics.library_path(code).read_bytes()
        with self.assertRaisesRegex(ValueError, "地图不一致"):
            tactics.import_tactics(package, "de_dust2")
        self.assertEqual(before, tactics.library_path(code).read_bytes())
        self.assertFalse(tactics.library_path().exists())
        tactics.library_path("de_mirage").write_bytes(tactics.encode_library(clean))
        with self.assertRaisesRegex(ValueError, "地图不一致"):
            tactics.load_library("de_mirage")

    def test_standalone_import_uses_selection_and_wrapped_map_is_enforced(self):
        tactics.import_tactics({"tactic": map_tactic("de_dust2", "legacy")})
        tactics.import_tactics(map_tactic("de_nuke", "selected"), "de_nuke")
        tactics.import_tactics({"map": "de_train", "tactic": map_tactic("de_train", "wrapped")})
        self.assertEqual(["legacy"], [row["id"] for row in tactics.load_library()["tactics"]])
        self.assertEqual(["selected"], [row["id"] for row in tactics.load_library("de_nuke")["tactics"]])
        self.assertEqual(["wrapped"], [row["id"] for row in tactics.load_library("de_train")["tactics"]])
        with self.assertRaisesRegex(ValueError, "地图不一致"):
            tactics.import_tactics({"map": "de_train", "tactic": map_tactic("de_train")}, "de_nuke")
        with self.assertRaises(ValueError):
            tactics.import_tactics({"map": "de_train", "tactic": map_tactic("de_train"), "path": "game"})

    def test_unsupported_maps_are_rejected_before_creating_paths(self):
        for code in ("../de_dust2", "de_unknown", "mirage", "DE_DUST2", "", None, True):
            with self.subTest(map=code):
                for operation in (tactics.library_path, tactics.load_library, tactics.public_library, tactics.empty_library):
                    with self.assertRaises(ValueError):
                        operation(code)
                with self.assertRaises(ValueError):
                    tactics.save_tactic(tactic(), code)
                with self.assertRaises(ValueError):
                    tactics.validate_library({**pack(), "map": code})
        self.assertFalse((self.root / "save").exists())
        for code in tactics.SUPPORTED_MAPS:
            self.assertEqual(code, tactics.canonical_map(code))
            self.assertEqual(code, tactics.canonical_map(code.removeprefix("de_")))
        with self.assertRaises(ValueError):
            tactics.canonical_map("../mirage")


class TacticalHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp = isolated_temp()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root), "CS2CAREER_NO_GAME": "1"})
        env.start()
        self.addCleanup(env.stop)
        examples = example_source(self.root / "missing_examples.json")
        examples.start()
        self.addCleanup(examples.stop)
        self.state = ApplicationDouble(persist=lambda: self.fail("tactics API persisted career"),
                                     payload=lambda *args: self.fail("tactics API inspected career"))
        self.server = create_server(self.state)
        self.server.preview = True
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_server)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def close_server(self):
        self.server.shutdown()
        self.worker.join(timeout=5)
        self.server.server_close()

    def request(self, path, value=None, token=True, raw=None):
        blob = raw if raw is not None else (json.dumps(value).encode() if value is not None else None)
        req = Request(self.base + path, data=blob, headers={"X-Career-Token": self.server.token if token else ""})
        with urlopen(req, timeout=5) as response:
            return json.load(response)

    def test_authorized_read_edit_import_delete_never_mutates_career_or_game(self):
        game = self.root / "mock_game" / "tactical_playbook.json"
        game.parent.mkdir()
        game.write_bytes(b"game-sentinel")
        result = self.request("/api/tactics")
        self.assertEqual(tactics.map_metadata(), result["map_meta"])
        self.assertIn("箭头观察", result["runtime_note"])
        self.assertIn("T 守包、CT 回防", result["runtime_note"])
        with patch.object(launch, "_deploy_tactical_playbook", side_effect=AssertionError("API must not deploy")):
            self.assertTrue(self.request("/api/tactics/save", {"tactic": tactic()})["ok"])
            result = self.request("/api/tactics/import", pack(tactic(name="HTTP覆盖"), tactic("new")))
            self.assertEqual(["test_a"], result["overwritten_ids"])
            self.request("/api/tactics/delete", {"id": "new"})
        self.assertEqual(b"game-sentinel", game.read_bytes())
        self.assertEqual(["test_a"], [t["id"] for t in self.request("/api/tactics")["tactics"]])

    def test_auth_validation_and_body_limit(self):
        for path, value in (("/api/tactics", None), ("/api/tactics/save", {"tactic": tactic()})):
            with self.assertRaises(HTTPError) as error:
                self.request(path, value, token=False)
            self.assertEqual(403, error.exception.code)
        for path, value in (("/api/tactics/save", {}), ("/api/tactics/delete", {"id": "../bad"}),
                            ("/api/tactics/import", {"tactic": tactic(), "path": "game"})):
            with self.assertRaises(HTTPError) as error:
                self.request(path, value)
            self.assertEqual(400, error.exception.code)
        with self.assertRaises(HTTPError) as error:
            self.request("/api/tactics/import", raw=b" " * (tactics.MAX_BYTES + 1))
        self.assertEqual(413, error.exception.code)
        self.assertFalse(tactics.library_path().exists())

    def test_map_queries_save_delete_and_import_are_isolated(self):
        self.request("/api/tactics/save", {"tactic": tactic()})
        self.request("/api/tactics/save", {"map": "de_mirage", "tactic": map_tactic("de_mirage", "test_a")})
        result = self.request("/api/tactics?map=de_mirage")
        self.assertEqual("de_mirage", result["map"])
        self.assertEqual(tactics.map_metadata("de_mirage"), result["map_meta"])
        self.assertEqual(10, len(result["available_maps"]))
        self.assertEqual(["test_a"], [row["id"] for row in result["tactics"]])
        self.request("/api/tactics/import?map=de_mirage", {"tactic": map_tactic("de_mirage", "new")})
        self.request("/api/tactics/delete", {"map": "de_mirage", "id": "test_a"})
        self.assertEqual(["new"], [row["id"] for row in self.request("/api/tactics?map=de_mirage")["tactics"]])
        self.assertEqual(["test_a"], [row["id"] for row in self.request("/api/tactics")["tactics"]])
        self.request("/api/tactics/import", {"map": "de_nuke", "tactic": map_tactic("de_nuke", "wrapped")})
        self.assertEqual(["wrapped"], [row["id"] for row in self.request("/api/tactics?map=de_nuke")["tactics"]])
        before = tactics.library_path("de_mirage").read_bytes()
        for path, body in (("/api/tactics?map=de_unknown", None),
                           ("/api/tactics?map=de_mirage&map=de_nuke", None),
                           ("/api/tactics?map=", None),
                           ("/api/tactics/save", {"map": "../de_mirage", "tactic": tactic()}),
                           ("/api/tactics/import?map=de_mirage", pack(tactic("wrong"))),
                           ("/api/tactics/import?map=de_mirage", {"map": "de_nuke", "tactic": map_tactic("de_nuke")}),
                           ("/api/tactics/delete", {"map": "de_mirage", "id": "new", "path": "game"})):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(path, body)
            self.assertEqual(400, error.exception.code)
            self.assertEqual(before, tactics.library_path("de_mirage").read_bytes())

    def test_http_preserves_assignment_fields_and_rejects_whole_invalid_import(self):
        value = map_tactic("de_nuke", "ability")
        value.update(assignment="ability", human_slot=3)
        value["slots"][1]["duty"] = "awp"
        value["slots"][3]["duty"] = "awp"
        result = self.request("/api/tactics/save", {"map": "de_nuke", "tactic": value})
        self.assertEqual("ability", result["tactic"]["assignment"])
        stored = self.request("/api/tactics?map=de_nuke")["tactics"][0]
        self.assertEqual(3, stored["human_slot"])
        self.assertEqual("awp", stored["slots"][1]["duty"])
        before = tactics.library_path("de_nuke").read_bytes()
        invalid = {**value, "id": "invalid", "assignment": "roster"}
        with self.assertRaises(HTTPError) as error:
            self.request("/api/tactics/import?map=de_nuke", {"schema_version": 1, "map": "de_nuke", "tactics": [value, invalid]})
        self.assertEqual(400, error.exception.code)
        self.assertEqual(before, tactics.library_path("de_nuke").read_bytes())

    def test_http_movement_round_trip_and_invalid_save_import_are_atomic(self):
        value = movement_tactic("de_mirage")
        result = self.request("/api/tactics/save", {"map": "de_mirage", "tactic": value})
        expected = result["tactic"]
        stored = self.request("/api/tactics?map=de_mirage")["tactics"]
        self.assertEqual([expected], stored)
        package = {"schema_version": 1, "map": "de_mirage", "tactics": stored}
        self.assertEqual(stored, self.request("/api/tactics/import?map=de_mirage", package)["tactics"])
        before = tactics.library_path("de_mirage").read_bytes()
        invalid = movement_tactic("de_mirage", "invalid")
        invalid["slots"][0]["steps"][1]["movement"] = "sprint"
        for path, payload in (("/api/tactics/save", {"map": "de_mirage", "tactic": invalid}),
                              ("/api/tactics/import?map=de_mirage", {**package, "tactics": [value, invalid]})):
            with self.subTest(path=path), self.assertRaises(HTTPError) as error:
                self.request(path, payload)
            self.assertEqual(400, error.exception.code)
            self.assertEqual(before, tactics.library_path("de_mirage").read_bytes())


class TacticalDeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = isolated_temp()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        env = patch.dict(os.environ, {"CS2CAREER_SAVE_DIR": str(self.root / "save")})
        env.start()
        self.addCleanup(env.stop)
        examples = example_source(self.root / "missing_examples.json")
        examples.start()
        self.addCleanup(examples.stop)
        self.csgo = self.root / "game" / "csgo"
        self.csgo.mkdir(parents=True)
        live = patch.object(launch, "cs2_is_live", return_value=False)
        live.start()
        self.addCleanup(live.stop)

    def test_snapshot_deploy_is_validated_atomic_and_never_replaced_live(self):
        tactics.save_tactic(tactic())
        self.assertEqual(len(tactics.SUPPORTED_MAPS) + 1, launch._deploy_tactical_playbook(self.csgo))
        for code in tactics.SUPPORTED_MAPS:
            book = launch.plugin_dir(self.csgo) / 'tactical_playbooks' / (code + '.json')
            self.assertEqual(tactics.load_library(code), json.loads(book.read_bytes()))
        target = launch.plugin_dir(self.csgo) / "tactical_playbook.json"
        before = target.read_bytes()
        self.assertEqual(tactics.load_library(), json.loads(before))
        self.assertEqual(0, launch._deploy_tactical_playbook(self.csgo))
        tactics.save_tactic(tactic("new"))
        self.assertEqual(before, target.read_bytes())
        with patch.object(launch, "cs2_is_live", return_value=True):
            with self.assertRaisesRegex(ValueError, "退出 CS2"):
                launch._deploy_tactical_playbook(self.csgo)
        self.assertEqual(before, target.read_bytes())
        with patch.object(tactics.os, "replace", side_effect=PermissionError("locked")):
            with self.assertRaises(PermissionError):
                launch._deploy_tactical_playbook(self.csgo)
        self.assertEqual(before, target.read_bytes())
        self.assertFalse(list(target.parent.glob("*.tmp")))

    def test_snapshot_preserves_optional_movement_and_rejects_invalid_data(self):
        value = movement_tactic("de_train")
        tactics.save_tactic(value, "de_train")
        package = tactics.load_library("de_train")
        self.assertEqual(len(tactics.SUPPORTED_MAPS) + 1, launch._deploy_tactical_playbook(self.csgo, package))
        target = launch.plugin_dir(self.csgo) / "tactical_playbook.json"
        before = target.read_bytes()
        self.assertEqual(package, json.loads(before))
        invalid = json.loads(before)
        invalid["tactics"][0]["slots"][0]["steps"][1]["movement"] = None
        with self.assertRaisesRegex(ValueError, "移动方式"):
            launch._deploy_tactical_playbook(self.csgo, invalid)
        self.assertEqual(before, target.read_bytes())

    def test_install_deploys_local_library_not_mod_supplied_playbook(self):
        (self.csgo / "gameinfo.gi").write_text(
            '"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n'
            '\t\t\tGame csgo\n\t\t}\n\t}\n}\n', encoding="utf-8")
        mod = self.root / "mod"
        for name in ("addons/metamod", "addons/counterstrikesharp", "overrides"):
            (mod / name).mkdir(parents=True)
        source = launch.plugin_dir(mod) / "tactical_playbook.json"
        source.parent.mkdir(parents=True)
        source.write_text("untrusted-mod-data")
        tactics.save_tactic(tactic())
        with patch.object(launch, "settings", return_value=dict(launch.DEFAULTS)), \
             patch.object(launch, "_copy_career_match", return_value=0), \
             patch.object(launch, "_copy_botbuy_patch", return_value=0), \
             patch.object(launch, "hook_competitive_cfg"), patch.object(launch, "apply_bothider_config"):
            launch.install_mod(self.csgo, mod)
        self.assertEqual(tactics.load_library(), json.loads((launch.plugin_dir(self.csgo) / "tactical_playbook.json").read_bytes()))

    def test_prepare_uses_validated_library_before_other_game_writes(self):
        mod = self.root / "mod"
        mod.mkdir()
        tactics.library_path().write_bytes(b"{invalid")
        with patch.object(launch, "mod_installed", return_value=True), \
             patch.object(launch, "_copy_career_match") as copy_plugin, \
             patch.object(launch, "_copy_botbuy_patch") as copy_buy:
            with self.assertRaises(ValueError):
                launch.prepare_game(self.csgo, mod, {"map": "de_dust2", "observer": False}, dict(launch.DEFAULTS))
            copy_plugin.assert_not_called()
            copy_buy.assert_not_called()
        self.assertEqual([], list(self.csgo.rglob("*")))

    def test_full_existing_prepare_deploys_without_launching(self):
        from test_v15_core import fake_team
        (self.csgo / "gameinfo.gi").write_text(
            '"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n'
            '\t\t\tGame csgo\n\t\t}\n\t}\n}\n', encoding="utf-8")
        for name in ("addons/metamod", "addons/counterstrikesharp", "addons/BotHider"):
            (self.csgo / name).mkdir(parents=True, exist_ok=True)
        mod = self.root / "mod"
        mod.mkdir()
        tactics.save_tactic(tactic())
        request = launch.build_request(fake_team("A", 90), fake_team("B", 86), "A0", "de_dust2", "ct")
        with patch.object(launch, "_copy_career_match", return_value=0), \
             patch.object(launch, "_copy_botbuy_patch", return_value=0), \
             patch.object(launch, "install_skins_plugin", return_value=0), \
             patch.object(launch, "launch_cs2") as start:
            launch.prepare_game(self.csgo, mod, request, dict(launch.DEFAULTS))
            start.assert_not_called()
        target = launch.plugin_dir(self.csgo) / "tactical_playbook.json"
        self.assertEqual(tactics.load_library(), json.loads(target.read_bytes()))
        self.assertEqual(request["nonce"], json.loads((target.parent / "match_request.json").read_bytes())["nonce"])

    def test_prepare_selects_current_map_snapshot_including_short_arena_map_names(self):
        from test_v15_core import fake_team
        (self.csgo / "gameinfo.gi").write_text(
            '"GameInfo"\n{\n\t"FileSystem"\n\t{\n\t\t"SearchPaths"\n\t\t{\n'
            '\t\t\tGame csgo\n\t\t}\n\t}\n}\n', encoding="utf-8")
        for name in ("addons/metamod", "addons/counterstrikesharp", "addons/BotHider"):
            (self.csgo / name).mkdir(parents=True, exist_ok=True)
        mod = self.root / "mod"
        mod.mkdir()
        tactics.save_tactic(tactic("dust_only"))
        tactics.save_tactic(movement_tactic("de_mirage", "mirage_only"), "de_mirage")
        dust_before = tactics.library_path().read_bytes()
        for match_map in ("de_mirage", "mirage"):
            request = launch.build_request(fake_team("A", 90), fake_team("B", 86), "A0", match_map, "ct")
            with patch.object(launch, "_copy_career_match", return_value=0), \
                 patch.object(launch, "_copy_botbuy_patch", return_value=0), \
                 patch.object(launch, "install_skins_plugin", return_value=0), \
                 patch.object(launch, "launch_cs2") as start:
                launch.prepare_game(self.csgo, mod, request, dict(launch.DEFAULTS))
                start.assert_not_called()
            target = launch.plugin_dir(self.csgo) / "tactical_playbook.json"
            self.assertEqual(tactics.load_library("de_mirage"), json.loads(target.read_bytes()))
            self.assertEqual(dust_before, tactics.library_path().read_bytes())

    def test_prepare_rejects_unknown_map_before_game_writes(self):
        mod = self.root / "mod"
        mod.mkdir()
        with patch.object(launch, "mod_installed", return_value=True), \
             patch.object(launch, "_copy_career_match") as copy_plugin, \
             patch.object(launch, "_copy_botbuy_patch") as copy_buy:
            with self.assertRaises(ValueError):
                launch.prepare_game(self.csgo, mod, {"map": "de_unknown", "observer": False}, dict(launch.DEFAULTS))
            copy_plugin.assert_not_called()
            copy_buy.assert_not_called()
        self.assertEqual([], list(self.csgo.rglob("*")))


if __name__ == "__main__":
    unittest.main()
