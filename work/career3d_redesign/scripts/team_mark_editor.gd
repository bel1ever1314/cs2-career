extends RefCounted
const UI = preload("res://scripts/computer_ui.gd")
const Images = preload("res://scripts/team_mark_image.gd")
const Visuals = preload("res://scripts/team_visuals.gd")
var host: Node
var dialog: FileDialog
var preview: Window

func render(parent: Node, data: Dictionary) -> void:
	var marks: Dictionary = data.get("marks", {})
	if not marks.get("allowed", false): return
	var card := UI.card(parent)
	card.name = "CustomTeamMark"
	UI.label(card, "自建战队队标", 19)
	var row := HBoxContainer.new()
	card.add_child(row)
	Visuals.badge(row, str(data.get("team", "")), 54)
	UI.label(row, "上传后用于队伍资料、场馆和比赛头像。也可以单独选择 CS2 内的头像。", 13, UI.MUTED)
	var actions := HFlowContainer.new()
	card.add_child(actions)
	var team_id := str(data.get("team_id", ""))
	host._button(actions, "上传队标（同时用于 CS2）", choose.bind("club", team_id), false).name = "UploadClubMark"
	host._button(actions, "单独设置 CS2 头像", choose.bind("avatar", team_id), false).name = "UploadCS2Mark"
	UI.label(card, "PNG / JPG / WebP，最大 8 MB；本地保存。CS2 内沿用灰黑半透明底，下一次开赛生效。", 12, UI.MUTED)

func choose(kind: String, team_id: String) -> void:
	if CareerBridge.busy or not CareerBridge.connected: return
	if is_instance_valid(dialog): dialog.queue_free()
	dialog = FileDialog.new()
	dialog.name = "TeamMarkFileDialog"
	dialog.access = FileDialog.ACCESS_FILESYSTEM
	dialog.file_mode = FileDialog.FILE_MODE_OPEN_FILE
	dialog.filters = PackedStringArray(["*.png,*.jpg,*.jpeg,*.webp ; 队标图片"])
	dialog.title = "选择战队队标" if kind == "club" else "选择 CS2 头像"
	dialog.use_native_dialog = true
	host.add_child(dialog)
	dialog.file_selected.connect(func(path: String):
		dialog.hide()
		load_selection(path, kind, team_id)
		dialog.queue_free()
	)
	dialog.canceled.connect(func(): dialog.queue_free())
	dialog.popup_centered(Vector2i(760, 500))

func error(message: String) -> void:
	host.notice = message
	CareerBridge.message = message
	CareerBridge.status_changed.emit()
	host._rebuild()

func load_selection(path: String, kind: String, team_id: String) -> void:
	if path.get_extension().to_lower() not in ["png", "jpg", "jpeg", "webp"]:
		error("请选择 PNG、JPG 或 WebP 图片。"); return
	var file := FileAccess.open(path, FileAccess.READ)
	if file == null or file.get_length() > 8 * 1024 * 1024:
		error("图片无法读取，或超过 8 MB。"); return
	file.close()
	var source := Image.new()
	if source.load(path) != OK or source.get_width() > 4096 or source.get_height() > 4096:
		error("图片无法读取，宽高请不超过 4096 像素。"); return
	var panel := Images.panel(source)
	var avatar := Images.avatar(source)
	if panel == null or avatar == null:
		error("这张图片完全透明，请选择有内容的队标。"); return
	var payload := {"team_id":team_id, "kind":kind, "avatar_png":Marshalls.raw_to_base64(avatar.save_png_to_buffer())}
	if kind == "club": payload["panel_png"] = Marshalls.raw_to_base64(panel.save_png_to_buffer())
	show_preview(panel, avatar, payload)

func show_preview(panel: Image, avatar: Image, payload: Dictionary) -> void:
	if is_instance_valid(preview): preview.queue_free()
	preview = Window.new()
	preview.name = "TeamMarkPreview"
	preview.title = "队标预览"
	preview.transient = true
	preview.exclusive = true
	preview.size = Vector2i(510, 350)
	host.add_child(preview)
	var background := ColorRect.new()
	background.color = UI.CREAM
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	preview.add_child(background)
	var column := VBoxContainer.new()
	column.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	column.offset_left = 20; column.offset_right = -20; column.offset_top = 20; column.offset_bottom = -20
	preview.add_child(column)
	UI.label(column, "确认使用这张队标？", 20)
	var row := HBoxContainer.new()
	row.size_flags_vertical = Control.SIZE_EXPAND_FILL
	column.add_child(row)
	for item in [{"label":"生涯队标" if payload.kind == "club" else "所选图片", "image":panel}, {"label":"CS2 顶部 / 计分板", "image":avatar}]:
		var box := VBoxContainer.new()
		box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(box)
		UI.label(box, item.label, 14)
		var art := TextureRect.new()
		art.texture = ImageTexture.create_from_image(item.image)
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		art.custom_minimum_size = Vector2(128, 150)
		box.add_child(art)
	UI.button(column, "保存队标", func():
		if CareerBridge.busy or not CareerBridge.connected: return
		var body := payload.duplicate(true)
		body["request_id"] = "team-mark-%d-%d" % [OS.get_process_id(), Time.get_ticks_usec()]
		host._device_command("/api/3d/controls/team-logo", body)
		preview.hide(); preview.queue_free()
	).name = "ConfirmTeamMark"
	UI.button(column, "取消", func(): preview.hide(); preview.queue_free())
	preview.close_requested.connect(func(): preview.hide(); preview.queue_free())
	preview.popup_centered()
