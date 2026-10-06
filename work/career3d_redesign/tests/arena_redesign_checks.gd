extends RefCounted
## Additional checks for the new crowd, lighting hierarchy and cue timing.

func evaluate(app) -> Array[Dictionary]:
	var checks: Array[Dictionary] = []
	var crowd: Dictionary = app.crowd.diagnostic_snapshot()
	var arena: Dictionary = app.atmosphere.diagnostic_snapshot()
	checks.append({"ok": crowd["species"] == "chicken" and crowd["seated"] > 3000, "label": "all original arena spectators replaced by seated chickens"})
	checks.append({"ok": crowd["legacy_removed"] >= crowd["seated"] and crowd["legacy_removed"] - crowd["seated"] < 40, "label": "every combined legacy bear and chair was removed (none left floating)"})
	checks.append({"ok": app.model.find_children("Crowd*", "MeshInstance3D", true, false).is_empty(), "label": "legacy bear meshes no longer remain in scene"})
	checks.append({"ok": is_equal_approx(crowd["body_bottom_m"], crowd["cushion_top_m"]), "label": "seated body rests on cushion, not chair back"})
	checks.append({"ok": crowd["foot_sole_m"] >= 0.0 and crowd["foot_sole_m"] < 0.025, "label": "feet contact original terrace level within 25 mm"})
	checks.append({"ok": crowd["grounded"] == crowd["seated"] and crowd["max_floor_error_m"] < 0.0001, "label": "all actual foot soles align with original floor and terrace tops"})
	checks.append({"ok": crowd["animated"] > 0 and crowd["animated"] <= 56 and crowd["far_static"] > 3000, "label": "near spectators animate, distant terraces stay static"})
	checks.append({"ok": crowd["batches"] <= 5 and crowd["spectator_physics"] == 0, "label": "whole crowd uses five shared batches and no spectator physics"})
	checks.append({"ok": arena["face_keys"] == 2 and arena["stage_spots"] >= 5, "label": "stage and player faces have dedicated key lighting"})
	checks.append({"ok": arena["screens"] == 3 and not arena["strobe"], "label": "three entrance graphics with no strobe"})
	checks.append({"ok": arena["entrance_bpm"] == 128.0 and arena["cue"] == "major_final", "label": "free visit choreography uses the new 128 BPM opener"})
	checks.append({"ok": absf(arena["entrance_duration"] - float(app.atmosphere.cue["length"])) < .1, "label": "new entrance cue matches the authored duration"})
	var drop: float = app.atmosphere.cue["drop"]
	var on_beat: Dictionary = app.atmosphere.beat_state(drop)
	var between: Dictionary = app.atmosphere.beat_state(drop + 0.5 * 60.0 / 128.0)
	var settled: Dictionary = app.atmosphere.beat_state(float(app.atmosphere.cue["length"]))
	checks.append({"ok": on_beat["pulse"] > 0.95 and between["pulse"] < 0.01, "label": "soft accent follows beat then releases"})
	checks.append({"ok": settled["phrase"] == 0.0 and settled["pulse"] == 0.0, "label": "entrance lighting settles after one phrase"})
	var level_ok := true
	for house in app.atmosphere.bowl_lights:
		if house.position.z < 50.0 and house.light_energy > 0.5:
			level_ok = false
	checks.append({"ok": level_ok and app.atmosphere.stage_lights[0].light_energy >= 7.0, "label": "bright stage remains above dim audience lighting"})
	return checks
