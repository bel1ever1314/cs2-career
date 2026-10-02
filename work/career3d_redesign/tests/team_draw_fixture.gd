extends RefCounted
## Explicitly synthetic UI fixtures, never player fitting data or live saves.
const AXES := [{"id":"firepower", "name":"火力"}, {"id":"entrying", "name":"突破"}, {"id":"trading", "name":"补枪"}, {"id":"opening", "name":"首杀"}, {"id":"clutching", "name":"残局"}, {"id":"sniping", "name":"狙击"}, {"id":"utility", "name":"道具"}]

static func upgrade_options(options: Dictionary) -> Dictionary:
	var result := options.duplicate(true)
	result["attribute_draw"] = {"schema_version":2, "selection_scope":"one_attribute_per_team_draw", "max_draws":10, "axes":AXES.duplicate(true), "preview_teams":[]}
	for team in result.get("teams", []):
		result.attribute_draw.preview_teams.append({"source_team":team.name, "vrs_points":1500, "band_label":"精英", "band_color":"9b75d1"})
	return result

static func empty_session(era: String = "2026") -> Dictionary:
	var rows: Array = []
	var unfilled: Array = []
	for axis in AXES:
		rows.append({"id":axis.id, "name":axis.name, "selected_player_id":null, "selected_value":null, "selected_draw_id":null, "selection":null})
		unfilled.append(axis.id)
	return {"schema_version":2, "selection_scope":"one_attribute_per_team_draw", "draft_id":"fixture-complete-" + era, "era":era, "revision":0, "max_draws":10, "remaining":10, "attempts_used":0, "complete":false, "team_draws":[], "pending_draw_id":null, "axes":rows, "unfilled_axes":unfilled, "selectable_axes":[], "can_roll":true}

static func draw(session: Dictionary, team: Dictionary, index: int = 1) -> Dictionary:
	var players: Array = []
	for row in team.players:
		var stats := {}
		for axis in AXES: stats[axis.id] = 70 + players.size() * 2
		players.append({"player_id":row.player_id, "source_player_id":row.player_id, "source_player":row.name, "source_team":team.name, "source_team_id":team.id, "stats":stats})
	var result := {"draw_id":"fixture-draw-" + str(index), "attempt":index, "team_id":team.id, "source_team":team.name, "source_team_id":team.id, "source_era":session.era, "vrs_points":1500, "vrs_rank":8, "band":"elite", "band_label":"精英", "band_color":"9b75d1", "players":players, "selection":null}
	session.team_draws.append(result)
	session.pending_draw_id = result.draw_id
	session.attempts_used = index
	session.remaining = 10 - index
	session.can_roll = false
	session.selectable_axes = []
	for axis in AXES: session.selectable_axes.append(axis.id)
	session.revision += 1
	return result

static func choose(session: Dictionary, draw_row: Dictionary, axis_id: String, player_index: int = 0) -> void:
	var player: Dictionary = draw_row.players[player_index]
	var axis_name := axis_id
	for axis in AXES:
		if axis.id == axis_id: axis_name = axis.name
	var selection := {"axis":axis_id, "axis_name":axis_name, "player_id":player.player_id, "source_player_id":player.player_id, "source_player":player.source_player, "source_team":draw_row.source_team, "value":player.stats[axis_id], "draw_id":draw_row.draw_id}
	draw_row.selection = selection
	for axis in session.axes:
		if axis.id == axis_id:
			axis.merge({"selected_player_id":player.player_id, "selected_value":selection.value, "selected_draw_id":draw_row.draw_id, "selection":selection}, true)
	session.unfilled_axes.erase(axis_id)
	session.pending_draw_id = null
	session.selectable_axes = []
	session.can_roll = session.remaining > 0
	session.complete = session.unfilled_axes.is_empty()
	session.revision += 1

static func completed(era: String = "2026") -> Dictionary:
	var session := empty_session(era)
	var players: Array = []
	for index in range(5): players.append({"player_id":"fixture-player-" + str(index), "name":"Fixture Player " + str(index)})
	var team := {"id":"fixture-team", "name":"Fixture Team", "players":players}
	for index in range(7):
		var drawn := draw(session, team, index + 1)
		choose(session, drawn, AXES[index].id)
	return session
