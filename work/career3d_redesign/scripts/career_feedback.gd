extends CanvasLayer
## Frozen results only. Presentation never rolls a match or chooses an award.
const UI = preload("res://scripts/computer_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const Trophy = preload("res://scripts/career_trophy.gd")
const ChampionCeremony = preload("res://scripts/venue_champion_ceremony.gd")
const CeremonyAudio = preload("res://scripts/ceremony_audio.gd")
const ACK_PATH := "/api/3d/feedback/ack"
var queue: Array[Dictionary] = []
var seen: Dictionary = {}
var map_sounds: Dictionary = {}
var entry: Dictionary = {}
var overlay: Control
var sheet: PanelContainer
var body: VBoxContainer
var status: Label
var actions: Array[Button] = []
var acknowledgements_pending := false
var visit_after_ack := false
var command_sender: Callable
var sound_player: AudioStreamPlayer
var audio_cache: Dictionary = {}
var last_sound := ""
var sound_count := 0
var active_career := ""
var flight: Tween
var venue_results: Dictionary = {}
var champion_seen: Dictionary = {}
var champion_ceremony: CanvasLayer
var championship_sound_played := false
# Top20 is sealed when it arrives: an invitation to the ceremony, or a staged
# reveal here from #20 to #1. Names are never listed up front.
var top20_rows: Array[Dictionary] = []
var top20_name_labels: Dictionary = {}
var top20_team_labels: Dictionary = {}
var top20_cards: Dictionary = {}
var reveal_queue: Array[int] = []
var reveal_clock := 0.0
var revealing := false
var reveal_done := false
var reveal_button: Button

func reset_for_loaded_career() -> void:
	queue.clear()
	seen.clear()
	map_sounds.clear()
	venue_results.clear()
	champion_seen.clear()
	acknowledgements_pending = false
	active_career = ""
	if is_instance_valid(sound_player): sound_player.stop()
	_release()

func _ready() -> void:
	layer = 35
	sound_player = AudioStreamPlayer.new()
	add_child(sound_player)
	CareerBridge.changed.connect(ingest)
	CareerBridge.command_finished.connect(_finished)
	get_viewport().size_changed.connect(_layout)
	set_process(true)

func ingest() -> void:
	var identity := str(CareerBridge.context.get("player", {}).get("id", ""))
	if not active_career.is_empty() and identity != active_career:
		queue.clear(); seen.clear(); map_sounds.clear()
		venue_results.clear(); champion_seen.clear()
		if not entry.is_empty(): _release()
	active_career = identity
	var feed: Dictionary = CareerBridge.context.get("feedback", {})
	for row in feed.get("items", []):
		if not row is Dictionary: continue
		var id := str(row.get("id", ""))
		if id.is_empty() or seen.has(id): continue
		seen[id] = true
		queue.append(row.duplicate(true))

func _process(delta: float) -> void:
	if entry.is_empty() and not queue.is_empty() and can_present():
		present(queue.pop_front())
	_tick_reveal(delta)

func can_present() -> bool:
	if CareerBridge.sleeping: return false
	if CareerBridge.busy or Travel.busy or CareerBridge._has_pending_match(): return false
	if Computer.screen.visible and Computer.active_page in ["start", "appearance"]: return false
	if Computer.match_center.is_presenting(): return false
	if is_instance_valid(Computer.rts_room.session): return false
	# A choice remains a choice. The newspaper does not answer unrelated stories.
	var stories: Array = CareerBridge.context.get("stories", [])
	if not stories.is_empty() and not stories[0].get("choices", []).is_empty(): return false
	return true

func present(value: Dictionary) -> void:
	if not entry.is_empty() or value.is_empty(): return
	entry = value.duplicate(true)
	# Opening feedback invokes the venue's before_phone hook, which leaves
	# the match seat. Freeze an older final's attendance before that transition.
	var celebration := championship_plan(entry)
	CareerBridge.feedback_active = true
	UI.device_open(self, "feedback")
	championship_sound_played = false
	var ident := str(entry.get("id", ""))
	if not celebration.is_empty() and not champion_seen.has(ident):
		champion_seen[ident] = true
		champion_ceremony = ChampionCeremony.new()
		champion_ceremony.name = "VenueChampionCeremony"
		add_child(champion_ceremony)
		champion_ceremony.lift_started.connect(func(): championship_sound_played = true; play_sound("champion"))
		champion_ceremony.finished.connect(_championship_finished)
		if champion_ceremony.start(celebration): return
		champion_ceremony.queue_free()
	_show_newspaper()

func remember_venue_result(snapshot: Dictionary, preflight: Dictionary) -> void:
	var scene := get_tree().current_scene
	if scene == null or scene.scene_file_path not in ["res://lan.tscn", "res://major_walk.tscn"]: return
	var id := str(snapshot.get("match_id", snapshot.get("id", "")))
	if not scene.has_method("match_seated") or not bool(scene.match_seated(id)): return
	if not bool(snapshot.get("played", false)): return
	var value: Variant = scene.get("roster_plan")
	if not value is Dictionary or value.is_empty(): return
	var venue: Dictionary = preflight.get("venue", {})
	var event_id := str(preflight.get("identity", {}).get("event_id", venue.get("event_id", "")))
	if event_id.is_empty() or str(preflight.get("stage", "")) != "GF": return
	venue_results[event_id] = {"personal":true, "destination":"lan" if scene.scene_file_path == "res://lan.tscn" else "major",
		"stage":"GF", "event_id":event_id, "roster":value.duplicate(true), "result":snapshot.duplicate(true),
		"appearance":CareerBridge.context.get("avatar", {}).get("appearance", {}).duplicate(true)}

func championship_plan(award: Dictionary) -> Dictionary:
	var event_id := str(award.get("event_id", ""))
	if not venue_results.has(event_id):
		# A final already underway before this version was installed still has
		# its frozen venue, roster and saved result. No new local marker is required.
		remember_venue_result(Computer.match_center.last_result, Computer.match_center.preflight)
	return ChampionCeremony.plan(award, venue_results.get(event_id, {}))

func _championship_finished() -> void:
	if is_instance_valid(champion_ceremony): champion_ceremony.queue_free()
	champion_ceremony = null
	if not entry.is_empty(): _show_newspaper()

func _show_newspaper() -> void:
	overlay = Control.new()
	overlay.name = "CareerHonoursFeedback"
	overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(overlay)
	var shade := ColorRect.new()
	shade.color = Color("131d18", .72)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	overlay.add_child(shade)
	sheet = PanelContainer.new()
	sheet.name = "CareerNewspaper"
	sheet.add_theme_stylebox_override("panel", UI.style(Color("f8f3e3"), 24, 5, Color("c7bb9e")))
	overlay.add_child(sheet)
	var scroll := ScrollContainer.new()
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	sheet.add_child(scroll)
	body = VBoxContainer.new()
	body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	body.add_theme_constant_override("separation", 10)
	scroll.add_child(body)
	var masthead := UI.label(body, "CAREER  /  赛场纪事", 16, Color("826b3a"))
	masthead.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	UI.label(body, str(entry.get("date", "")), 12, UI.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var line := HSeparator.new()
	body.add_child(line)
	var headline := UI.label(body, str(entry.get("title", entry.get("event_name", "赛场荣誉"))), 28)
	headline.name = "HonoursHeadline"
	headline.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	if entry.get("kind", "") == "top20": _top20()
	else: _event_awards()
	status = UI.label(body, "", 12, UI.MUTED)
	var buttons := HBoxContainer.new()
	buttons.add_theme_constant_override("separation", 12)
	body.add_child(buttons)
	if entry.get("kind", "") == "top20":
		# Quick mode gets the same invitation: the ceremony is the reveal.
		if entry.get("ceremony", {}).get("ready", false):
			var go := UI.button(buttons, "前往颁奖现场揭晓", acknowledge.bind(true))
			UI.primary(go)
			actions.append(go)
		reveal_button = UI.button(buttons, "在这里揭晓", start_reveal)
		actions.append(reveal_button)
		actions.append(UI.button(buttons, "稍后再看", acknowledge.bind(false)))
		status.text = ""
	else:
		var next := UI.button(buttons, "我看完了 · 继续", acknowledge.bind(false))
		UI.primary(next)
		actions.append(next)
	_layout()
	sheet.pivot_offset = sheet.size / 2
	var final_position := sheet.position
	sheet.position = final_position + Vector2(get_viewport().get_visible_rect().size.x * .72, -70)
	sheet.rotation = .08
	sheet.modulate.a = 0
	flight = create_tween().set_parallel(true)
	flight.tween_property(sheet, "position", final_position, .52).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	flight.tween_property(sheet, "rotation", 0.0, .52).set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	flight.tween_property(sheet, "modulate:a", 1.0, .28)
	if not championship_sound_played: play_sound("champion" if _won_title() else "honours")

func _layout() -> void:
	if not is_instance_valid(sheet): return
	var viewport := get_viewport().get_visible_rect().size
	sheet.size = Vector2(minf(920, viewport.x * .86), minf(820, viewport.y * .86))
	sheet.position = (viewport - sheet.size) / 2
	var headline := body.find_child("HonoursHeadline", true, false) as Label
	if headline != null:
		var title := str(entry.get("title", entry.get("event_name", "赛场荣誉")))
		var separator := title.find(" · ")
		var width := headline.get_theme_font("font").get_string_size(title, HORIZONTAL_ALIGNMENT_LEFT, -1, 28).x
		# Prefer a meaningful title/subtitle boundary to an orphaned final glyph.
		headline.text = title.substr(0, separator) + "\n" + title.substr(separator + 3) if separator >= 0 and width > sheet.size.x - 48 else title

func _won_title() -> bool:
	return not str(entry.get("own_team", "")).is_empty() and str(entry.get("champion", "")) == str(entry.get("own_team", ""))

func _event_awards() -> void:
	var champion := str(entry.get("champion", ""))
	if not champion.is_empty():
		# Text gets the complete sheet width. Sharing a non-expanding HBox
		# with the trophy/logo gave wrapped labels a one-character column.
		var champion_block := VBoxContainer.new()
		champion_block.name = "HonoursChampionBlock"
		champion_block.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		champion_block.add_theme_constant_override("separation", 6)
		body.add_child(champion_block)
		var row := HBoxContainer.new()
		row.name = "HonoursChampionMarks"
		row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.alignment = BoxContainer.ALIGNMENT_CENTER
		row.add_theme_constant_override("separation", 12)
		champion_block.add_child(row)
		var trophy := Trophy.new()
		trophy.size_flags_vertical = Control.SIZE_SHRINK_CENTER
		row.add_child(trophy)
		TeamVisuals.badge(row, champion, 64)
		var heading := UI.label(champion_block, "我们夺冠了！" if _won_title() else "赛事冠军", 17, Color("92702c"))
		heading.name = "HonoursChampionHeading"
		heading.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		heading.autowrap_mode = TextServer.AUTOWRAP_OFF
		var name_label := UI.label(champion_block, champion, 26)
		name_label.name = "HonoursChampionName"
		name_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		name_label.tooltip_text = champion
	if entry.get("mvp") != null:
		var card := UI.card(body)
		UI.label(card, "MVP  /  最有价值选手", 18, Color("9c772e"))
		_player(card, entry.mvp, true)
	for item in [["evp", "EVP  /  卓越表现"], ["five", "BEST FIVE  /  最佳阵容"]]:
		var players: Variant = entry.get(item[0], [])
		if not players is Array or players.is_empty(): continue
		var card := UI.card(body)
		UI.label(card, item[1], 17)
		for player in players: _player(card, player)

func _top20() -> void:
	top20_rows.clear(); top20_name_labels.clear(); top20_team_labels.clear(); top20_cards.clear()
	reveal_queue.clear(); revealing = false; reveal_done = false
	var intro := UI.label(body, "年度颁奖礼邀请函", 18, Color("92702c"))
	intro.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	var line := UI.label(body, "二十个名字已经封存，揭晓时刻由你决定。", 14, UI.MUTED)
	line.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	for row in entry.get("rows", []):
		if row is Dictionary: top20_rows.append(row)
	top20_rows.sort_custom(func(a, b): return int(a.get("rank", 0)) < int(b.get("rank", 0)))
	var grid := GridContainer.new()
	grid.name = "Top20SealedGrid"
	grid.columns = 2
	grid.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	grid.add_theme_constant_override("h_separation", 12)
	grid.add_theme_constant_override("v_separation", 6)
	body.add_child(grid)
	# Column-major: #1–#10 left, #11–#20 right.
	var ordered: Array[Dictionary] = []
	var half := int(ceil(top20_rows.size() / 2.0))
	for i in range(half):
		ordered.append(top20_rows[i])
		if i + half < top20_rows.size(): ordered.append(top20_rows[i + half])
	for row in ordered:
		var rank := int(row.get("rank", 0))
		var card := PanelContainer.new()
		card.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		card.add_theme_stylebox_override("panel", UI.style(Color("efe8d5"), 8, 10, Color("ddd2b6")))
		grid.add_child(card)
		var cells := HBoxContainer.new()
		cells.add_theme_constant_override("separation", 10)
		card.add_child(cells)
		var number := UI.label(cells, "#%d" % rank, 20 if rank <= 3 else 15, Color("9c772e") if rank <= 3 else UI.MUTED)
		number.custom_minimum_size.x = 44
		number.autowrap_mode = TextServer.AUTOWRAP_OFF
		var name_label := UI.label(cells, "？", 18 if rank <= 3 else 15, UI.MUTED)
		name_label.name = "HonoursPlayerName"
		name_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		name_label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
		var team_label := UI.label(cells, "", 12, UI.MUTED)
		team_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT
		team_label.size_flags_horizontal = Control.SIZE_SHRINK_END
		team_label.autowrap_mode = TextServer.AUTOWRAP_OFF
		top20_name_labels[rank] = name_label
		top20_team_labels[rank] = team_label
		top20_cards[rank] = card

## Staged reveal: #20…#4 tick over quickly, then a drum roll before each of
## the top three. The player's own row is called out when it lands.
func start_reveal() -> void:
	if revealing or reveal_done or top20_rows.is_empty(): return
	revealing = true
	reveal_clock = 0.0
	if is_instance_valid(reveal_button): reveal_button.text = "全部揭晓"; reveal_button.pressed.disconnect(start_reveal); reveal_button.pressed.connect(reveal_all)
	reveal_queue.clear()
	for row in top20_rows: reveal_queue.push_front(int(row.get("rank", 0)))

func reveal_all() -> void:
	while not reveal_queue.is_empty(): _reveal_rank(reveal_queue.pop_front(), false)
	_finish_reveal()

func _reveal_step_delay(rank: int) -> float:
	return 1.9 if rank <= 3 else (0.55 if rank <= 10 else 0.32)

func _tick_reveal(delta: float) -> void:
	if not revealing or reveal_queue.is_empty(): return
	reveal_clock += delta
	var rank: int = reveal_queue[0]
	if rank <= 3 and reveal_clock > 0.05 and not bool(top20_cards[rank].get_meta("rolling", false)):
		top20_cards[rank].set_meta("rolling", true)
		CeremonyAudio.play(self, "drumroll", -6.0)
		var label: Label = top20_name_labels[rank]
		var tween := create_tween().set_loops(4)
		tween.tween_property(label, "modulate:a", .25, .2); tween.tween_property(label, "modulate:a", 1.0, .2)
	if reveal_clock < _reveal_step_delay(rank): return
	reveal_clock = 0.0
	reveal_queue.pop_front()
	_reveal_rank(rank, true)
	if reveal_queue.is_empty(): _finish_reveal()

func _reveal_rank(rank: int, with_sound: bool) -> void:
	var row: Dictionary = {}
	for candidate in top20_rows:
		if int(candidate.get("rank", 0)) == rank: row = candidate
	if row.is_empty() or not top20_name_labels.has(rank): return
	var label: Label = top20_name_labels[rank]
	var human := str(entry.get("human_id", ""))
	var mine := not human.is_empty() and str(row.get("player_id", row.get("id", ""))) == human
	label.text = str(row.get("name", row.get("player", ""))) + ("  ·  你" if mine else "")
	label.modulate.a = 1.0
	label.add_theme_color_override("font_color", UI.GREEN if mine else UI.INK)
	(top20_team_labels[rank] as Label).text = str(row.get("team", ""))
	var team := str(row.get("team", ""))
	if not team.is_empty():
		var cells := label.get_parent()
		var mark := TeamVisuals.badge(cells, team, 22)
		if mark: cells.move_child(mark, 1)
	var card: PanelContainer = top20_cards[rank]
	if mine: card.add_theme_stylebox_override("panel", UI.style(Color("dcebd9"), 8, 10, UI.GREEN))
	elif rank <= 3: card.add_theme_stylebox_override("panel", UI.style(Color("f6e7bf"), 8, 10, Color("d4b06b")))
	if with_sound:
		CeremonyAudio.stop(self, "drumroll")
		if mine or rank <= 3:
			CeremonyAudio.play(self, "hit", -6.0)
			CeremonyAudio.play(self, "fanfare" if (mine or rank == 1) else "applause", -4.0)
		else:
			CeremonyAudio.play(self, "tick", -2.0)
		card.pivot_offset = card.size / 2
		card.scale = Vector2(1.06, 1.06)
		create_tween().tween_property(card, "scale", Vector2.ONE, .25)

func _finish_reveal() -> void:
	revealing = false
	reveal_done = true
	if is_instance_valid(reveal_button): reveal_button.disabled = true
	for button in actions:
		if button.text == "稍后再看": button.text = "我看完了 · 继续"; UI.primary(button)

func _player(parent: Node, value: Variant, featured: bool = false) -> void:
	var row := HBoxContainer.new()
	row.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_theme_constant_override("separation", 10)
	parent.add_child(row)
	var data: Dictionary = value if value is Dictionary else {"name":str(value)}
	var team := str(data.get("team", ""))
	TeamVisuals.badge(row, team, 32 if featured else 24)
	var text := str(data.get("name", data.get("player", "")))
	var human := str(entry.get("human_id", ""))
	var mine := not human.is_empty() and str(data.get("player_id", data.get("id", ""))) == human
	if mine: text += "  ·  你"
	var label := UI.label(row, text, 23 if featured else 16, UI.GREEN if mine else UI.INK)
	label.name = "HonoursPlayerName"
	if not team.is_empty(): UI.label(row, team, 13, UI.MUTED).horizontal_alignment = HORIZONTAL_ALIGNMENT_RIGHT

func acknowledge(visit: bool = false) -> void:
	# Closing a presentation is local. Losing the server must not lock the UI;
	# no unconfirmed acknowledgement or ceremony travel is invented.
	if not CareerBridge.connected and not command_sender.is_valid():
		acknowledgements_pending = false
		_release()
		return
	if entry.is_empty() or acknowledgements_pending or (is_instance_valid(champion_ceremony) and champion_ceremony.active): return
	var payload := {"ids":[str(entry.get("id", ""))], "revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0))}
	var accepted := bool(command_sender.call(ACK_PATH, payload)) if command_sender.is_valid() else CareerBridge.command(ACK_PATH, payload)
	if not accepted:
		status.text = CareerBridge.message
		return
	acknowledgements_pending = true
	visit_after_ack = visit
	for button in actions: button.disabled = true
	status.text = "正在收好这份战报……"

func _finished(path: String, result: Dictionary) -> void:
	if path != ACK_PATH or not acknowledgements_pending: return
	acknowledgements_pending = false
	if not result.get("ok", false):
		status.text = str(result.get("reason", result.get("msg", "没有确认成功，再试一下。")))
		for button in actions: button.disabled = false
		return
	var ceremony: Dictionary = entry.get("ceremony", {}).duplicate(true)
	var visit := visit_after_ack
	_release()
	if visit and not ceremony.is_empty(): Travel.go_awards(ceremony)

func _release() -> void:
	if is_instance_valid(flight): flight.kill()
	if is_instance_valid(champion_ceremony): champion_ceremony.queue_free()
	champion_ceremony = null
	if is_instance_valid(overlay): overlay.queue_free()
	entry.clear(); actions.clear()
	revealing = false; reveal_queue.clear(); reveal_done = false
	CeremonyAudio.stop(self, "drumroll")
	visit_after_ack = false
	CareerBridge.feedback_active = false
	UI.device_closed(self)

func _input(event: InputEvent) -> void:
	if entry.is_empty(): return
	if is_instance_valid(champion_ceremony) and champion_ceremony.active:
		if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode in [KEY_E, KEY_P, KEY_ESCAPE]:
			get_viewport().set_input_as_handled()
			if not champion_ceremony.continue_button.disabled: champion_ceremony.finish()
		return
	if event is InputEventKey and event.pressed and not event.echo and event.physical_keycode in [KEY_E, KEY_P, KEY_ESCAPE]:
		get_viewport().set_input_as_handled()
		if event.physical_keycode == KEY_ESCAPE: acknowledge()

func map_result(key: String, won: bool) -> bool:
	if key.is_empty() or map_sounds.has(key): return false
	map_sounds[key] = true
	play_sound("win" if won else "loss")
	return true

func play_sound(kind: String) -> void:
	last_sound = kind
	sound_count += 1
	if CareerBridge.sound_muted or CareerBridge.sound_volume <= 0: return
	if not audio_cache.has(kind):
		# Awards stings use the orchestral ceremony renders; map results and any
		# missing file keep the short synthesized versions.
		var rendered: AudioStream = CeremonyAudio.sound(kind) if kind in ["champion", "honours"] else null
		audio_cache[kind] = rendered if rendered is AudioStreamOggVorbis else make_sound(kind)
	sound_player.stream = audio_cache[kind]
	sound_player.volume_db = linear_to_db(clampf(CareerBridge.sound_volume, .001, 1.0)) - 6.0
	sound_player.play()

static func make_sound(kind: String) -> AudioStreamWAV:
	# Original short stings, synthesized once and cached. No file/network in ticks.
	var rate := 22050
	var length := 2.7 if kind == "champion" else .85
	var notes: Array = [523.25, 659.25, 783.99] if kind in ["win", "honours"] else [329.63, 277.18, 220.0]
	if kind == "champion": notes = [392.0, 523.25, 659.25, 783.99, 1046.5]
	var bytes := PackedByteArray()
	var frames := int(rate * length)
	bytes.resize(frames * 2)
	for index in range(frames):
		var t := float(index) / rate
		var segment := length / (notes.size() + 1)
		var note := mini(int(t / segment), notes.size() - 1)
		var local := fmod(t, segment)
		var envelope := minf(1, local * 100) * exp(-local * 6) * minf(1, (length - t) * 8)
		var hz: float = notes[note]
		var sample := sin(TAU * hz * t) * .22 + sin(TAU * hz * 2 * t) * .035
		if kind == "champion":
			sample += sin(TAU * hz * .5 * t) * .09
			var beat := fmod(t, .3)
			sample += sin(TAU * (56 * beat + 45 * exp(-beat * 20))) * exp(-beat * 23) * .16
		bytes.encode_s16(index * 2, int(clampf(sample * envelope, -1, 1) * 32767))
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.data = bytes
	return stream
