extends RefCounted
## Only the existing pure-data tactic contract is edited. Controls stay alive during edits.
const UI = preload("res://scripts/computer_ui.gd")
const MapCanvas = preload("res://scripts/tactics_canvas.gd")
const DEFAULT_MAPS := ["de_dust2", "de_mirage", "de_inferno", "de_nuke", "de_ancient", "de_anubis", "de_overpass", "de_train", "de_vertigo", "de_cache"]
const DUTIES := [{"id":"auto", "name":"自动职责"}, {"id":"awp", "name":"主狙"}, {"id":"entry", "name":"突破"}, {"id":"rifle", "name":"步枪"}, {"id":"lurk", "name":"自由人"}, {"id":"igl", "name":"指挥"}]
const MAX_BYTES := 256 * 1024
const FINISHES := [{"id":"auto", "name":"自动：CT 留守，T 自主行动"}, {"id":"hold", "name":"留守最后位置"}, {"id":"native", "name":"恢复原生行动"}]
var host: Node
var map_code := "de_dust2"
var libraries: Dictionary = {}
var drafts: Dictionary = {}
var draft: Dictionary = {}
var selected_slot := 1
var selected_step := -1
var edit_mode := "route"
var map_tool := "edit"
var layer_index := 0
var library_filter := "all"
var original_id := ""
var base_draft := ""
var pending_path := ""
var pending_map := ""
var pending_action := ""
var pending_action_map := ""
var pending_tactic: Dictionary = {}
var pending_import_id := ""
var notice := ""
var dirty := false
var textures: Dictionary = {}
var command_sender: Callable
var clipboard_writer: Callable
var clipboard_reader: Callable
var copied_command := ""
var copy_feedback_deadline_msec := 0
var pending_read_feedback := false
var controls: Dictionary = {}
var view: Control
var canvas: Control
var confirmation: ConfirmationDialog
var confirmation_action: Callable
var file_dialog: FileDialog
var syncing := false
var map_views: Dictionary = {}

func attach(value: Node) -> void:
	host = value

func library() -> Dictionary:
	return libraries.get(map_code, {})

func render(parent: Node) -> void:
	controls.clear()
	if draft.is_empty(): make_draft()
	view = VBoxContainer.new()
	view.name = "TacticsEditor"
	view.add_theme_constant_override("separation", 7)
	parent.add_child(view)
	UI.label(view, "战术室 · 五个位置的路线", 21)
	UI.label(view, "点击地图添加路点；点击彩色点选中，拖动调整位置；右键设置观察方向。", 12, UI.MUTED)
	var top := HBoxContainer.new()
	view.add_child(top)
	choice(top, "TacticsMap", [], map_code, change_map)
	choice(top, "TacticsLibrary", [], "", load_selected_tactic)
	choice(top, "TacticsFilter", [{"id":"all", "name":"全部阵营"}, {"id":"t", "name":"T 进攻"}, {"id":"ct", "name":"CT 防守"}], library_filter, filter_changed)
	controls.TacticsLibrary.size_flags_stretch_ratio = 2
	var fields := HBoxContainer.new()
	view.add_child(fields)
	var id_column := VBoxContainer.new()
	id_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fields.add_child(id_column)
	UI.label(id_column, "ID（聊天指令名）", 11, UI.MUTED)
	line(id_column, "TacticsId", str(draft.get("id", "")), "小写字母 / 数字 / _ / -", func(value: String): draft["id"] = value; changed(), 32)
	var title_column := VBoxContainer.new()
	title_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	fields.add_child(title_column)
	UI.label(title_column, "名称", 11, UI.MUTED)
	line(title_column, "TacticsName", str(draft.get("name", "")), "战术名称", func(value: String): draft["name"] = value; changed(), 40)
	var side_column := VBoxContainer.new()
	fields.add_child(side_column)
	UI.label(side_column, "阵营", 11, UI.MUTED)
	choice(side_column, "TacticsSide", [{"id":"t", "name":"T 进攻"}, {"id":"ct", "name":"CT 防守"}], str(draft.get("side", "t")), func(value: String): draft["side"] = value; changed())
	var assignment_row := HBoxContainer.new()
	view.add_child(assignment_row)
	choice(assignment_row, "TacticsAssignment", [{"id":"roster", "name":"名单顺序分配"}, {"id":"ability", "name":"按能力匹配"}], str(draft.get("assignment", "roster")), assignment_changed)
	var human_choices: Array = []
	for number in range(1, 6): human_choices.append({"id":str(number), "name":"真人手动位置 %d" % number})
	choice(assignment_row, "TacticsHumanSlot", human_choices, str(draft.get("human_slot", 1)), human_changed)
	controls.assignment_note = UI.label(view, "", 11, UI.MUTED)
	UI.label(view, "职责可重复，可设置双狙。主狙按正常经济购买 AWP；资金不足时使用正常购买流程。", 11, UI.MUTED)
	var toolbar := HFlowContainer.new()
	toolbar.add_theme_constant_override("h_separation", 6)
	view.add_child(toolbar)
	button(toolbar, "TacticsSave", "保存战术", save_tactic)
	UI.primary(controls.TacticsSave)
	button(toolbar, "TacticsNew", "新建", new_tactic)
	button(toolbar, "TacticsRefresh", "重新读取", fetch.bind(true))
	button(toolbar, "TacticsImport", "导入 JSON", choose_import)
	button(toolbar, "TacticsExport", "导出当前", choose_export.bind(false))
	button(toolbar, "TacticsExportAll", "导出全部", choose_export.bind(true))
	button(toolbar, "TacticsDelete", "删除战术", delete_tactic)
	controls.dirty = UI.label(view, "", 11, UI.MUTED)
	var columns := HBoxContainer.new()
	columns.add_theme_constant_override("separation", 14)
	view.add_child(columns)
	var map_column := VBoxContainer.new()
	map_column.custom_minimum_size.x = 350
	map_column.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	columns.add_child(map_column)
	choice(map_column, "TacticsLayer", [], "", layer_changed)
	controls.layer_note = UI.label(map_column, "雷达视图只切换底图；每个路点的上层 / 下层请单独设置。", 11, UI.MUTED)
	var tools_row := HBoxContainer.new()
	map_column.add_child(tools_row)
	controls.tool_row = tools_row
	button(tools_row, "TacticsEditTool", "编辑路点", set_map_tool.bind("edit"))
	button(tools_row, "TacticsPanTool", "平移地图", set_map_tool.bind("pan"))
	controls.tool_status = UI.label(map_column, "", 12, UI.INK)
	canvas = MapCanvas.new()
	canvas.name = "TacticsMapCanvas"
	canvas.custom_minimum_size = Vector2(350, 290)
	canvas.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	canvas.point_chosen.connect(point_chosen)
	canvas.node_selected.connect(select_node)
	canvas.node_moved.connect(move_node)
	canvas.view_states = map_views
	canvas.view_changed.connect(zoom_changed)
	map_column.add_child(canvas)
	var zoom_row := HBoxContainer.new()
	map_column.add_child(zoom_row)
	button(zoom_row, "TacticsZoomOut", "−", func(): canvas.zoom_out())
	button(zoom_row, "TacticsZoomIn", "+", func(): canvas.zoom_in())
	button(zoom_row, "TacticsZoomFit", "适应地图", func(): canvas.fit_view())
	controls.zoom = UI.label(zoom_row, "100%", 11, UI.MUTED)
	UI.label(map_column, "滚轮缩放；也可用中键或空格＋左键临时平移。", 11, UI.MUTED)
	controls.map_note = UI.label(map_column, "", 11, UI.MUTED)
	var copy_row := HBoxContainer.new()
	map_column.add_child(copy_row)
	var copy_choices: Array = [{"id":"all", "name":"全部其他位置"}]
	for number in range(1, 6): copy_choices.append({"id":str(number), "name":"位置 %d" % number})
	choice(copy_row, "TacticsCopyTarget", copy_choices, "all", func(_value: String): pass)
	button(copy_row, "TacticsCopy", "复制本槽路线", copy_selected_route)
	var editor := VBoxContainer.new()
	editor.custom_minimum_size.x = 280
	editor.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	editor.add_theme_constant_override("separation", 5)
	columns.add_child(editor)
	controls.slot_title = UI.label(editor, "", 13)
	var slots_row := HBoxContainer.new()
	editor.add_child(slots_row)
	for number in range(1, 6): button(slots_row, "TacticsSlot%d" % number, str(number), select_slot.bind(number))
	choice(editor, "TacticsDuty", DUTIES, str(slot().get("duty", "auto")), func(value: String): slot()["duty"] = value; changed())
	UI.label(editor, "路线结束后", 11, UI.MUTED)
	choice(editor, "TacticsFinish", FINISHES, str(slot().get("finish", "auto")), func(value: String): slot()["finish"] = value; changed())
	controls.step_count = UI.label(editor, "", 11, UI.MUTED)
	var step_scroll := ScrollContainer.new()
	step_scroll.custom_minimum_size.y = 98
	step_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	editor.add_child(step_scroll)
	var timeline := VBoxContainer.new()
	timeline.name = "TacticsTimeline"
	timeline.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	step_scroll.add_child(timeline)
	controls.timeline = timeline
	controls.selection = UI.label(editor, "", 12, UI.MUTED)
	var detail := VBoxContainer.new()
	detail.name = "TacticsStepDetail"
	editor.add_child(detail)
	controls.detail = detail
	UI.label(detail, "到当前点 · 这段路的移动方式", 11, UI.MUTED)
	choice(detail, "TacticsMovement", [{"id":"run", "name":"跑动（默认）"}, {"id":"walk", "name":"静步"}], "run", movement_changed)
	var wait_row := HBoxContainer.new()
	detail.add_child(wait_row)
	var wait_label := UI.label(wait_row, "到点后等待（秒）", 11, UI.MUTED)
	wait_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	var hold := SpinBox.new()
	hold.name = "TacticsHold"
	hold.min_value = 0
	hold.max_value = 30
	hold.step = 0.1
	hold.custom_minimum_size.x = 86
	UI.line_edit(hold.get_line_edit())
	wait_row.add_child(hold)
	controls.TacticsHold = hold
	hold.value_changed.connect(wait_changed)
	choice(detail, "TacticsLevel", [{"id":"auto", "name":"自动判断层级"}, {"id":"upper", "name":"上层"}, {"id":"lower", "name":"下层"}], "auto", level_changed)
	controls.look = UI.label(detail, "", 11, UI.MUTED)
	var look_actions := HBoxContainer.new()
	detail.add_child(look_actions)
	button(look_actions, "TacticsSetLook", "设置观察方向", toggle_look)
	button(look_actions, "TacticsClearLook", "取消观察", clear_look)
	var step_actions := HBoxContainer.new()
	detail.add_child(step_actions)
	button(step_actions, "TacticsStepUp", "上移", reorder_step.bind(-1))
	button(step_actions, "TacticsStepDown", "下移", reorder_step.bind(1))
	button(step_actions, "TacticsRemoveStep", "删除路点", remove_step)
	UI.label(view, "中途 0 秒不停留；最后按结束方式行动。留守时仍会射击，受伤、无线电或炸弹任务可接管。", 11, UI.MUTED)
	var command_row := HBoxContainer.new()
	view.add_child(command_row)
	UI.label(command_row, "准备阶段聊天指令", 11, UI.MUTED)
	var command := line(command_row, "TacticsCommand", "", "", func(_value: String): pass)
	command.editable = false
	button(command_row, "TacticsCopyCommand", "复制指令", copy_command)
	button(command_row, "TacticsSync", "同步当前对局", sync_current_match)
	controls.publication = UI.label(view, "", 11, UI.MUTED)
	controls.notice = UI.label(view, notice, 12, UI.MUTED)
	controls.runtime = UI.label(view, "", 11, UI.MUTED)
	refresh_library_controls()
	refresh(true)
	if not libraries.has(map_code) and pending_path.is_empty(): host.call_deferred("_fetch_tactics")

func choice(parent: Node, node_name: String, choices: Array, selected: String, callback: Callable) -> OptionButton:
	var select := OptionButton.new()
	select.name = node_name
	UI.dark_options(select)
	for state in ["normal", "hover", "pressed"]: select.add_theme_stylebox_override(state, UI.style(UI.PAPER, 5, 8, UI.LINE))
	select.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	select.add_theme_font_size_override("font_size", 12)
	parent.add_child(select)
	controls[node_name] = select
	set_options(select, choices, selected)
	select.item_selected.connect(func(index: int):
		if not syncing: callback.call(str(select.get_item_metadata(index)))
	)
	return select

func line(parent: Node, node_name: String, value: String, placeholder: String, callback: Callable, maximum: int = 0) -> LineEdit:
	var input := LineEdit.new()
	input.name = node_name
	UI.line_edit(input)
	input.text = value
	input.placeholder_text = placeholder
	input.max_length = maximum
	input.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	input.custom_minimum_size.x = 110
	parent.add_child(input)
	controls[node_name] = input
	input.text_changed.connect(func(text_value: String):
		if not syncing: callback.call(text_value)
	)
	return input

func button(parent: Node, node_name: String, caption: String, callback: Callable) -> Button:
	var result: Button = host._button(parent, caption, callback, false)
	result.name = node_name
	compact(result)
	controls[node_name] = result
	return result

func compact(node: Button) -> void:
	node.custom_minimum_size.y = 27
	node.add_theme_font_size_override("font_size", 12)
	node.add_theme_stylebox_override("normal", UI.style(UI.PAPER, 4, 7, UI.LINE))
	node.add_theme_stylebox_override("hover", UI.style(Color("e5eddf"), 4, 7, Color("9eb19c")))
	for state in ["pressed", "hover_pressed"]: node.add_theme_stylebox_override(state, UI.style(UI.MINT, 4, 7, UI.GREEN))

func set_options(select: OptionButton, choices: Array, selected: String) -> void:
	select.clear()
	for entry in choices:
		select.add_item(str(entry.get("name", entry.get("id", ""))))
		select.set_item_metadata(select.item_count - 1, str(entry.get("id", "")))
		if str(entry.get("id", "")) == selected: select.select(select.item_count - 1)

func select_value(select: OptionButton, value: String) -> void:
	for index in range(select.item_count):
		if str(select.get_item_metadata(index)) == value:
			select.select(index)
			return

func current_value(select: OptionButton) -> String:
	return str(select.get_item_metadata(select.selected)) if select.selected >= 0 else ""

func has_view() -> bool:
	return is_instance_valid(view) and view.is_inside_tree() and not view.is_queued_for_deletion()

func busy() -> bool:
	return not pending_action.is_empty() or (CareerBridge.busy and CareerBridge.active_post)

func refresh_library_controls() -> void:
	if not has_view(): return
	syncing = true
	var maps: Array = []
	var available: Array = library().get("available_maps", [])
	if available.is_empty():
		for code in DEFAULT_MAPS: available.append({"map":code, "name":str(code).trim_prefix("de_").capitalize()})
	for entry in available: maps.append({"id":str(entry.get("map", "")), "name":str(entry.get("name", entry.get("map", "")))})
	set_options(controls.TacticsMap, maps, map_code)
	var saved: Array = [{"id":"", "name":"选择已保存战术"}]
	for tactic in library().get("tactics", []):
		if library_filter != "all" and str(tactic.get("side", "t")) != library_filter: continue
		saved.append({"id":str(tactic.get("id", "")), "name":"%s · %s · %s" % [tactic.get("name", "战术"), str(tactic.get("side", "t")).to_upper(), tactic.get("id", "")]})
	set_options(controls.TacticsLibrary, saved, original_id)
	var layers: Array = library().get("map_meta", {}).get("layers", [])
	var choices: Array = []
	for index in range(layers.size()): choices.append({"id":str(index), "name":str(layers[index].get("name", layers[index].get("id", "地图")))})
	if choices.is_empty(): choices.append({"id":"0", "name":"地图雷达"})
	layer_index = clampi(layer_index, 0, choices.size() - 1)
	set_options(controls.TacticsLayer, choices, str(layer_index))
	controls.TacticsLayer.visible = layers.size() > 1
	controls.layer_note.visible = layers.size() > 1
	controls.runtime.text = str(library().get("runtime_note", ""))
	refresh_publication()
	syncing = false
	refresh_canvas()

func refresh(update_values: bool = false) -> void:
	if not has_view(): return
	syncing = true
	if update_values:
		if controls.TacticsId.text != str(draft.get("id", "")): controls.TacticsId.text = str(draft.get("id", ""))
		if controls.TacticsName.text != str(draft.get("name", "")): controls.TacticsName.text = str(draft.get("name", ""))
		select_value(controls.TacticsSide, str(draft.get("side", "t")))
		select_value(controls.TacticsAssignment, str(draft.get("assignment", "roster")))
		select_value(controls.TacticsHumanSlot, str(draft.get("human_slot", 1)))
		select_value(controls.TacticsDuty, str(slot().get("duty", "auto")))
		select_value(controls.TacticsFinish, str(slot().get("finish", "auto")))
		if has_step():
			var step: Dictionary = steps()[selected_step]
			controls.TacticsHold.set_value_no_signal(float(step.get("wait", 0)))
			select_value(controls.TacticsMovement, str(step.get("movement", "run")))
			select_value(controls.TacticsLevel, str(step.get("level", "auto")))
	var locked := busy()
	for value in controls.values():
		if value is Button: value.disabled = locked
		elif value is LineEdit and value != controls.TacticsCommand: value.editable = not locked
	# Viewing tools never change the draft and remain usable during a service write.
	for name in ["TacticsEditTool", "TacticsPanTool", "TacticsZoomOut", "TacticsZoomIn", "TacticsZoomFit"]: controls[name].disabled = false
	# Clipboard is local: a poll or pending save must never lock this control.
	controls.TacticsCopyCommand.disabled = not valid_id(str(draft.get("id", "")))
	var published: Dictionary = library().get("publication", {})
	controls.TacticsSync.disabled = locked or not bool(published.get("can_sync", false)) or not bool(published.get("pending", true))
	refresh_copy_caption()
	controls.TacticsHold.editable = not locked
	controls.TacticsSave.disabled = locked or library().get("map_meta", {}).is_empty()
	controls.TacticsDelete.disabled = locked or original_id.is_empty()
	controls.TacticsRefresh.disabled = locked or not pending_path.is_empty()
	controls.TacticsExportAll.disabled = locked or library().get("tactics", []).is_empty()
	controls.TacticsHumanSlot.disabled = locked or draft.get("assignment", "roster") != "ability"
	controls.TacticsCopy.disabled = locked or steps().is_empty()
	for index in range(controls.TacticsCopyTarget.item_count): controls.TacticsCopyTarget.set_item_disabled(index, str(controls.TacticsCopyTarget.get_item_metadata(index)) == str(selected_slot))
	if current_value(controls.TacticsCopyTarget) == str(selected_slot): select_value(controls.TacticsCopyTarget, "all")
	var ability: bool = draft.get("assignment", "roster") == "ability"
	controls.assignment_note.text = "能力模式按职责与选手能力分配 Bot；真人所选路线只作参考，始终手动操作。" if ability else "位置 1 是你，手动操作；位置 2—5 按本场队友名单顺序分配。"
	var human_slot := int(draft.get("human_slot", 1))
	controls.slot_title.text = "位置 %d · %s · 职责" % [selected_slot, "你手动操作" if selected_slot == human_slot else ("能力匹配队友" if ability else "队友 %d" % (selected_slot - 1))]
	for number in range(1, 6):
		var slot_button: Button = controls["TacticsSlot%d" % number]
		slot_button.text = "%d · %d" % [number, draft.slots[number - 1].steps.size()]
		slot_button.add_theme_stylebox_override("normal", UI.style(UI.MINT if number == selected_slot else UI.PAPER, 4, 7, UI.LINE))
	controls.step_count.text = "本槽步骤 · %d / 12" % steps().size()
	refresh_timeline()
	controls.detail.visible = has_step()
	controls.selection.text = "先选择或添加一个路点。" if not has_step() else "路点 %d · 位置 %.1f, %.1f" % [selected_step + 1, float(steps()[selected_step].position[0]), float(steps()[selected_step].position[1])]
	if has_step():
		var look_value = steps()[selected_step].get("look_at")
		controls.look.text = "观察目标 · %.1f, %.1f" % [float(look_value[0]), float(look_value[1])] if look_value is Array else "观察目标 · 尚未设置"
		controls.TacticsClearLook.disabled = locked or not look_value is Array
		controls.TacticsStepUp.disabled = locked or selected_step == 0
		controls.TacticsStepDown.disabled = locked or selected_step == steps().size() - 1
	controls.TacticsSetLook.text = "取消标记" if edit_mode == "look" else "设置观察方向"
	for name in ["TacticsEditTool", "TacticsPanTool"]:
		var active: bool = (map_tool == "pan") == (name == "TacticsPanTool")
		controls[name].add_theme_stylebox_override("normal", UI.style(UI.MINT if active else UI.PAPER, 4, 7, UI.LINE))
	controls.tool_status.text = "当前：平移地图 · 按住左键拖动地图，不会添加路点。" if map_tool == "pan" else "当前：编辑路点 · 左键添加 / 拖动路点，右键设置观察方向。"
	controls.dirty.text = "当前草稿未保存" if dirty else ("已保存" if not original_id.is_empty() else "草稿尚未保存")
	controls.TacticsCommand.text = "play " + (str(draft.get("id", "")) if valid_id(str(draft.get("id", ""))) else "<id>")
	controls.notice.text = notice
	syncing = false
	refresh_canvas()

func refresh_timeline() -> void:
	var timeline: VBoxContainer = controls.timeline
	UI.clear(timeline)
	for index in range(steps().size()):
		var step: Dictionary = steps()[index]
		var wait_value := float(step.get("wait", 0))
		var wait_text := "等待 %ss" % str(wait_value) if wait_value > 0 else "经过点"
		if index == steps().size() - 1:
			var finish := str(slot().get("finish", "auto"))
			var final_text := "留守最后位置" if finish == "hold" or (finish == "auto" and draft.get("side") == "ct") else "恢复原生行动"
			wait_text = (wait_text + " → " if wait_value > 0 else "") + final_text
		var layer := str(step.get("level", "auto"))
		var layer_text := "自动" if layer == "auto" else ("上层" if layer == "upper" else "下层")
		var caption := "%d · %.0f, %.0f\n%s · %s · %s%s" % [index + 1, float(step.position[0]), float(step.position[1]), "静步" if step.get("movement", "run") == "walk" else "跑动", layer_text, wait_text, " · ↗" if step.get("look_at") is Array else ""]
		var step_button: Button = host._button(timeline, caption, select_step.bind(index), false)
		step_button.name = "TacticsStep%d" % index
		step_button.disabled = busy()
		compact(step_button)
		step_button.alignment = HORIZONTAL_ALIGNMENT_LEFT
		if index == selected_step: step_button.add_theme_stylebox_override("normal", UI.style(UI.MINT, 4, 7, UI.LINE))

func refresh_canvas() -> void:
	if not is_instance_valid(canvas): return
	var metadata: Dictionary = library().get("map_meta", {})
	canvas.metadata = metadata
	canvas.slots = draft.get("slots", [])
	canvas.selected_slot = selected_slot
	canvas.selected_step = selected_step
	canvas.look_mode = edit_mode == "look"
	canvas.set_tool_mode(map_tool)
	canvas.set_editable(not busy() and valid_meta(metadata))
	canvas.use_view("%s:%d" % [map_code, layer_index])
	var path := str(metadata.get("image_path", ""))
	var layers: Array = metadata.get("layers", [])
	if not layers.is_empty(): path = str(layers[clampi(layer_index, 0, layers.size() - 1)].get("image_path", path))
	canvas.texture = texture_for(path)
	canvas.queue_redraw()
	if has_view(): controls.map_note.text = "地图资料正在读取；载入后再安排路点。" if not valid_meta(metadata) else ("地图底图无法读取；点击重新读取。" if canvas.texture == null else ("点击地图选择观察目标。" if edit_mode == "look" else ("按住左键移动地图；切回「编辑路点」后可调整路线。" if map_tool == "pan" else "要移动放大后的地图，点击上方「平移地图」。")))

func valid_meta(metadata: Dictionary) -> bool:
	for key in ["pos_x", "pos_y", "scale", "width", "height"]:
		if not metadata.get(key) is float and not metadata.get(key) is int: return false
		if not is_finite(float(metadata[key])): return false
	return float(metadata.get("scale", 0)) > 0 and float(metadata.get("width", 0)) > 0 and float(metadata.get("height", 0)) > 0

func texture_for(path: String) -> Texture2D:
	if path.is_empty() or not FileAccess.file_exists(path): return null
	if not textures.has(path):
		var image := Image.new()
		if image.load(path) == OK: textures[path] = ImageTexture.create_from_image(image)
	return textures.get(path)

func make_draft() -> void:
	var taken: Array = library().get("tactics", [])
	var ident := "my_tactic"
	var suffix := 1
	var taken_ids: Array = []
	for row in taken: taken_ids.append(row.get("id"))
	while ident in taken_ids:
		suffix += 1
		ident = "my_tactic_%d" % suffix
	draft = {"id":ident, "name":"自定义战术", "side":"t", "assignment":"roster", "human_slot":1, "slots":[]}
	for number in range(1, 6): draft.slots.append({"slot":number, "duty":"auto", "steps":[]})
	selected_slot = 1
	selected_step = -1
	edit_mode = "route"
	original_id = ""
	base_draft = JSON.stringify(draft)
	dirty = false

func changed() -> void:
	dirty = JSON.stringify(draft) != base_draft
	refresh()

func report_notice(message: String, kind: String = "success", operation: String = "") -> void:
	notice = message
	if is_instance_valid(host) and host.has_method("show_action_feedback"):
		host.show_action_feedback(message, kind, 0.0 if kind == "progress" else 6.0 if kind == "error" else 4.5, operation)

func refresh_copy_caption() -> void:
	if not has_view(): return
	var current := "play " + str(draft.get("id", ""))
	controls.TacticsCopyCommand.text = "已复制 ✓" if current == copied_command and Time.get_ticks_msec() < copy_feedback_deadline_msec else "复制指令"

func request_confirmation(message: String, action: Callable) -> void:
	if is_instance_valid(confirmation): confirmation.hide(); confirmation.queue_free()
	confirmation_action = action
	confirmation = ConfirmationDialog.new()
	confirmation.name = "TacticsConfirmation"
	confirmation.title = "战术室"
	confirmation.dialog_text = message
	confirmation.ok_button_text = "继续"
	confirmation.cancel_button_text = "取消"
	confirmation.get_label().autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	host.add_child(confirmation)
	confirmation.confirmed.connect(confirm_pending)
	confirmation.canceled.connect(cancel_confirmation)
	confirmation.close_requested.connect(cancel_confirmation)
	confirmation.popup_centered(Vector2i(460, 160))

func confirm_pending() -> void:
	var action := confirmation_action
	confirmation_action = Callable()
	if is_instance_valid(confirmation): confirmation.hide(); confirmation.queue_free()
	if action.is_valid(): action.call()

func cancel_confirmation() -> void:
	confirmation_action = Callable()
	if is_instance_valid(confirmation): confirmation.hide(); confirmation.queue_free()
	refresh_library_controls()

func discard_then(action: Callable) -> void:
	if busy(): return
	if dirty: request_confirmation("放弃当前未保存的修改？", action)
	else: action.call()

func new_tactic() -> void:
	discard_then(func(): make_draft(); notice = ""; refresh_library_controls(); refresh(true))

func load_selected_tactic(ident: String) -> void:
	for tactic in library().get("tactics", []):
		if str(tactic.get("id", "")) == ident: open_tactic(tactic); return

func open_tactic(value: Dictionary) -> void:
	var candidate := value.duplicate(true)
	discard_then(func(): set_draft(candidate); notice = ""; refresh_library_controls(); refresh(true))

func set_draft(value: Dictionary) -> void:
	draft = value.duplicate(true)
	coerce_tactic_integers(draft)
	draft.slots.sort_custom(func(a, b): return int(a.slot) < int(b.slot))
	selected_slot = 1
	selected_step = 0 if not steps().is_empty() else -1
	edit_mode = "route"
	original_id = str(draft.get("id", ""))
	base_draft = JSON.stringify(draft)
	dirty = false

func coerce_tactic_integers(value: Dictionary) -> void:
	# Godot parses every JSON number as float; the engine requires integer slot fields.
	if value.has("human_slot"): value["human_slot"] = int(value.human_slot)
	for row in value.get("slots", []): row["slot"] = int(row.slot)

func change_map(value: String) -> void:
	if value == map_code or value not in DEFAULT_MAPS: return
	if busy(): return
	var switch_map := func():
		drafts[map_code] = {"draft":draft.duplicate(true), "id":original_id, "dirty":dirty, "base":base_draft, "slot":selected_slot, "step":selected_step}
		map_code = value
		layer_index = 0
		notice = ""
		var cached: Dictionary = drafts.get(value, {})
		if cached.is_empty(): make_draft()
		else:
			set_draft(cached.draft)
			original_id = str(cached.id)
			base_draft = str(cached.base)
			dirty = bool(cached.dirty)
			selected_slot = int(cached.slot)
			selected_step = int(cached.step)
		refresh_library_controls()
		refresh(true)
		if not libraries.has(map_code): fetch()
	if dirty: request_confirmation("当前草稿未保存。切换地图后将保留草稿，继续？", switch_map)
	else: switch_map.call()

func filter_changed(value: String) -> void:
	library_filter = value
	refresh_library_controls()

func layer_changed(value: String) -> void:
	layer_index = int(value)
	refresh_canvas()

func zoom_changed(value: float) -> void:
	if has_view() and controls.has("zoom"): controls.zoom.text = "%d%%" % roundi(value * 100)

func set_map_tool(value: String) -> void:
	if value not in ["edit", "pan"]: return
	map_tool = value
	if value == "pan": edit_mode = "route"
	refresh()

func slot() -> Dictionary:
	return draft.get("slots", [])[selected_slot - 1]

func steps() -> Array:
	return slot().get("steps", [])

func has_step() -> bool:
	return selected_step >= 0 and selected_step < steps().size()

func select_slot(number: int) -> void:
	if busy() or number < 1 or number > 5: return
	selected_slot = number
	selected_step = 0 if not steps().is_empty() else -1
	edit_mode = "route"
	refresh(true)

func select_step(index: int) -> void:
	if busy() or index < 0 or index >= steps().size(): return
	selected_step = index
	edit_mode = "route"
	refresh(true)

func select_node(number: int, index: int) -> void:
	if busy(): return
	selected_slot = number
	selected_step = index
	edit_mode = "route"
	refresh(true)

func move_node(number: int, index: int, world: Array) -> void:
	if busy(): return
	var route: Array = draft.slots[number - 1].steps
	if index < 0 or index >= route.size(): return
	route[index]["position"] = world.duplicate()
	changed()

func point_chosen(world: Array, look: bool) -> void:
	if busy(): return
	if look or edit_mode == "look":
		if not has_step(): return
		steps()[selected_step]["look_at"] = world.duplicate()
		edit_mode = "route"
	else:
		if steps().size() >= 12: notice = "每个位置最多 12 个路点。"; refresh(); return
		steps().append({"position":world.duplicate(), "level":"auto", "wait":0, "look_at":null, "movement":"run"})
		selected_step = steps().size() - 1
	notice = ""
	dirty = JSON.stringify(draft) != base_draft
	refresh(true)

func toggle_look() -> void:
	if not has_step() or busy(): return
	map_tool = "edit"
	edit_mode = "route" if edit_mode == "look" else "look"
	refresh()

func clear_look() -> void:
	if not has_step() or busy(): return
	steps()[selected_step]["look_at"] = null
	edit_mode = "route"
	changed()

func movement_changed(value: String) -> void:
	if has_step(): steps()[selected_step]["movement"] = value; changed()

func level_changed(value: String) -> void:
	if has_step(): steps()[selected_step]["level"] = value; changed()

func wait_changed(value: float) -> void:
	if not syncing and has_step(): steps()[selected_step]["wait"] = value; changed()

func remove_step() -> void:
	if not has_step() or busy(): return
	steps().remove_at(selected_step)
	selected_step = mini(selected_step, steps().size() - 1)
	edit_mode = "route"
	dirty = JSON.stringify(draft) != base_draft
	refresh(true)

func reorder_step(delta: int) -> void:
	var destination := selected_step + delta
	if not has_step() or busy() or destination < 0 or destination >= steps().size(): return
	var previous = steps()[selected_step]
	steps()[selected_step] = steps()[destination]
	steps()[destination] = previous
	selected_step = destination
	edit_mode = "route"
	dirty = JSON.stringify(draft) != base_draft
	refresh(true)

func copy_selected_route() -> void:
	copy_route(current_value(controls.TacticsCopyTarget))

func copy_route(target: String) -> void:
	if busy() or steps().is_empty(): return
	var targets: Array[int] = []
	for number in range(1, 6):
		if number != selected_slot and (target == "all" or str(number) == target): targets.append(number)
	if targets.is_empty(): return
	var source := steps().duplicate(true)
	var finish := str(slot().get("finish", "auto"))
	var apply_copy := func():
		for number in targets:
			draft.slots[number - 1]["steps"] = source.duplicate(true)
			draft.slots[number - 1]["finish"] = finish
		report_notice("路线已复制到%s，记得保存战术。" % ("其他四个位置" if target == "all" else "位置 " + target))
		changed()
	if targets.any(func(number): return not draft.slots[number - 1].steps.is_empty()): request_confirmation("目标位置已有步骤，复制后将替换，继续？", apply_copy)
	else: apply_copy.call()

func assignment_changed(value: String) -> void:
	draft["assignment"] = value
	if value == "roster": draft["human_slot"] = 1
	elif not draft.has("human_slot"): draft["human_slot"] = 1
	dirty = JSON.stringify(draft) != base_draft
	refresh(true)

func human_changed(value: String) -> void:
	if draft.get("assignment", "roster") != "ability": return
	draft["human_slot"] = int(value)
	changed()

func set_human() -> void:
	human_changed(str(selected_slot))
	refresh(true)

func valid_id(value: String) -> bool:
	if value.is_empty() or value.length() > 32: return false
	for index in range(value.length()):
		if value[index] not in "abcdefghijklmnopqrstuvwxyz0123456789_-": return false
	return true

func pair_error(value, label: String) -> String:
	if not value is Array or value.size() != 2: return label + "必须是两个有限坐标。"
	for coordinate in value:
		if not coordinate is float and not coordinate is int: return label + "必须是两个有限坐标。"
		if not is_finite(float(coordinate)): return label + "必须是两个有限坐标。"
	var meta: Dictionary = library().get("map_meta", {})
	if valid_meta(meta):
		if float(value[0]) < float(meta.pos_x) or float(value[0]) > float(meta.pos_x) + float(meta.width) * float(meta.scale) or float(value[1]) > float(meta.pos_y) or float(value[1]) < float(meta.pos_y) - float(meta.height) * float(meta.scale): return label + "超出当前地图范围。"
	return ""

func tactic_error(value) -> String:
	if not value is Dictionary: return "导入内容需为一条战术或战术包。"
	for key in ["id", "name", "side", "slots"]:
		if not value.has(key): return "战术缺少字段：" + key
	for key in value:
		if key not in ["id", "name", "side", "slots", "assignment", "human_slot"]: return "战术包含未知字段：" + str(key)
	if not value.id is String or not valid_id(value.id): return "ID 只能用 1—32 个小写字母、数字、下划线或短横线。"
	if not value.name is String or value.name.strip_edges().is_empty() or value.name.length() > 40: return "名称需为 1—40 个可见字符。"
	if value.side not in ["t", "ct"]: return "战术阵营需为 T 或 CT。"
	var assignment = value.get("assignment", "roster")
	var human = value.get("human_slot", 1)
	if assignment not in ["roster", "ability"]: return "分配模式需为 roster 或 ability。"
	if (not human is int and not human is float) or float(human) != int(human) or int(human) < 1 or int(human) > 5 or (assignment == "roster" and int(human) != 1): return "真人槽位需为 1—5；名单顺序模式固定为位置 1。"
	if not value.slots is Array or value.slots.size() != 5: return "战术需要 1—5 号各一个位置。"
	var seen: Array = []
	for row in value.slots:
		if not row is Dictionary or not row.has("slot") or not row.has("steps"): return "位置字段不完整。"
		for key in row:
			if key not in ["slot", "steps", "duty", "finish"]: return "位置包含未知字段：" + str(key)
		if (not row.slot is float and not row.slot is int) or float(row.slot) != int(row.slot) or int(row.slot) < 1 or int(row.slot) > 5 or int(row.slot) in seen: return "战术需要 1—5 号各一个位置。"
		seen.append(int(row.slot))
		if row.get("duty", "auto") not in ["auto", "awp", "entry", "rifle", "lurk", "igl"]: return "位置职责无效。"
		if row.get("finish", "auto") not in ["auto", "hold", "native"]: return "路线结束方式无效。"
		if not row.steps is Array or row.steps.size() > 12: return "每个位置最多 12 个路点。"
		for step in row.steps:
			if not step is Dictionary: return "路点字段无效。"
			for key in ["position", "level", "wait", "look_at"]:
				if not step.has(key): return "路点缺少字段：" + key
			for key in step:
				if key not in ["position", "level", "wait", "look_at", "movement"]: return "路点包含未知字段：" + str(key)
			var error := pair_error(step.position, "路点")
			if not error.is_empty(): return error
			if step.look_at != null:
				error = pair_error(step.look_at, "观察目标")
				if not error.is_empty(): return error
			if step.level not in ["auto", "upper", "lower"]: return "层级需为 auto、upper 或 lower。"
			if step.get("movement", "run") not in ["run", "walk"]: return "移动方式需为 run 或 walk。"
			if (not step.wait is float and not step.wait is int) or not is_finite(float(step.wait)) or float(step.wait) < 0 or float(step.wait) > 30: return "等待需为 0—30 秒。"
	return ""

func save_tactic() -> void:
	if busy(): return
	var error := tactic_error(draft)
	if not error.is_empty(): report_notice(error, "error"); refresh(); return
	var value := draft.duplicate(true)
	var send_save := func(): send_command("save", {"tactic":value})
	if str(value.id) != original_id and library().get("tactics", []).any(func(row): return row.get("id") == value.id): request_confirmation("此 ID 已存在，覆盖已保存战术？", send_save)
	else: send_save.call()

func delete_tactic() -> void:
	if busy() or original_id.is_empty(): return
	var ident := original_id
	request_confirmation("删除这条已保存战术？生涯或比赛记录不受影响。", func(): send_command("delete", {"id":ident}))

func send_command(action: String, extra: Dictionary) -> void:
	if busy(): return
	var body := {"revision":int(CareerBridge.context.get("calendar", {}).get("revision", 0)), "map":map_code}
	for key in extra: body[key] = extra[key]
	var path := "/api/3d/tactics/" + action
	var sent := bool(command_sender.call(path, body.duplicate(true))) if command_sender.is_valid() else CareerBridge.command(path, body)
	if sent:
		pending_action = action
		pending_action_map = map_code
		pending_tactic = extra.get("tactic", {}).duplicate(true)
		report_notice({"save":"正在保存战术…", "delete":"正在删除…", "import":"正在导入…", "sync":"正在同步当前对局战术…"}.get(action, "正在处理…"), "progress", "tactics:%s:%s" % [action, map_code])
	else: report_notice("请求未发送，请等待当前操作结束后重试。", "error")
	refresh()

func choose_import() -> void:
	if not busy(): show_file_dialog(false, false)

func choose_export(all_saved: bool) -> void:
	if busy(): return
	if not all_saved:
		var error := tactic_error(draft)
		if not error.is_empty(): report_notice(error, "error"); refresh(); return
	show_file_dialog(true, all_saved)

func show_file_dialog(saving: bool, all_saved: bool) -> void:
	if is_instance_valid(file_dialog): file_dialog.queue_free()
	file_dialog = FileDialog.new()
	file_dialog.name = "TacticsFileDialog"
	file_dialog.access = FileDialog.ACCESS_FILESYSTEM
	file_dialog.file_mode = FileDialog.FILE_MODE_SAVE_FILE if saving else FileDialog.FILE_MODE_OPEN_FILE
	file_dialog.filters = PackedStringArray(["*.json ; JSON 战术"])
	file_dialog.title = "导出战术 JSON" if saving else "导入战术 JSON"
	file_dialog.use_native_dialog = true
	if saving: file_dialog.current_file = "%s-%s.json" % [map_code.trim_prefix("de_"), "tactics" if all_saved else str(draft.get("id", "tactic"))]
	host.add_child(file_dialog)
	file_dialog.file_selected.connect(func(path: String):
		file_dialog.hide()
		if saving: export_file(path, all_saved)
		else: import_file(path)
		file_dialog.queue_free()
	)
	file_dialog.canceled.connect(func(): file_dialog.queue_free())
	file_dialog.popup_centered(Vector2i(760, 500))

func export_value(all_saved: bool = false) -> Dictionary:
	if all_saved:
		var rows: Array = library().get("tactics", []).duplicate(true)
		for row in rows: coerce_tactic_integers(row)
		return {"schema_version":1, "map":map_code, "tactics":rows}
	return {"map":map_code, "tactic":draft.duplicate(true)}

func export_file(path: String, all_saved: bool = false) -> void:
	var file := FileAccess.open(path, FileAccess.WRITE)
	if file == null: report_notice("无法写入所选文件。", "error"); refresh(); return
	file.store_string(JSON.stringify(export_value(all_saved), "  ") + "\n")
	file.flush()
	var written := file.get_error() == OK
	file.close()
	if not written: report_notice("导出没有完成，请检查所选文件夹。", "error"); refresh(); return
	report_notice(("已导出全部战术：" if all_saved else "已导出草稿：") + path.get_file())
	refresh()

func import_file(path: String) -> void:
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null: report_notice("无法读取所选文件。", "error"); refresh(); return
	if file.get_length() > MAX_BYTES: report_notice("战术数据超过 256 KiB 大小限制。", "error"); refresh(); file.close(); return
	var source := file.get_as_text()
	file.close()
	import_json(source)

func import_json(source: String) -> void:
	if busy(): return
	if source.to_utf8_buffer().size() > MAX_BYTES: report_notice("战术数据超过 256 KiB 大小限制。", "error"); refresh(); return
	var parser := JSON.new()
	if parser.parse(source.trim_prefix("\ufeff")) != OK: report_notice("JSON 无效：" + parser.get_error_message(), "error"); refresh(); return
	var value = parser.data
	if not value is Dictionary: report_notice("导入内容需为一条战术或战术包。", "error"); refresh(); return
	if value.has("map") and value.map != map_code: report_notice("导入地图与当前地图不同，请先选择对应地图再导入。", "error"); refresh(); return
	var rows: Array = []
	if value.has("tactic"):
		for key in value:
			if key not in ["map", "tactic"]: report_notice("导入包包含未知字段。", "error"); refresh(); return
		rows.append(value.tactic)
	elif value.has("tactics"):
		if value.size() != 3 or value.get("schema_version") != 1 or value.get("map") != map_code or not value.tactics is Array or value.tactics.size() > 20: report_notice("战术包版本、地图或数量无效。", "error"); refresh(); return
		rows = value.tactics
	else: rows.append(value)
	var ids: Array = []
	for row in rows:
		var error := tactic_error(row)
		if not error.is_empty(): report_notice(error, "error"); refresh(); return
		if row.id in ids: report_notice("导入包包含重复 ID；未写入任何条目。", "error"); refresh(); return
		ids.append(row.id)
	var payload: Dictionary = value.duplicate(true)
	if payload.has("schema_version"): payload["schema_version"] = 1
	if payload.has("tactic"): coerce_tactic_integers(payload.tactic)
	elif payload.has("tactics"):
		for row in payload.tactics: coerce_tactic_integers(row)
	else: coerce_tactic_integers(payload)
	var send_import := func():
		pending_import_id = str(ids[0]) if not ids.is_empty() else ""
		send_command("import", {"value":payload})
	var check_collision := func():
		if library().get("tactics", []).any(func(row): return row.get("id") in ids): request_confirmation("导入包含同名 ID，会覆盖已有战术，继续？", send_import)
		else: send_import.call()
	discard_then(check_collision)

func copy_command() -> void:
	if not valid_id(str(draft.get("id", ""))):
		report_notice("先填写有效的战术 ID，再复制指令。", "error")
		refresh()
		return
	var command := "play " + str(draft.get("id", ""))
	var written := true
	if clipboard_writer.is_valid(): written = bool(clipboard_writer.call(command))
	else: DisplayServer.clipboard_set(command)
	var copied := str(clipboard_reader.call()) if clipboard_reader.is_valid() else DisplayServer.clipboard_get()
	if not written or copied != command:
		copied_command = ""
		report_notice("没有复制成功，请重试；也可以选中左侧指令手动复制。", "error")
		refresh_copy_caption()
		refresh()
		return
	copied_command = command
	copy_feedback_deadline_msec = Time.get_ticks_msec() + 2500
	var publication: Dictionary = library().get("publication", {})
	var advice := "草稿还没保存，先保存后再同步当前对局。" if dirty or original_id.is_empty() else str(publication.get("reason", "请确认已同步当前对局，再在准备阶段粘贴。"))
	report_notice("已复制：" + command + " · " + advice)
	refresh_copy_caption()
	if is_instance_valid(host) and host.is_inside_tree():
		host.get_tree().create_timer(2.6).timeout.connect(refresh_copy_caption)
	# A local clipboard operation does not rebuild the timeline, steal focus,
	# change scroll position, send a request, or imply that a draft was saved.
	if has_view(): controls.notice.text = notice

func sync_current_match() -> void:
	# Synchronise saved data, never publish an unsaved editor draft or reset a match.
	send_command("sync", {})

func refresh_publication() -> void:
	if not has_view(): return
	var published: Dictionary = library().get("publication", {})
	var ids: Array = published.get("published_ids", [])
	controls.publication.text = "本场战术快照（%s）：%s\n%s" % [str(published.get("prepared_map", "")), ", ".join(ids) if not ids.is_empty() else "无", str(published.get("reason", "请重新读取战术以确认同步状态。"))]

func fetch(show_feedback: bool = false) -> void:
	if CareerBridge.busy or not pending_path.is_empty() or not pending_action.is_empty(): return
	var path := "/api/3d/tactics?map=" + map_code.uri_encode()
	if CareerBridge._send(path, {}, false):
		pending_path = path
		pending_map = map_code
		notice = "正在读取战术…"
		pending_read_feedback = show_feedback
		if show_feedback: report_notice(notice, "progress", "tactics:read:" + map_code)
		refresh()

func finished(path: String, result: Dictionary) -> bool:
	if not path.begins_with("/api/3d/tactics"): return false
	var action := path.trim_prefix("/api/3d/tactics/") if path.begins_with("/api/3d/tactics/") else ""
	# A duplicate or foreign write result must not undo edits made after a
	# completed save/import, even when it carries the same map and tactic ID.
	if not action.is_empty() and action != pending_action: return true
	var target := str(result.get("map", pending_action_map if not action.is_empty() else pending_map))
	if target.is_empty(): target = map_code
	var owned_write := not action.is_empty() and action == pending_action
	var owned_read := path == pending_path and pending_read_feedback
	if path == pending_path: pending_path = ""
	if owned_read: pending_read_feedback = false
	if action == pending_action: pending_action = ""
	if result.get("ok", false):
		# Save/delete responses may omit radar metadata; retain the last valid projection.
		var merged: Dictionary = libraries.get(target, {}).duplicate(true)
		for key in result: merged[key] = result[key]
		for row in merged.get("tactics", []): coerce_tactic_integers(row)
		libraries[target] = merged
		if target == map_code:
			if action == "save":
				var saved: Dictionary = result.get("tactic", pending_tactic)
				if not saved.is_empty(): set_draft(saved)
				notice = str(result.get("reason", result.get("msg", "战术已保存。")))
			elif action == "delete": make_draft(); notice = str(result.get("reason", result.get("msg", "战术已删除。")))
			elif action == "import":
				for row in merged.get("tactics", []):
					if str(row.get("id", "")) == pending_import_id: set_draft(row); break
				notice = str(result.get("reason", result.get("msg", "导入已完成。")))
			elif action == "sync": notice = str(result.get("reason", result.get("msg", "同步状态已更新。")))
			else: notice = ""
	else: notice = str(result.get("reason", result.get("msg", "操作失败，请重试。")))
	if owned_write and result.get("ok", false) and not str(result.get("library_message", "")).is_empty():
		notice = str(result.library_message) + " · " + notice
	if owned_write or owned_read:
		var operation := "tactics:%s:%s" % ["read" if owned_read else action, target]
		if target != map_code:
			if is_instance_valid(host) and host.has_method("show_action_feedback"):
				host.show_action_feedback("", "success", 4.0, operation)
		elif owned_read and result.get("ok", false): report_notice("战术列表已更新。当前草稿保留。", "success", operation)
		else: report_notice(notice, "success" if result.get("ok", false) and (action != "sync" or bool(result.get("publication", {}).get("synced", false))) else "error", operation)
	if target == map_code:
		refresh_library_controls()
		# Reads never replace draft text or the current selection.
		refresh(not action.is_empty() and bool(result.get("ok", false)))
	return true
