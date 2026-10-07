extends Node
## Data-only fragments emit intents; they never submit commands or edit context.
const Pages = preload("res://scripts/device_pages.gd")
const Data = preload("res://scripts/device_page_data.gd")
var checks := 0
var failures: Array[String] = []
var intents: Array = []

func _ready() -> void: call_deferred("run")

func check(ok: bool, label: String) -> void:
	checks += 1
	if not ok: failures.append(label)

func button(parent: Node, text: String, callback: Callable, _mutation: bool = true) -> Button:
	var control := Button.new()
	control.text = text
	control.pressed.connect(callback)
	parent.add_child(control)
	return control

func phone_row(parent: Node, text: String, _subtitle: String, callback: Callable, _avatar: String = "", _icon: String = "", _pending: bool = false, _write: bool = false) -> Button:
	return button(parent, text, callback, false)

func run() -> void:
	if not "--no-service" in OS.get_cmdline_user_args(): get_tree().quit(2); return
	var root := get_tree().root
	var locale = root.get_node("Locale")
	var old_language: String = locale.language
	var context := {"inbox":[{"id":"invite", "kind":"invite", "evname":"Cup", "status":"open"}, {"kind":"news"}, {"kind":"top20"}]}
	var before := context.duplicate(true)
	check(Data.inbox(context).size() == 1, "news is not duplicated in either inbox")
	check(Data.days_in_month("2024-02") == 29 and Data.days_in_month("2100-02") == 28, "calendar leap years")
	check(Data.shift_month("2026-12", 1, "2026-01-01") == "2026-12", "calendar cannot cross season year")
	check(Data.mail_intent("accept", {"decision_pending":true}) == {"page":"stories"}, "contract continuation navigates without another accept")
	check(Data.mail_intent("accept", {"accept_action":"/arbitrary"}).is_empty(), "unknown mail action cannot send a command")
	var stale := {"id":"invite", "status":"open", "body":"full body"}
	var fresh := Data.current_mail([{"id":"invite", "status":"accepted"}], stale)
	check(fresh.status == "accepted" and fresh.body == "full body" and stale.status == "open", "refresh merges mail status without discarding full body or editing caller")
	for language in ["zh-CN", "en"]:
		locale.set_language(language, false)
		check(locale.message("growth.points", {"count":3}).contains("3"), "keyed message preserves count")
		check(not locale.message("mail.inbox").contains("mail.inbox"), "key resolves in both languages")
		for compact in [true, false]:
			var page = Pages.new()
			var host := VBoxContainer.new()
			root.add_child(host)
			var roster := {"data_provenance":{"roster_policy":"opening_complete", "roster_as_of":"2026-01-09"}}
			var roster_before := roster.duplicate(true)
			page.roster_date(host, roster, compact)
			check(host.get_child_count() == 1 and host.get_child(0).text.contains("2026-01-09"), "actual roster date on both devices and languages")
			check(roster == roster_before, "roster label is read-only")
			host.get_child(0).free()
			page.mail_action.connect(func(action, letter): intents.append([action, letter.id]))
			page.mail_content(host, context.inbox[0], compact, button)
			var accept: Button = host.get_child(1)
			accept.pressed.emit()
			check(intents.pop_back() == ["accept", "invite"], "mail emits same intent on both devices")
			check(context == before, "mail does not mutate its input")
			host.free()
			host = VBoxContainer.new()
			root.add_child(host)
			page.mail_selected.connect(func(letter): intents.append(letter.id))
			host.set_meta("phone_edge", compact)
			page.mail_list(host, context.inbox, compact, button, phone_row)
			check(not compact or host.get_child(0) is MarginContainer, "shared inbox preserves phone side padding")
			var mail_button: Button = host.find_child(("MailRow_" if compact else "ComputerMail_") + "invite", true, false)
			mail_button.pressed.emit()
			check(intents.pop_back() == "invite", "inbox selection carries stable mail ID")
			host.free()
			host = VBoxContainer.new()
			root.add_child(host)
			page.sleep_requested.connect(func(day): intents.append(day))
			page.calendar_controls(host, "2026-12-31", "2026-12-31", "2026-12", "", compact, button)
			var selected_sleep: Button = host.find_child("CalendarSleepSelected", true, false)
			selected_sleep.pressed.emit()
			check(intents.pop_back() == "2026-12-31", "sleep request uses selected date")
			var tomorrow_sleep: Button = host.find_child("CalendarSleepTomorrow", true, false)
			tomorrow_sleep.pressed.emit()
			check(intents.pop_back() == "2027-01-01", "tomorrow handles year boundary, service still owns calendar gate")
			check(not root.get_node("CareerBridge").busy, "rendering fragment and emitting intent do not submit a command")
			host.free()
			host = VBoxContainer.new()
			root.add_child(host)
			page.event_selected.connect(func(id): intents.append(id))
			page.calendar_events(host, [{"id":"oct", "name":"Cup", "date":"2026-10-09"}, {"id":"nov", "name":"Later", "date":"2026-11-01"}], "2026-10", compact, button, phone_row)
			var event_buttons: Array = host.find_children("*", "Button", true, false)
			check(event_buttons.size() == 1, "calendar lists only selected month")
			event_buttons[0].pressed.emit()
			check(intents.pop_back() == "oct", "calendar emits event ID without navigating host")
			host.free()
			var grid := GridContainer.new()
			root.add_child(grid)
			page.day_selected.connect(func(day): intents.append(day))
			page.calendar_grid(grid, "2026-10-05", "2026-10-09", "2026-10", compact, button)
			var past: Button = grid.find_child("CalendarDay_04", true, false)
			var next_day: Button = grid.find_child("CalendarDay_09", true, false)
			check(past.disabled and not next_day.disabled, "calendar disables past days on both devices")
			next_day.pressed.emit()
			check(intents.pop_back() == "2026-10-09", "calendar retains selected date identity")
			grid.free()
			host = VBoxContainer.new()
			root.add_child(host)
			page.match_selected.connect(func(id): intents.append(id))
			page.recent_matches(host, [{"id":"fixture-id", "team_a":"A", "team_b":"B", "series":[2,1], "date":"2026-10-05", "event":"Cup"}], compact, button)
			var match_button: Button = host.find_child("RecentMatch_fixture-id", true, false)
			match_button.pressed.emit()
			check(intents.pop_back() == "fixture-id", "match selection carries ID, not translated text")
			host.free()
	var personal := {"attributes":{"firepower":82.6, "sniping":100, "utility":null}, "growth_allowed":true}
	var rows := Data.growth_rows(personal, {"firepower":1}, 2)
	check(rows[0].value == 82.6 and rows[0].pending == 1 and rows[0].plus, "growth preserves decimals and staged points")
	check(not rows[1].plus and not rows[2].plus and not rows[2].measured, "cap and missing values cannot be spent")
	var original: String = locale._keyed_messages["mail.inbox"]["zh"]
	locale._keyed_messages["mail.inbox"]["zh"] = "改过的中文"
	locale.set_language("en", false)
	check(locale.message("mail.inbox") == "Inbox", "Chinese copy edit does not invalidate English ID")
	locale._keyed_messages["mail.inbox"]["zh"] = original
	locale.set_language(old_language, false)
	print("DEVICE_FRAGMENTS_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
