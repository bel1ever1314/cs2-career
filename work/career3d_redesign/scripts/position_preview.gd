extends RefCounted
## Read-only page fragment. Owns its widgets and emits an intent, never touches
## Phone/Computer navigation or CareerBridge state.
signal role_selected(role: String)
const UI = preload("res://scripts/phone_ui.gd")
const DesktopUI = preload("res://scripts/computer_ui.gd")
const Fmt = preload("res://scripts/ui_format.gd")
const AXES = {"firepower":"火力", "entrying":"突破", "trading":"补枪", "opening":"首杀", "clutching":"残局", "sniping":"狙击", "utility":"道具"}

func render(parent: Node, data: Dictionary, current_role: String, current_stats: Dictionary, selected: String, role_labels: Dictionary, page: String, compact: bool) -> Control:
	var raw: Variant = data.get("position_views", [])
	var views: Array = raw if raw is Array else []
	if views.is_empty(): return null
	var shown := {"ability":data.get("ability"), "stats":current_stats}
	var box := UI.card(parent)
	box.name = ("PhonePositionPreview_" if compact else "ComputerPositionPreview_") + page
	UI.label(box, "位置能力", 15 if compact else 18)
	var selector := OptionButton.new()
	if not compact:
		DesktopUI.dark_options(selector)
	else:
		UI.decorate_button(selector)
		var popup := selector.get_popup()
		popup.add_theme_stylebox_override("panel", UI.style(UI.PAPER, 8, 9, UI.LINE))
		popup.add_theme_font_override("font", UI.font())
		popup.add_theme_font_size_override("font_size", 14)
		popup.add_theme_color_override("font_color", UI.INK)
		popup.add_theme_color_override("font_hover_color", UI.INK)
		popup.add_theme_stylebox_override("hover", UI.style(UI.MINT, 6, 5))
	selector.name = "PositionPreviewSelector"
	selector.custom_minimum_size = Vector2(0 if compact else 220, 36)
	if compact: selector.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	selector.add_item("当前位置 · " + str(role_labels.get(current_role, current_role)))
	selector.set_item_metadata(0, "")
	box.add_child(selector)
	for view in views:
		if not view is Dictionary: continue
		selector.add_item(str(view.get("label", view.get("role", ""))))
		var index := selector.item_count - 1
		selector.set_item_metadata(index, str(view.get("role", "")))
		if str(view.get("role", "")) == selected:
			selector.select(index)
			shown = view
	selector.item_selected.connect(func(index: int): role_selected.emit(str(selector.get_item_metadata(index))))
	_row(box, "位置适配能力", Fmt.num(shown.get("ability"), 2), compact, 16)
	var stats: Dictionary = shown.get("stats", {}) if shown.get("stats") is Dictionary else {}
	for axis in AXES:
		_row(box, AXES[axis], Fmt.num(stats.get(axis), 1), compact, 13)
	UI.label(box, "切换预览不会改变阵容。", 12, UI.MUTED)
	return box

func _row(parent: Node, title: String, value: String, compact: bool, size: int) -> void:
	var row := HBoxContainer.new()
	parent.add_child(row)
	UI.label(row, title, size if compact else 15, UI.MUTED).size_flags_horizontal = Control.SIZE_EXPAND_FILL
	UI.label(row, value, size if compact else 15)
