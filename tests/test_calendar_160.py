"""Calendar provenance and era regressions; never load a player save."""
import unittest
from copy import deepcopy
from types import SimpleNamespace

from cs2career.league.calendar import calendar_for, reconcile_calendar, validate_calendar
from cs2career.league import formats
from cs2career.league.season import Season, _blank_event
from cs2career.career import Career


class Calendar160Tests(unittest.TestCase):
    def test_verified_years_and_correct_major_cities(self):
        expected = {2024: ("Copenhagen", "Shanghai"), 2025: ("Austin", "Budapest"),
                    2026: ("Cologne", "Singapore")}
        for year, cities in expected.items():
            calendar = calendar_for(year, include_extensions=False)
            validate_calendar(calendar)
            majors = [ev for ev in calendar["events"] if ev["type"] == "major"]
            self.assertEqual(2, len(majors))
            for ev, city in zip(majors, cities):
                self.assertIn(city, ev["name"])
                self.assertEqual(24 if year == 2024 else 32, ev["size"])
                self.assertEqual(13 if year == 2024 else 18, len(ev["dates"]))
                self.assertEqual(ev["real_event_dates"], [ev["dates"][0], ev["dates"][-1]])
            for ev in calendar["events"]:
                self.assertEqual("verified_edition", ev["provenance"]["status"])
                self.assertTrue(ev["provenance"]["sources"])
                self.assertNotIn("Play-In", ev["name"])
                self.assertNotIn("fictional", ev)

    def test_no_year_relabel_and_qualified_paths(self):
        events = calendar_for(2025, include_extensions=False)["events"]
        major = next(ev for ev in events if ev["id"] == "major-1")
        qualifiers = [ev for ev in events if ev.get("feeds") == major["id"]]
        self.assertEqual(3, len(qualifiers))
        self.assertTrue(all(ev["gate"] == "mrq" for ev in qualifiers))
        self.assertTrue(all(ev["dates"][-1] < major["dates"][0] for ev in qualifiers))
        self.assertFalse(any(ev.get("gate") == "rmr" for ev in events))
        with self.assertRaises(ValueError):
            calendar_for(2023, include_extensions=False)

    def test_future_is_explicit_and_no_historical_brand_recycling(self):
        events = calendar_for(2030, include_extensions=False)["events"]
        self.assertEqual(2, sum(ev["type"] == "major" for ev in events))
        for ev in events:
            self.assertTrue(ev["fictional"])
            self.assertIn("模拟", ev["name"])
            self.assertEqual("future_simulation", ev["provenance"]["status"])
            self.assertNotIn("2026", ev["name"])

    def test_complete_major_stays_in_real_event_window(self):
        for year in (2024, 2025, 2026):
            for ev in calendar_for(year, include_extensions=False)["events"]:
                if ev["type"] != "major":
                    continue
                ev["matches"] = formats.open_event(ev, [f"T{i}" for i in range(ev["size"])])
                for _ in range(25):
                    for match in ev["matches"]:
                        if not match["played"]:
                            match.update(played=True, winner=match["team_a"])
                    if formats.is_complete(ev):
                        break
                    ev["matches"].extend(formats.advance_event(ev))
                self.assertTrue(formats.is_complete(ev))
                self.assertEqual(ev["real_event_dates"][-1], ev["matches"][-1]["date"])
                self.assertTrue(all(ev["real_event_dates"][0] <= m["date"] <= ev["real_event_dates"][-1]
                                    for m in ev["matches"]))

    def test_save_reconciliation_preserves_live_and_done(self):
        existing = [
            {"id": "major-1", "status": "done", "name": "Saved history", "dates": ["2026-06-20"], "matches": [{"winner": "A"}]},
            {"id": "ongoing", "status": "live", "dates": ["2026-09-25"], "matches": [{"played": False}]},
            {"id": "invented", "status": "upcoming", "dates": ["2026-10-01"]}]
        before = deepcopy(existing)
        updated = reconcile_calendar(existing, calendar_for(2026, include_extensions=False)["events"], "2026-09-27")
        self.assertEqual(before, existing)
        self.assertEqual(before[0], next(ev for ev in updated if ev["id"] == "major-1"))
        self.assertEqual(before[1], next(ev for ev in updated if ev["id"] == "ongoing"))
        self.assertNotIn("invented", {ev["id"] for ev in updated})
        self.assertEqual(1, sum(ev["id"] == "major-1" for ev in updated))
        self.assertTrue(all(ev["dates"][0] >= "2026-09-27" for ev in updated if ev.get("status", "upcoming") == "upcoming"))

    def test_bad_feeds_rejected(self):
        blob = calendar_for(2024, include_extensions=False)
        blob["events"][0]["feeds"] = "missing"
        with self.assertRaises(ValueError):
            validate_calendar(blob)

    def test_season_uses_real_calendar_and_alignment_is_idempotent(self):
        season = Season.__new__(Season)
        season.year = 2025
        season.date = "2025-01-08"
        season.events = [_blank_event(e) for e in calendar_for(2025, include_extensions=False)["events"]]
        self.assertFalse(season.align_calendar())
        self.assertFalse(season._calendar_replaced_ids)
        major = next(ev for ev in season.events if ev["id"] == "major-1")
        self.assertTrue(season.has_qualifier(major))
        self.assertEqual(24, season.dest_direct(major))
        untouched = deepcopy(season.events)
        self.assertFalse(season.align_calendar())
        self.assertEqual(untouched, season.events)

    def test_regional_qualifier_and_austin_invites(self):
        season = Season.__new__(Season)
        season.year = 2025
        season.qualified = {}
        season.events = [_blank_event(e) for e in calendar_for(2025, include_extensions=False)["events"]]
        career = Career.__new__(Career)
        career.team_id = "player-club"
        major = next(ev for ev in season.events if ev["id"] == "major-1")
        mrq = next(ev for ev in season.events if ev.get("feeds") == "major-1" and ev["region"] == "EU")
        ranking = {"id": career.team_id, "rank": 30, "region": "EU"}
        self.assertFalse(career.eligible_invite(season, major, rank_row=ranking))
        self.assertTrue(career.eligible_invite(season, mrq, rank_row=ranking))
        self.assertFalse(career.eligible_invite(season, mrq, rank_row={**ranking, "region": "AS"}))
        season.qualified[major["id"]] = [career.team_id]
        self.assertTrue(career.eligible_invite(season, major, rank_row=ranking))
        self.assertFalse(career.eligible_invite(season, mrq, rank_row=ranking))
        regional = next(ev for ev in season.events if ev.get("regional_only") and ev["region"] == "AS")
        self.assertFalse(career.eligible_invite(season, regional, rank_row=ranking))

    def test_regional_qualifier_field_does_not_become_global(self):
        season = Season.__new__(Season)
        season.year = 2025
        season.career = None
        season.events = [_blank_event(e) for e in calendar_for(2025, include_extensions=False)["events"]]
        season.teams = [{"id": str(i), "name": str(i), "region": "EU" if i < 20 else "AS"} for i in range(40)]
        season.ranked = lambda: list(season.teams)
        qualifier = next(ev for ev in season.events if ev.get("feeds") == "iem-dallas" and ev["region"] == "AS")
        field = season.field_for(qualifier)
        self.assertEqual(qualifier["size"], len(field))
        self.assertTrue(all(t["region"] == "AS" for t in field))

    def test_declined_regional_event_replaces_player_with_local_reserve(self):
        season = Season.__new__(Season)
        season.year = 2026
        season.date = "2026-01-08"
        season.events = [_blank_event(e) for e in calendar_for(2026, include_extensions=False)["events"]]
        season.teams = [{"id": str(i), "name": str(i), "region": "EU" if i < 20 else "AS"} for i in range(40)]
        season.ranked = lambda: list(season.teams)
        season.career = SimpleNamespace(exists=True, team_id="20", registered=[], incident_state={})
        event = next(ev for ev in season.events if ev.get("regional_only") and ev["region"] == "AS")
        field = season.field_for(event)
        self.assertEqual(event["size"], len(field))
        self.assertNotIn("20", {t["id"] for t in field})
        self.assertTrue(all(t["region"] == "AS" for t in field))


if __name__ == "__main__":
    unittest.main()
