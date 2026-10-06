extends Control
const Fragment = preload("res://scripts/position_preview.gd")
const UI = preload("res://scripts/phone_ui.gd")
const Fmt = preload("res://scripts/ui_format.gd")
var failures: Array[String] = []
var checks := 0
var intents: Array[String] = []

func check(value: bool, label: String) -> void:
	checks += 1
	if not value: failures.append(label)
	print("POSITION_CHECK ", "PASS " if value else "FAIL ", label)

func _ready() -> void:
	call_deferred("run")

func run() -> void:
	var bg := ColorRect.new(); bg.color = UI.PAPER
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT); add_child(bg)
	var margin := MarginContainer.new(); add_child(margin)
	margin.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	for side in ["left", "right", "top", "bottom"]: margin.add_theme_constant_override("margin_"+side, 28)
	var row := HBoxContainer.new(); margin.add_child(row); row.add_theme_constant_override("separation", 32)
	var stats := {"firepower":82.6, "entrying":79.1, "trading":80.3, "opening":77.4, "clutching":71.3, "sniping":61.5, "utility":84.2}
	var data := {"ability":81.3, "position_views":[{"role":"entry", "label":"突破手", "ability":82.4, "stats":stats.duplicate()}, {"role":"awp", "label":"主狙", "ability":66.2, "stats":stats.duplicate()}]}
	var before := JSON.stringify(data)
	for compact in [true, false]:
		var col := VBoxContainer.new(); row.add_child(col)
		col.custom_minimum_size.x = 330 if compact else 630
		UI.label(col, "手机 · 位置预览" if compact else "电脑 · 位置预览", 22)
		var fragment := Fragment.new()
		fragment.role_selected.connect(func(role): intents.append(role))
		var view := fragment.render(col, data, "entry", stats, "awp", {"entry":"突破手"}, "player", compact)
		view.set_meta("fragment", fragment)
		var selector: OptionButton = view.find_child("PositionPreviewSelector", true, false)
		check(selector.item_count == 3 and selector.selected == 2, "roles and current selection: " + str(compact))
		selector.item_selected.emit(1)
		check(intents.back() == "entry", "selection emits only a role intent: " + str(compact))
		check(JSON.stringify(data) == before, "page never mutates source data: " + str(compact))
	check(Fmt.signed(-.6) == "-0.6", "negative form keeps its sign and precision")
	check(Phone._stat_value(.847, 1, true) == Computer._percentage(.847), "same percentage on both devices")
	check(Phone._stat(1.25, 2) == Computer._number(1.25, 2), "same rating on both devices")
	check(Fmt.num(NAN) == "—" and Fmt.percent_fixed(null) == "—", "missing and invalid numeric values stay missing")
	await get_tree().process_frame
	await get_tree().process_frame
	check(row.get_combined_minimum_size().x <= margin.size.x, "shared fragments fit their host widths")
	if "--capture" in OS.get_cmdline_user_args():
		await RenderingServer.frame_post_draw
		DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path("res://temp"))
		get_viewport().get_texture().get_image().save_png("res://temp/refactor-position.png")
	print("POSITION_RESULT checks=", checks, " failures=", failures)
	get_tree().quit(0 if failures.is_empty() else 1)
