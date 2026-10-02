extends RefCounted
## Frozen display-only identity join. No names, opponents or career results invented.

static func plan(visit: Dictionary) -> Dictionary:
	var venue: Dictionary = visit.get("venue", {})
	var team_a := str(venue.get("team_a", ""))
	var team_b := str(venue.get("team_b", ""))
	var own_team := str(venue.get("own_team", venue.get("your_team", "")))
	var human_id := str(venue.get("human_id", ""))
	var a: Array = venue.get("players_a", venue.get("roster_a", []))
	var b: Array = venue.get("players_b", venue.get("roster_b", []))
	var grouped: Variant = venue.get("rosters", {})
	if grouped is Dictionary:
		if a.is_empty(): a = grouped.get(team_a, [])
		if b.is_empty(): b = grouped.get(team_b, [])
	if a.size() != 5 or b.size() != 5 or human_id.is_empty() or team_a.is_empty() or team_b.is_empty() or own_team not in [team_a, team_b] or team_a == team_b: return {}
	var seen: Dictionary = {}
	var human_count := 0
	for rows in [a, b]:
		for row in rows:
			if not row is Dictionary: return {}
			var id := identity(row)
			if id.is_empty() or seen.has(id) or str(row.get("name", "")).strip_edges().is_empty(): return {}
			seen[id] = true
			if id == human_id: human_count += 1
	if human_count != 1: return {}
	var own: Array = (a if own_team == team_a else b).duplicate(true)
	var other: Array = (b if own_team == team_a else a).duplicate(true)
	var human_index := -1
	for i in range(own.size()):
		if identity(own[i]) == human_id: human_index = i
	if human_index < 0: return {}
	# Reserve the centre seat for the user; this only changes presentation order.
	var human: Dictionary = own.pop_at(human_index)
	own.insert(2, human)
	return {"own":own, "opponents":other, "own_team":own_team,
		"opponent_team":team_b if own_team == team_a else team_a,
		"human_id":human_id, "match_id":str(visit.get("match_id", ""))}

static func identity(row: Dictionary) -> String:
	var id: Variant=row.get("player_id",row.get("id",""))
	return str(id) if id!=null else ""
