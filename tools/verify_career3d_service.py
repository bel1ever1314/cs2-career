"""Black-box checks against fresh, explicitly isolated E-drive demo saves."""
from __future__ import annotations

import argparse
from datetime import date, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
AUDITED_LAUNCH = """
import os, runpy, sys
root = sys.argv[1]
sys.argv = sys.argv[2:]
protected = [os.path.normcase(os.path.abspath(os.path.join(root, name))) for name in ('save', 'extensions')]
def reject_regular_data(event, args):
    if event not in ('open', 'os.scandir') or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
        return
    path = os.path.normcase(os.path.abspath(os.fsdecode(args[0])))
    if any(path == base or path.startswith(base + os.sep) for base in protected):
        raise RuntimeError('Verification forbids all access to regular save and extensions')
sys.addaudithook(reject_regular_data)
runpy.run_path(sys.argv[0], run_name='__main__')
"""
OWNER_LAUNCH = """
import json, os, pathlib, subprocess, sys, time
root, folder, audit = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
folder.mkdir(parents=True, exist_ok=True)
with (folder / 'service.stdout.log').open('w', encoding='utf-8') as out, (folder / 'service.stderr.log').open('w', encoding='utf-8') as err:
    child = subprocess.Popen([sys.executable, '-c', audit, str(root), str(root / 'tools' / 'career3d_service.py'),
        '--data-dir', str(folder / 'data'), '--port', '127.0.0.1:0', '--ready-file', str(folder / 'ready.json'),
        '--no-cs2-config',
        '--parent-pid', str(os.getpid())], stdin=subprocess.DEVNULL, stdout=out, stderr=err,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    print(json.dumps({'parent_pid': os.getpid(), 'service_pid': child.pid}), flush=True)
    while not (folder / 'owner-exit.request').exists():
        time.sleep(0.05)
"""


class Client:
    def __init__(self, folder, mode="normal"):
        self.folder = folder
        self.ready_path = folder / "ready.json"
        self.process = subprocess.Popen(
            [sys.executable, "-c", AUDITED_LAUNCH, str(ROOT), str(ROOT / "tools" / "career3d_service.py"),
             "--data-dir", str(folder / "data"), "--port", "127.0.0.1:0",
             "--no-cs2-config",
             "--ready-file", str(self.ready_path), "--mode", mode],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if self.ready_path.exists():
                self.ready = json.loads(self.ready_path.read_text("utf-8"))
                return
            if self.process.poll() is not None:
                raise RuntimeError(self.process.communicate())
            time.sleep(0.05)
        self.process.kill()
        raise RuntimeError("service did not publish readiness")

    def api(self, path, body=None, token=True, expected=200):
        headers = {"Content-Type": "application/json"}
        if token:
            headers["X-Career-Token"] = self.ready["token"]
        request = Request(self.ready["base_url"] + path,
                          data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                status, payload = response.status, json.loads(response.read())
        except HTTPError as exc:
            status, payload = exc.code, json.loads(exc.read())
        assert status == expected, (status, payload)
        return payload

    def context(self):
        return self.api("/api/3d/context")

    def calendar(self, target, request_id=None):
        context = self.context()
        return self.api("/api/3d/calendar", {"target_date": target,
                         "revision": context["calendar"]["revision"],
                         "request_id": request_id or uuid4().hex})

    def ack_all(self):
        count = 0
        while self.context()["stories"]:
            row = self.context()["stories"][0]
            choices = row["choices"]
            self.api("/api/3d/story", {"id": row["id"], "choice": choices[0]["id"] if choices else ""})
            count += 1
            assert count < 40, "story choice chain failed to settle"
        return count

    def hashes(self):
        return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in (self.folder / "data" / "save").glob("*.json")}

    def close(self):
        self.api("/api/3d/shutdown", {})
        stdout, stderr = self.process.communicate(timeout=20)
        assert self.process.returncode == 0, (stdout, stderr)
        assert not self.ready_path.exists(), "readiness must be removed on normal exit"


def normal_checks(folder):
    client = Client(folder)
    checks = []
    try:
        client.api("/api/3d/context", token=False, expected=403)
        client.api("/api/3d/match?id=missing", token=False, expected=403)
        client.api("/api/3d/match?id=missing", expected=404)
        client.api("/api/3d/shutdown", {}, token=False, expected=403)
        client.api("/api/cs2/status", expected=404)
        client.api("/api/cs2/settings", {}, expected=403)
        checks.append("token protection, disabled CS2 endpoints and audit rejection of all regular-save/extension access")
        initial = client.context()
        duplicate = subprocess.run([sys.executable, "-c", AUDITED_LAUNCH, str(ROOT),
            str(ROOT / "tools" / "career3d_service.py"), "--data-dir", str(folder / "data"),
            "--ready-file", str(folder / "duplicate-ready.json")],
            capture_output=True, text=True, encoding="utf-8", timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        assert duplicate.returncode == 2 and "already using" in duplicate.stderr
        assert not (folder / "duplicate-ready.json").exists()
        checks.append("second process cannot load or write the same demo save pair")
        assert initial["origin"] == "academy" and initial["mode"] == "normal"
        roster = initial["team"]["roster"]
        assert len(roster) == 5 and len({r["id"] for r in roster}) == 5
        assert len([r for r in roster if r["id"] != initial["player"]["id"]]) == 4
        assert all(r["name"] and r["id"] for r in roster)
        assert initial["clock"]["display_only"] and not initial["clock"]["hourly_absence_implemented"]
        checks.append("academy creation, five stable player identities and display-only clock")
        before = client.hashes()
        for _ in range(5):
            assert client.context() == initial
        assert client.hashes() == before
        checks.append("repeated read-only context leaves saved state unchanged")
        target = (date.fromisoformat(initial["date"]) + timedelta(days=1)).isoformat()
        if initial["stories"]:
            held = client.calendar(target)
            assert held["status"] == "paused" and held["actualdate"] == initial["date"]
            client.ack_all()
            checks.append("pending initial story pauses without date advancement")
        request_id = uuid4().hex
        result = client.calendar(target, request_id)
        assert result["status"] == "reached" and result["actualdate"] == target, result
        state_hash = client.hashes()
        replay = client.api("/api/3d/calendar", {"target_date": target, "request_id": request_id, "revision": -1})
        assert replay["replayed"] and replay["actualdate"] == target and client.hashes() == state_hash
        checks.append("exact empty-day target and idempotent calendar replay")
        current = client.context()
        body = {"target_date": current["date"], "revision": current["calendar"]["revision"], "request_id": uuid4().hex}
        for changed in ({"target_date": initial["date"]}, {"target_date": "2027-01-01"}, {"display_hour": 24}, {"revision": -1}):
            client.api("/api/3d/calendar", {**body, **changed}, expected=400)
        assert client.hashes() == state_hash
        checks.append("past date, year crossing, invalid hour and stale revision rejected without writes")
        context = client.context()
        event_lookup = {e["id"]: e for e in context["calendar_events"]}
        invitations = [r for r in context["inbox"] if r["kind"] == "invite" and r["status"] == "open"]
        assert invitations, context["inbox"]
        invitation = min(invitations, key=lambda r: event_lookup[r["event_id"]]["date"])
        assert invitation["evname"] == event_lookup[invitation["event_id"]]["name"] and invitation["dates"]
        accepted = client.api("/api/3d/mail/accept", {"id": invitation["id"]})
        assert any(e["id"] == invitation["event_id"] and e["registered"] for e in accepted["context"]["calendar_events"])
        event = event_lookup[invitation["event_id"]]
        target = event["end_date"]
        for _ in range(20):
            result = client.calendar(target)
            assert result["actualdate"] <= target
            if result["reason_code"] == "player_match":
                break
            client.ack_all()
            assert result["status"] != "reached", result
        else:
            raise AssertionError("accepted event never exposed a player fixture")
        context = client.context()
        match_id = context["nextmatch"]["id"]
        assert context["nextmatch"]["due"] and not context["recent_matches"]
        held_date = context["date"]
        held = client.calendar(target)
        assert held["status"] == "paused" and held["actualdate"] == held_date
        checks.append("accepted invitation produces own fixture, calendar stops before simulating it")
        for _ in range(15):
            response = client.api("/api/3d/match/simulate", {"match_id": match_id})
            if any(r["id"] == match_id for r in response["context"]["recent_matches"]):
                break
            if response["context"]["stories"]:
                held = client.calendar(target)
                assert held["status"] == "paused" and held["reason_code"] == "story"
                assert held["actualdate"] == response["context"]["date"]
            client.ack_all()
        else:
            raise AssertionError("explicit player match simulation never finished")
        completed = next(r for r in client.context()["recent_matches"] if r["id"] == match_id)
        assert completed["winner"] and completed["series"]
        checks.append("explicit real-engine player series simulation produces a saved winner and score")
        detail_path = "/api/3d/match?id=" + quote(match_id, safe="")
        saved_before = client.hashes()
        detail = client.api(detail_path)
        assert detail["ok"] and detail["yours"] and detail["match"]["data_complete"]
        totals = detail["match"]["totals"]
        assert len(totals) == 10 and len({p["player_id"] for p in totals}) == 10
        assert all(p["data_complete"] and p["rating"] is not None for p in totals)
        assert all(mp["data_complete"] and mp["source"] == "sim" for mp in detail["match"]["maps"])
        for _ in range(3):
            assert client.api(detail_path) == detail
        assert client.hashes() == saved_before
        checks.append("authenticated match detail returns ten actual player totals and repeated reads never alter saved state")
        match_contract = {"response_keys": sorted(detail), "match_keys": sorted(detail["match"]),
                          "total_keys": sorted(totals[0]), "map_keys": sorted(detail["match"]["maps"][0]),
                          "player_total": next(r for r in totals if r["player_id"] == initial["player"]["id"])}
        client.ack_all()
        for _ in range(10):
            birthday_result = client.calendar("2026-03-04")
            if any(r["id"].startswith("bday.2026-03-03.fame") for r in birthday_result["context"]["stories"]):
                break
            assert birthday_result["status"] == "progress", birthday_result
        else:
            raise AssertionError("fame birthday was not exposed on its real date")
        assert birthday_result["status"] == "paused" and birthday_result["actualdate"] == "2026-03-03"
        checks.append("mandatory story gate retains date and roster birthday pauses on March 3 before a March 4 target")
        settled = client.context()
        client.close()
    except BaseException:
        if client.process.poll() is None:
            try:
                client.close()
            except BaseException:
                client.process.kill()
                client.process.communicate()
        raise
    reloaded = Client(folder)
    try:
        after = reloaded.context()
        for key in ("date", "player", "team", "money", "attr_points", "recent_matches"):
            assert settled[key] == after[key], key
        checks.append("normal shutdown removes handshake and restart retains career settlement")
    finally:
        reloaded.close()
    return {"checks": checks, "initial_date": initial["date"], "final_date": settled["date"],
            "roster": initial["team"]["roster"], "simulated_match": completed, "match_contract": match_contract}


def quick_checks(folder):
    client = Client(folder, "quick")
    try:
        context = client.context()
        assert context["mode"] == "quick"
        client.ack_all()
        target = (date.fromisoformat(context["date"]) + timedelta(days=1)).isoformat()
        result = client.calendar(target, "q" * 100)
        assert result["actualdate"] == target and result["status"] == "reached", result
        return {"checks": ["quick-mode domain command retains exact date cap and supports a 100-character request ID"],
                "final_date": result["actualdate"]}
    finally:
        client.close()


def parent_exit_checks(folder):
    """A real owner process launches the child service and exits without shutdown HTTP."""
    from career3d_service import ParentProcessMonitor
    owner = subprocess.Popen([sys.executable, "-c", OWNER_LAUNCH, str(ROOT), str(folder), AUDITED_LAUNCH],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    ownership = json.loads(owner.stdout.readline())
    child_monitor = ParentProcessMonitor(ownership["service_pid"])
    client = Client.__new__(Client)
    client.folder, client.ready_path = folder, folder / "ready.json"
    try:
        deadline = time.monotonic() + 20
        while not client.ready_path.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert client.ready_path.exists(), "owned service did not start"
        client.ready = json.loads(client.ready_path.read_text("utf-8"))
        assert client.ready["parent_pid"] == ownership["parent_pid"]
        initial = client.context()
        client.ack_all()
        target = (date.fromisoformat(initial["date"]) + timedelta(days=1)).isoformat()
        result = client.calendar(target)
        assert result["status"] == "reached"
        settled = client.context()
        started = time.monotonic()
        (folder / "owner-exit.request").write_text("exit", encoding="ascii")
        owner.communicate(timeout=10)
        assert owner.returncode == 0
        if os.name == "nt":
            assert child_monitor.kernel.WaitForSingleObject(child_monitor.handle, 5000) == 0, "child service failed to exit"
        else:
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(ownership["service_pid"], 0)
                except ProcessLookupError:
                    break
                time.sleep(0.05)
            else:
                raise AssertionError("child service failed to exit")
        elapsed = time.monotonic() - started
        assert elapsed < 5, elapsed
        assert not client.ready_path.exists(), "parent exit must remove readiness"
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            child_monitor.kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            child_monitor.kernel.GetExitCodeProcess.restype = wintypes.BOOL
            code = wintypes.DWORD()
            assert child_monitor.kernel.GetExitCodeProcess(child_monitor.handle, ctypes.byref(code))
            assert code.value == 0, code.value
        saved = json.loads((folder / "data" / "save" / "season.json").read_text("utf-8"))
        assert saved["date"] == settled["date"]
    finally:
        child_monitor.close()
        if owner.poll() is None:
            (folder / "owner-exit.request").write_text("exit", encoding="ascii")
            owner.communicate(timeout=10)
    # Starting the same directory again proves that the dead child released the save lock.
    reloaded = Client(folder)
    try:
        after = reloaded.context()
        for key in ("date", "player", "team", "money", "attr_points"):
            assert settled[key] == after[key], key
    finally:
        reloaded.close()
    return {"checks": ["real parent exit gracefully stops child, persists state, removes handshake and releases save lock",
                       "restarting without --parent-pid retains independent CLI behavior"],
            "parent_pid": ownership["parent_pid"], "service_pid": ownership["service_pid"],
            "shutdown_seconds": round(elapsed, 3), "saved_date": settled["date"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    folder = args.output_dir.resolve()
    if os.name == "nt" and folder.drive.upper() != "E:":
        parser.error("These black-box checks must use an isolated E-drive directory")
    if folder.exists():
        parser.error("Select a new output directory; verification does not overwrite existing runs")
    report = {"ok": True, "normal": normal_checks(folder / "normal"), "quick": quick_checks(folder / "quick"),
              "parent_exit": parent_exit_checks(folder / "parent-exit")}
    report_path = folder / "verification.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
