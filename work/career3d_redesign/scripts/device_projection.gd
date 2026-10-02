extends RefCounted
## Stable page projections keep periodic connection probes from repainting devices.
static func signature(page: String, context: Dictionary) -> String:
	var fields: Array = {
		"home":["date", "player", "inbox", "stories", "nextmatch"],
		"desktop":["date", "player", "attr_points", "inbox"],
		"battle":["nextmatch", "match_preflight", "ladder", "quick", "custom"],
		"career_match":["nextmatch", "match_preflight", "recent_matches", "player", "stories"],
		"quick":["quick", "nextmatch", "stories", "date"],
		"settings":["settings"], "tactics":[], "start":[], "appearance":[], "saves":[],
		"management":[], "training":[], "assistance":[], "rankings":["date"], "workshop":[],
		"mail":["inbox", "stories"], "chat":["player", "team", "contacts", "stories"],
		"ladder":["ladder", "player"], "custom":["custom", "ladder"], "scrim":["scrims", "date"],
		"match":["nextmatch", "recent_matches", "calendar_events"],
		"calendar":["date", "calendar_events", "nextmatch", "quick"],
		"profile":["player", "personal", "attr_points", "money", "team", "recent_matches"],
		"market":["skins", "money"], "operations":["operations", "finance"],
		"transfers":["transfers", "player_transfers"], "news":["news"],
		"stories":["stories"], "events":["teams", "calendar_events", "recent_matches"]
	}.get(page, ["player", "team", "date"])
	var projection := {}
	for key in fields:
		projection[key] = context.get(key)
	return JSON.stringify(projection)
