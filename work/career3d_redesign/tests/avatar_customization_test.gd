extends Node
## Isolated rendering/UI fixture. It never launches or writes a real career.
const Avatar = preload("res://scripts/appearance_customization.gd")
const Player = preload("res://scripts/chicken_player.gd")
const Npc = preload("res://scripts/club_npc.gd")
var checks := 0
var failures: Array[String] = []
var editor = Avatar.new()
var actor
var neighbor
var submitted: Dictionary = {}

func _ready() -> void:
	call_deferred("run")

func check(ok: bool, text: String) -> void:
	checks += 1
	if not ok: failures.append(text)
	print("AVATAR_CHECK ", "PASS " if ok else "FAIL ", text)

func mesh(model: Node3D, name_text: String) -> MeshInstance3D:
	for node in model.find_children("*", "MeshInstance3D", true, false):
		if str(node.name).replace("_", " ").begins_with(name_text): return node
	return null

func send(path: String, body: Dictionary) -> bool:
	submitted = {"path":path, "body":body.duplicate(true)}
	return true

func run() -> void:
	CareerBridge.context = {"avatar":{"appearance":Avatar.DEFAULTS.duplicate()}, "calendar":{"revision":12}}
	CareerBridge.connected = true
	actor = Player.new()
	actor.enabled = false
	add_child(actor)
	neighbor = Npc.new()
	neighbor.definition = {"id":"avatar-test-npc", "color":"bb6677", "name":"外观隔离测试", "role":"rifle"}
	add_child(neighbor)
	neighbor.set_physics_process(false)
	actor.set_physics_process(false)
	check(actor.is_in_group("career_personal_avatar") and not neighbor.is_in_group("career_personal_avatar"), "NPC does not subscribe to personal avatar projection")
	var neighbor_head := mesh(neighbor.chicken_model, "Round chicken head")
	var neighbor_material := neighbor_head.get_active_material(0)
	var source_color: Color = (neighbor_material as StandardMaterial3D).albedo_color
	var panel := VBoxContainer.new()
	panel.size = Vector2(1050, 650)
	add_child(panel)
	editor.command_sender = send
	editor.render(self, panel)
	await get_tree().process_frame
	await get_tree().process_frame
	check(is_instance_valid(editor.preview_model), "live preview instantiates existing chicken model")
	check(panel.get_combined_minimum_size().x <= 1050, "appearance form fits workstation width")
	editor.set_value("body_color", "c7d7dd")
	editor.set_value("jersey_color", "913f51")
	editor.set_value("outfit", "natural")
	var actor_head := mesh(actor.chicken_model, "Round chicken head")
	var preview_head := mesh(editor.preview_model, "Round chicken head")
	check((actor_head.material_override as StandardMaterial3D).albedo_color.is_equal_approx(Color("c7d7dd")), "body colour reaches controllable actor")
	check((preview_head.material_override as StandardMaterial3D).albedo_color.is_equal_approx(Color("c7d7dd")), "preview and actor show matching colour")
	CareerBridge.context["date"] = "2026-10-02"
	CareerBridge.changed.emit()
	check(actor.appearance["body_color"] == "c7d7dd", "unrelated context refresh preserves unsaved live preview")
	check(neighbor_head.get_active_material(0) == neighbor_material and (neighbor_material as StandardMaterial3D).albedo_color.is_equal_approx(source_color), "personal recolour leaves NPC and imported material unchanged")
	check(not (actor.chicken_model.find_child("PlayerKit", true, false) as Node3D).visible and mesh(actor.chicken_model, "Cream belly bib").visible, "light outfit removes kit and reveals belly")
	editor.set_value("outfit", "jersey")
	check((actor.chicken_model.find_child("PlayerKit", true, false) as Node3D).visible and not mesh(actor.chicken_model, "Cream belly bib").visible, "jersey outfit restores kit and hides covered belly")
	check((mesh(actor.chicken_model, "Sleeveless team jersey").material_override as StandardMaterial3D).albedo_color.is_equal_approx(Color("913f51")), "jersey colour applies independently")
	editor.submit()
	check(submitted["path"] == "/api/3d/avatar" and submitted["body"]["revision"] == 12 and submitted["body"]["appearance"]["jersey_color"] == "913f51", "save sends appearance and revision to sole backend writer")
	check(editor.saving and editor.save_button.disabled and editor.save_button.text == "保存中……", "save immediately displays pending feedback")
	var saved: Dictionary = editor.values()
	CareerBridge.context["avatar"] = {"appearance":saved}
	check(editor.finished("/api/3d/avatar", {"ok":true, "avatar":{"appearance":saved}}), "avatar response belongs to module")
	check(not editor.saving and not editor.dirty and editor.message.contains("已保存"), "successful response clears draft state and reports saved")
	editor.set_value("body_color", "abcdef")
	editor.reset()
	check(editor.values()["body_color"] == "c7d7dd" and not editor.dirty, "reset restores saved appearance")
	CareerBridge.context["avatar"]["appearance"]["body_color"] = "aa7755"
	CareerBridge.changed.emit()
	check(actor.appearance["body_color"] == "aa7755" and neighbor.appearance.is_empty(), "context refresh reapplies player appearance only")
	editor.command_sender = func(_path, _body): return false
	CareerBridge.busy = true
	editor.submit()
	check(not editor.saving and editor.message.contains("还没有保存"), "rejected busy request leaves visible retry feedback")
	var normalization := Avatar.normalize({"outfit":"unknown", "body_color":"invalid", "trim_color":"#8899aaff"})
	check(normalization["outfit"] == "jersey" and normalization["body_color"] == Avatar.DEFAULTS["body_color"] and normalization["trim_color"] == "8899aa", "invalid or transparent colour cannot corrupt opaque avatar projection")
	var creation = Avatar.new()
	var existing_appearance: Dictionary = actor.appearance.duplicate(true)
	creation.creation_mode = true
	check(creation.values() == Avatar.DEFAULTS, "new career defaults do not inherit old career appearance before rendering")
	creation.command_sender = send
	var creation_panel := VBoxContainer.new()
	creation_panel.size = Vector2(1050, 650)
	add_child(creation_panel)
	creation.render(self, creation_panel)
	creation.set_value("body_color", "eeccdd")
	check(creation.values()["body_color"] == "eeccdd" and actor.appearance == existing_appearance, "new career preview does not modify existing actor")
	check(creation.save_button == null and creation_panel.find_child("AppearanceSave", true, false) == null, "new career draft offers no existing-avatar save action")
	var before_submission := submitted.duplicate(true)
	creation.submit()
	check(submitted == before_submission, "new career appearance cannot POST to existing career")
	creation.dirty = false
	preload("res://scripts/computer_ui.gd").clear(creation_panel)
	creation.render(self, creation_panel)
	check(creation.values()["body_color"] == "eeccdd", "clean embedded rerender preserves new career appearance draft")
	creation.reset()
	check(creation.values() == Avatar.DEFAULTS and actor.appearance == existing_appearance, "new career reset changes draft only")
	print("AVATAR_TEST_RESULT ", JSON.stringify({"checks":checks, "failures":failures}))
	get_tree().quit(0 if failures.is_empty() else 1)
