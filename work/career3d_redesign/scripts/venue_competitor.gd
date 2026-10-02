extends "res://scripts/chicken_player.gd"
## Stable display identity prevents roster guests inheriting the personal avatar.
var npc_id := ""
var display_name := ""
var team_name := ""

func setup_identity(row: Dictionary, team: String, color: Color) -> void:
	npc_id = str(row.get("player_id", row.get("id", "")))
	display_name = str(row.get("name", "")); team_name = team
	collision_layer = 0
	for mesh in visual.find_children("*", "MeshInstance3D", true, false):
		if str(mesh.name).replace("_", " ") == "Sleeveless team jersey":
			var jersey := StandardMaterial3D.new(); jersey.albedo_color = color; jersey.roughness = .82
			mesh.material_override = jersey
