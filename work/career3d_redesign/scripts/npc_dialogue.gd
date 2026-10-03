extends CanvasLayer
## Dialogue presentation only; ClubLife owns choices and NPC resumption.
const UI = preload("res://scripts/computer_ui.gd")
var life
var panel: PanelContainer
var heading: Label
var activity: Label
var text: Label
var relation: Label
var portrait: Portrait
var letter_progress := 0.0
var opening: Tween
var buttons: Array[Button] = []

class Portrait extends Control:
	var shirt := Color("79a695")
	func _draw() -> void:
		var p := Vector2(size.x*.5, 62)
		draw_circle(p+Vector2(0,16),49,Color("dfebd8"))
		draw_circle(p+Vector2(0,44),36,shirt)
		draw_circle(p,32,Color("fff3d8"))
		draw_circle(p+Vector2(-12,-3),3,Color("293e35"))
		draw_circle(p+Vector2(12,-3),3,Color("293e35"))
		draw_circle(p+Vector2(-20,9),5,Color("edc2ad"))
		draw_circle(p+Vector2(20,9),5,Color("edc2ad"))
		draw_colored_polygon(PackedVector2Array([p+Vector2(-8,6),p+Vector2(8,6),p+Vector2(0,15)]),Color("d69c50"))
		for x in [-8,0,8]: draw_circle(p+Vector2(x,-32),7,Color("c77f64"))

func setup(manager) -> void:
	life = manager; layer = 8
	var root := Control.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(root)
	panel = PanelContainer.new()
	panel.name = "ClubDialogue"
	root.add_child(panel)
	panel.set_anchors_and_offsets_preset(Control.PRESET_BOTTOM_WIDE)
	panel.offset_left = 45; panel.offset_right = -45
	panel.offset_top = -310; panel.offset_bottom = -30
	panel.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 22, 24, Color("c4d0be")))
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 22)
	panel.add_child(row)
	portrait = Portrait.new()
	portrait.custom_minimum_size = Vector2(105,130)
	portrait.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_child(portrait)
	var col := VBoxContainer.new()
	col.add_theme_constant_override("separation", 10)
	col.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(col)
	var title := HBoxContainer.new()
	title.add_theme_constant_override("separation", 15)
	col.add_child(title)
	heading = UI.label(title,"",26)
	heading.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	heading.autowrap_mode = TextServer.AUTOWRAP_OFF
	var badge := PanelContainer.new()
	badge.add_theme_stylebox_override("panel", UI.style(UI.MINT,6,9))
	title.add_child(badge)
	activity = UI.label(badge,"",14,UI.GREEN)
	activity.autowrap_mode = TextServer.AUTOWRAP_OFF
	activity.size_flags_horizontal = Control.SIZE_SHRINK_BEGIN
	text = UI.label(col,"",21)
	text.name = "DialogueText"
	text.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	text.custom_minimum_size.y = 74
	text.size_flags_vertical = Control.SIZE_EXPAND_FILL
	text.mouse_filter = Control.MOUSE_FILTER_STOP
	text.gui_input.connect(func(event):
		if event is InputEventMouseButton and event.pressed and event.button_index==MOUSE_BUTTON_LEFT: reveal())
	relation = UI.label(col,"",13,UI.MUTED)
	var choices := HBoxContainer.new()
	choices.add_theme_constant_override("separation",10)
	col.add_child(choices)
	for item in [["busy","1  你在忙什么？"],["training","2  聊聊训练"],["encourage","3  一起加油"],["leave","4  回头见"]]:
		var button := UI.button(choices,item[1],handle_choice.bind(item[0]))
		button.name = "DialogueChoice_" + str(item[0])
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.custom_minimum_size.y = 42
		buttons.append(button)
	life.dialogue_changed.connect(refresh)
	life.dialogue_closed.connect(_closed)
	Locale.changed.connect(func(): if life.speaker != null: refresh())
	panel.hide()

func refresh() -> void:
	if life.speaker == null:
		_closed(); return
	var npc = life.speaker
	heading.text = str(npc.definition["name"])
	activity.text = str(npc.definition["role"])
	text.text = Locale.text(life.line)
	text.visible_characters = 0; letter_progress = 0.0
	relation.text = Locale.text("熟悉度") + "  " + "●".repeat(npc.bond) + "○".repeat(maxi(0,5-npc.bond)) + "     ·     " + Locale.text("点击文字展开 · 1—4 选择 · Esc 结束")
	portrait.shirt = Color(str(npc.definition.get("color","79a695"))); portrait.queue_redraw()
	if not panel.visible:
		panel.show(); panel.modulate.a = 0
		if opening and opening.is_valid(): opening.kill()
		opening = create_tween()
		opening.tween_property(panel,"modulate:a",1.0,.16)

func _process(delta: float) -> void:
	if not is_instance_valid(panel) or not panel.visible or text.visible_characters < 0: return
	letter_progress += delta * (48 if Locale.language=="en" else 30)
	text.visible_characters = mini(int(letter_progress),text.get_total_character_count())
	if text.visible_characters >= text.get_total_character_count(): text.visible_characters = -1

func reveal() -> void:
	if is_instance_valid(text): text.visible_characters = -1

func handle_choice(topic: String) -> void:
	if topic == "leave": life.close(); return
	if text.visible_characters >= 0:
		reveal(); return
	life.choose(topic)

func _closed() -> void:
	if opening and opening.is_valid(): opening.kill()
	panel.hide(); text.visible_characters = -1
