extends RefCounted
## Shared fragments: input data + intents. Button factory only supplies device
## styling/busy registration; fragments never read or mutate their host.
signal day_selected(day: String)
signal growth_adjusted(axis: String, delta: int)
signal growth_confirmed
signal growth_cleared
signal mail_action(action: String, letter: Dictionary)
signal match_selected(id: String)
signal mail_selected(letter: Dictionary)
signal month_shifted(amount: int)
signal sleep_requested(day: String)
signal event_selected(id: String)
const Data = preload("res://scripts/device_page_data.gd")
const PhoneUI = preload("res://scripts/phone_ui.gd")
const DesktopUI = preload("res://scripts/computer_ui.gd")
const Kit = preload("res://scripts/ui_kit.gd")
const Fmt = preload("res://scripts/ui_format.gd")

func mail_list(parent: Node, rows: Array, compact: bool, button: Callable, phone_row: Callable = Callable()) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var list := VBoxContainer.new()
	list.set_meta("page_fragment", self)
	PhoneUI.inset(parent, list) if compact else parent.add_child(list)
	if compact:
		ui.label(list, Locale.message("mail.inbox"), 12, ui.MUTED)
		ui.space(list, 4)
	else:
		ui.label(list, Locale.message("mail.title"), 25)
		var waiting := 0
		for letter in rows:
			if letter.get("status") == "open": waiting += 1
		Kit.section(list, ui, Locale.message("mail.inbox"), Locale.message("mail.waiting", {"count":waiting}) if waiting > 0 else Locale.message("mail.done"), 15)
	if rows.is_empty():
		Kit.empty_state(list, ui, "mail", Locale.message("mail.empty"), Locale.message("mail.empty_hint"))
	for letter in rows:
		var subject := Data.mail_subject(letter)
		var sender := Data.mail_sender(letter)
		var status := str(letter.get("status", ""))
		var row: Button
		if compact:
			row = phone_row.call(list, subject, "%s · %s · %s" % [sender, letter.get("date", ""), Data.mail_status(status)], func(): mail_selected.emit(letter), "", "mail", status == "open")
			row.add_to_group("phone_mail_row")
		else:
			row = button.call(list, subject, func(): mail_selected.emit(letter), false)
			var tone: String = {"open":"amber", "expired":"gray", "accepted":"green", "declined":"gray"}.get(status, "gray")
			Kit.rich_row(row, ui, subject, sender + " · " + str(letter.get("date", "")), "", Data.mail_status(status), tone, "mail", "", ui.AMBER if status == "open" else Color.TRANSPARENT)
		row.name = ("MailRow_" if compact else "ComputerMail_") + str(letter.get("id", "")).validate_node_name()
		row.set_meta("focus_key", "mail:" + str(letter.get("id", "")))

func calendar_controls(parent: Node, current: String, selected: String, month: String, pending: String, compact: bool, button: Callable) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var box := VBoxContainer.new()
	box.set_meta("page_fragment", self)
	PhoneUI.inset(parent, box) if compact else parent.add_child(box)
	if not compact:
		ui.label(box, Locale.message("calendar.title"), 25)
		ui.label(box, Locale.message("calendar.hint"), 14, ui.MUTED)
	var header := HBoxContainer.new()
	ui.inset(box, header) if compact else box.add_child(header)
	for amount in [-1, 1]:
		var arrow: Button = button.call(header, "‹" if amount < 0 else "›", func(): month_shifted.emit(amount), false)
		ui.transparent(ui.compact(arrow))
		arrow.custom_minimum_size = Vector2(34, 34)
		if amount < 0:
			var caption: Label = ui.label(header, month, 18)
			caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			caption.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
			caption.autowrap_mode = TextServer.AUTOWRAP_OFF
	var columns: BoxContainer = VBoxContainer.new() if compact else HBoxContainer.new()
	columns.add_theme_constant_override("separation", 12 if compact else 32)
	box.add_child(columns)
	var grid := GridContainer.new()
	grid.columns = 7
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 3 if compact else 5)
	grid.add_theme_constant_override("v_separation", 3 if compact else 5)
	columns.add_child(grid)
	calendar_grid(grid, current, selected, month, compact, button)
	var actions := VBoxContainer.new()
	actions.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	actions.add_theme_constant_override("separation", 10 if compact else 13)
	columns.add_child(actions)
	ui.label(actions, Locale.message("calendar.wake", {"day":selected}), 14 if compact else 19)
	var sleep_button: Button = button.call(actions, Locale.message("calendar.sleep_selected"), func(): sleep_requested.emit(selected))
	sleep_button.name = "CalendarSleepSelected"
	DesktopUI.primary(sleep_button)
	# Calendar date calculation is deterministic and is not a bridge command.
	var tomorrow := Time.get_datetime_string_from_unix_time(Time.get_unix_time_from_datetime_string(current + "T00:00:00") + 86400).left(10)
	var next_day: Button = button.call(actions, Locale.message("calendar.sleep_tomorrow"), func(): sleep_requested.emit(tomorrow))
	next_day.name = "CalendarSleepTomorrow"
	if not pending.is_empty() and pending > current:
		button.call(actions, Locale.message("calendar.resume", {"day":pending}), func(): sleep_requested.emit(pending))
	ui.label(actions, Locale.message("calendar.pause_hint"), 12, ui.MUTED)

func calendar_events(parent: Node, events: Array, month: String, compact: bool, button: Callable, phone_row: Callable = Callable()) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var box := VBoxContainer.new()
	box.set_meta("page_fragment", self)
	PhoneUI.inset(parent, box) if compact else parent.add_child(box)
	if not compact: Kit.section(box, ui, Locale.message("calendar.month_events"), "", 18)
	var count := 0
	for item in events:
		if not str(item.get("date", "")).begins_with(month): continue
		count += 1
		var id := str(item.get("id", ""))
		var registered := Locale.message("calendar.registered") if item.get("registered", false) else ""
		if compact:
			phone_row.call(box, str(item.get("name", "")), str(item.get("date", "")) + (" · " + registered if not registered.is_empty() else ""), func(): event_selected.emit(id), "", "calendar", false, true)
		else:
			var row: Button = button.call(box, str(item.get("name", "")), func(): event_selected.emit(id), false)
			var tier := Kit.event_tier(str(item.get("type", "")))
			Kit.rich_row(row, ui, str(item.get("name", "")), Locale.message("calendar.starts", {"day":Kit.short_date(str(item.get("date", "")))}), registered, str(tier[0]), str(tier[1]), "calendar", "", ui.GREEN if item.get("registered", false) else Color.TRANSPARENT)
	if count == 0 and not compact: Kit.empty_state(box, ui, "calendar", Locale.message("calendar.no_events"), "")

func player_summary(parent: Node, summary: Dictionary, compact: bool) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var stats: Node = ui.card(parent) if compact else parent
	ui.label(stats, Locale.message("profile.summary", {"rating":Fmt.num(summary.get("rating"), 2), "adr":Fmt.num(summary.get("adr"), 1), "kast":Fmt.percent_fixed(summary.get("kast")), "maps":summary.get("maps", 0), "rounds":summary.get("rounds", 0)}), 14 if compact else 19)
	if int(summary.get("maps", 0)) > 0:
		ui.label(stats, Locale.message("profile.kda", {"k":summary.get("k", "—"), "d":summary.get("d", "—"), "a":summary.get("a", "—")}), 14)
		if not summary.get("data_complete", false): ui.label(stats, Locale.message("profile.partial_stats"), 12, ui.MUTED)
	else: ui.label(stats, Locale.message("profile.no_stats"), 12, ui.MUTED)

func player_honours(parent: Node, detail: Dictionary, compact: bool) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var honours: Dictionary = detail.get("honours", {})
	if compact: ui.label(parent, Locale.message("profile.honours"), 16)
	for group in ["titles", "mvp", "evp", "top20"]:
		var rows: Array = honours.get(group, [])
		var title: String = Locale.message("profile.title") if group == "titles" else Locale.message("profile.top20") if group == "top20" else str(group).to_upper()
		ui.label(parent, "%s · %d" % [title, int(honours.get("counts", {}).get(group, rows.size()))], 14 if compact else 19)
		for item in rows:
			if not item is Dictionary: continue
			var caption := str(item.get("date", "")) + " · " + str(item.get("event", item.get("name", item.get("short", ""))))
			if group == "top20":
				caption = Locale.message("profile.top20_record", {"year":item.get("year", ""), "rank":item.get("rank", ""), "rating":Fmt.num(item.get("rating"), 2)})
			elif item.get("rating") != null: caption += " · Rating " + Fmt.num(item.rating, 2)
			ui.label(parent, caption, 12 if compact else 14, ui.MUTED)
		if rows.is_empty() and not compact: ui.label(parent, Locale.message("profile.no_honours"), 13, ui.MUTED)
	if not str(detail.get("honours_notice", "")).is_empty(): ui.label(parent, str(detail.honours_notice), 12, ui.MUTED)

func calendar_grid(grid: GridContainer, current: String, selected: String, month: String, compact: bool, button: Callable) -> void:
	var ui = PhoneUI if compact else DesktopUI
	grid.set_meta("page_fragment", self)
	for key in ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]:
		ui.label(grid, Locale.message("calendar." + key), 12, ui.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var first := Time.get_datetime_dict_from_datetime_string(month + "-01T00:00:00", true)
	for _blank in range(int(first.get("weekday", 0))): ui.label(grid, " ")
	for day in range(1, Data.days_in_month(month) + 1):
		var stamp := "%s-%02d" % [month, day]
		var cell: Button = button.call(grid, str(day), func(): day_selected.emit(stamp), false)
		cell.name = "CalendarDay_%02d" % day
		ui.transparent(cell)
		cell.custom_minimum_size = Vector2(34, 34) if compact else Vector2(42, 40)
		if compact: cell.add_theme_font_size_override("font_size", 12)
		cell.disabled = stamp < current or stamp.left(4) != current.left(4)
		if stamp == selected: cell.add_theme_stylebox_override("normal", ui.style(ui.MINT, 4 if compact else 5, 8))

func growth(parent: Node, personal: Dictionary, draft: Dictionary, remaining: int, compact: bool, button: Callable, busy: bool) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var box := VBoxContainer.new()
	box.set_meta("page_fragment", self)
	PhoneUI.inset(parent, box) if compact else parent.add_child(box)
	ui.label(box, Locale.message("growth.points", {"count":remaining}), 17 if compact else 22, ui.GREEN)
	if not str(personal.get("growth_reason", "")).is_empty(): ui.label(box, str(personal.growth_reason), 12, ui.MUTED)
	for data in Data.growth_rows(personal, draft, remaining):
		var row := HBoxContainer.new()
		row.name = ("PhoneAttribute_" if compact else "ComputerAttribute_") + data.axis
		row.add_theme_constant_override("separation", 5 if compact else 12)
		box.add_child(row)
		var caption: Label = ui.label(row, data.label, 13 if compact else 14)
		if compact: caption.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		else: caption.custom_minimum_size.x = 86
		if not compact:
			var meter := ProgressBar.new()
			meter.size_flags_horizontal = Control.SIZE_EXPAND_FILL
			meter.custom_minimum_size = Vector2(180, 8)
			meter.size_flags_vertical = Control.SIZE_SHRINK_CENTER
			meter.show_percentage = false
			meter.value = data.value + data.pending
			meter.add_theme_stylebox_override("background", ui.style(Color("e6e3d6"), 0, 4))
			meter.add_theme_stylebox_override("fill", ui.style(ui.GREEN if data.pending == 0 else ui.AMBER, 0, 4))
			row.add_child(meter)
		var value: Label = ui.label(row, Fmt.num(data.value, 1) + (" +%d" % data.pending if data.pending > 0 else "") if data.measured else "—", 14)
		value.name = "AttributeValue"
		value.custom_minimum_size.x = 58 if compact else 76
		value.size_flags_horizontal = Control.SIZE_SHRINK_END
		for delta in [-1, 1]:
			var adjust: Button = button.call(row, "−" if delta == -1 else "+", func(): growth_adjusted.emit(data.axis, delta))
			adjust.name = ("Growth" if compact else "Attribute") + ("Minus_" if delta == -1 else "Plus_") + data.axis
			ui.compact(adjust)
			adjust.custom_minimum_size = Vector2(34, 34 if compact else 30)
			adjust.disabled = not data.minus if delta == -1 else not data.plus
			adjust.set_meta("career_gate_disabled", adjust.disabled)
	var actions: BoxContainer = VBoxContainer.new() if compact else HBoxContainer.new()
	box.add_child(actions)
	var confirm: Button = button.call(actions, Locale.message("growth.commit"), func(): growth_confirmed.emit())
	confirm.name = "GrowthCommit" if compact else "ComputerGrowthCommit"
	DesktopUI.primary(confirm)
	confirm.disabled = draft.is_empty() or not personal.get("growth_allowed", false)
	confirm.set_meta("career_gate_disabled", confirm.disabled)
	var clear: Button = button.call(actions, Locale.message("growth.clear"), func(): growth_cleared.emit(), false)
	clear.disabled = draft.is_empty() or busy
	ui.label(box, Locale.message("growth.shared_hint"), 12, ui.MUTED)

func mail_content(parent: Node, letter: Dictionary, compact: bool, button: Callable) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var paper: VBoxContainer = ui.card(parent)
	paper.set_meta("page_fragment", self)
	ui.label(paper, Data.mail_subject(letter), 16 if compact else 20)
	ui.label(paper, "%s · %s" % [letter.get("date", ""), Data.mail_status(str(letter.get("status", "")))], 12, ui.MUTED)
	if letter.get("kind") == "invite": ui.label(paper, Locale.message("mail.invite_hint"), 14)
	if not str(letter.get("body", "")).is_empty(): ui.label(paper, Locale.field(letter, "body"), 14 if compact else 15)
	if not str(letter.get("evname", "")).is_empty():
		var raw = letter.get("dates", [])
		var dates := "、".join(PackedStringArray(raw)) if raw is Array else str(raw)
		ui.label(paper, str(letter.evname) + "\n" + dates, 14)
	ui.label(paper, "—— " + Data.mail_sender(letter), 12, ui.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
	if letter.get("status") != "open": return
	var labels: Array = []
	if letter.get("kind") == "invite": labels = ["mail.enter", "mail.skip"]
	elif letter.get("kind") == "contract":
		ui.label(paper, Locale.message("mail.contract_hint"), 12, ui.MUTED)
		labels = ["mail.join_continue" if letter.get("decision_pending", false) else "mail.join_view", "mail.decline"]
	elif not str(letter.get("accept_action", "")).is_empty(): labels = ["mail.accept", "mail.decline"]
	for index in range(labels.size()):
		var action := "accept" if index == 0 else "decline"
		var control: Button = button.call(parent, Locale.message(labels[index]), func(): mail_action.emit(action, letter))
		if index == 0: DesktopUI.primary(control)

func recent_matches(parent: Node, records: Array, compact: bool, button: Callable) -> void:
	var ui = PhoneUI if compact else DesktopUI
	var list := VBoxContainer.new()
	list.set_meta("page_fragment", self)
	PhoneUI.inset(parent, list) if compact else parent.add_child(list)
	if records.is_empty(): ui.label(list, Locale.message("matches.empty"), 12 if compact else 14, ui.MUTED)
	for game in records:
		var data := Data.match_row(game)
		var row: Button = button.call(list, data.title, func(): match_selected.emit(data.id), false)
		row.name = "RecentMatch_" + data.id.validate_node_name()
		Kit.rich_row(row, ui, data.title, data.subtitle, "", "", "gray", "match")
