extends RefCounted
## Read-only projections used by both devices. No autoload writes or navigation.
const Fmt = preload("res://scripts/ui_format.gd")

const PHONE_PAGES := {"home":"page.home", "mail":"mail.title", "chat":"page.chat", "match":"page.match", "quick":"page.quick", "calendar":"calendar.title", "profile":"page.profile", "settings":"page.settings", "team":"page.team", "stories":"page.stories", "player":"page.player", "event":"page.event", "news":"page.news"}
const DESKTOP_PAGES := {"desktop":"page.desktop", "battle":"page.battle", "career_match":"page.career_match", "quick":"page.quick", "settings":"page.settings", "tactics":"page.tactics", "ladder":"page.ladder", "custom":"page.custom", "rts":"page.rts", "scrim":"page.scrim", "events":"page.events", "team":"page.team_details", "player":"page.player_details", "event":"page.event", "match":"page.match_report", "market":"page.market", "profile":"page.career", "mail":"mail.title", "calendar":"calendar.title", "operations":"page.operations", "transfers":"page.transfers", "news":"page.news", "management":"page.management", "training":"page.training", "assistance":"page.assistance", "rankings":"page.rankings", "workshop":"page.workshop", "start":"page.start", "appearance":"page.appearance", "saves":"page.saves"}

static func page_titles(compact: bool) -> Dictionary:
	var titles := {}
	var keys: Dictionary = PHONE_PAGES if compact else DESKTOP_PAGES
	for page in keys: titles[page] = Locale.source(keys[page])
	return titles

static func role_labels() -> Dictionary:
	var roles := {}
	for role in ["rifle", "awp", "entry", "lurk", "igl", "support"]:
		roles[role] = Locale.source("role." + role)
	roles["lurker"] = roles.lurk
	return roles

static func apps(compact: bool) -> Array:
	var result: Array = []
	var titles := page_titles(compact)
	if compact:
		for id in ["mail", "chat", "match", "calendar", "profile", "settings"]:
			result.append({"id":id, "name":titles[id]})
	else:
		for item in [["battle", "match"], ["events", "trophy"], ["market", "clipboard"], ["operations", "finance"], ["transfers", "transfers"], ["news", "news"], ["profile", "profile"], ["mail", "mail"], ["calendar", "calendar"]]:
			result.append({"page":item[0], "label":titles[item[0]], "icon":item[1]})
	return result

static func current_mail(inbox_rows: Array, selected: Dictionary) -> Dictionary:
	var letter := selected.duplicate(true)
	for fresh in inbox_rows:
		if str(fresh.get("id", "")) == str(letter.get("id", "")):
			letter.merge(fresh, true)
			break
	return letter

static func inbox(context: Dictionary) -> Array:
	var rows: Array = []
	for row in context.get("inbox", []):
		if row.get("kind") not in ["news", "awards", "top20"] and not (row.get("kind") == "notification" and row.has("publication_key")):
			rows.append(row)
	return rows

static func mail_subject(row: Dictionary) -> String:
	var subject := Locale.field(row, "title")
	if not subject.is_empty(): return subject
	if row.get("kind") == "contract": return Locale.message("mail.join_subject", {"team":row.get("team", "")})
	return str(row.get("evname", Locale.message("mail.title")))

static func mail_sender(row: Dictionary) -> String:
	return Locale.message("mail.coach") if row.get("kind") == "invite" else str(row.get("sender", row.get("team", Locale.message("mail.club"))))

static func mail_status(status: String) -> String:
	return Locale.message("mail." + status) if status in ["open", "accepted", "declined", "read", "filed", "expired"] else status

static func mail_intent(action: String, row: Dictionary) -> Dictionary:
	if action == "accept" and row.get("decision_pending", false): return {"page":"stories"}
	var path := str(row.get(action + "_action", "/api/3d/mail/" + action))
	if path not in ["/api/3d/mail/accept", "/api/3d/mail/decline"]: return {}
	return {"path":path, "body":{"id":str(row.get("id", ""))}}

static func days_in_month(value: String) -> int:
	var year := int(value.left(4))
	var month := int(value.right(2))
	if month == 2: return 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28
	return 30 if month in [4, 6, 9, 11] else 31

static func shift_month(value: String, amount: int, current: String) -> String:
	var year := int(value.left(4))
	var number := int(value.right(2)) + amount
	if number < 1: year -= 1; number = 12
	elif number > 12: year += 1; number = 1
	return "%04d-%02d" % [year, number] if year == int(current.left(4)) else value

static func growth_rows(personal: Dictionary, draft: Dictionary, remaining: int) -> Array:
	var attributes: Dictionary = personal.get("attributes", {})
	var rows: Array = []
	for axis in personal.get("axes", attributes.keys()):
		var measured := Fmt.is_number(attributes.get(axis))
		var value := float(attributes[axis]) if measured else 0.0
		var pending := int(draft.get(axis, 0))
		var allowed := bool(personal.get("growth_allowed", false)) and measured
		rows.append({"axis":str(axis), "label":str(personal.get("axis_labels", {}).get(axis, axis)),
			"value":value, "pending":pending, "measured":measured,
			"minus":allowed and pending > 0, "plus":allowed and remaining > 0 and value + pending < 100})
	return rows

static func match_row(game: Dictionary) -> Dictionary:
	var series = game.get("series", [])
	var score := "%s : %s" % [series[0], series[1]] if series is Array and series.size() == 2 else str(series) if series is String else ""
	return {"id":str(game.get("id", "")), "title":"%s  %s  %s" % [game.get("team_a", ""), score, game.get("team_b", "")],
		"subtitle":"%s · %s" % [game.get("date", ""), game.get("event", "")]}
