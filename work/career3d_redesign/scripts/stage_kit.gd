extends RefCounted
## Shared stage dressing for the LAN room, the awards hall and the Major:
## LED walls that render real 2D layouts, team logos, light strips, trusses,
## monitor content, confetti and an environment pass. Presentation only —
## nothing here reads or writes career state beyond the media lookup.
const Base = preload("res://scripts/phone_ui.gd")
const TeamVisuals = preload("res://scripts/team_visuals.gd")
const GOLD := Color("e2bd72")
const GOLD_SOFT := Color("f3dfb0")
const NIGHT := Color("0a111d")
const NIGHT_2 := Color("13213a")
const LED_TEXT := Color("f6efe0")
const LED_MUTED := Color("9fb0c4")
const TEAM_A := Color("4f86b0")
const TEAM_B := Color("d0844a")
static var _materials: Dictionary = {}
static var _logos: Dictionary = {}

# ---------------------------------------------------------------- materials

static func material(color: Color, glow: float = 0.0, roughness: float = 0.7, metallic: float = 0.0) -> StandardMaterial3D:
	var key := "%s:%s:%s:%s" % [color.to_html(), glow, roughness, metallic]
	if _materials.has(key): return _materials[key]
	var mat := StandardMaterial3D.new()
	mat.albedo_color = color
	mat.roughness = roughness
	mat.metallic = metallic
	if glow > 0.0:
		mat.emission_enabled = true
		mat.emission = color
		mat.emission_energy_multiplier = glow
	if color.a < 0.999: mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	_materials[key] = mat
	return mat

static func box(parent: Node3D, id: String, at: Vector3, size: Vector3, mat: Material) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = id
	var shape := BoxMesh.new(); shape.size = size
	mesh.mesh = shape
	mesh.position = at
	mesh.material_override = mat
	parent.add_child(mesh)
	return mesh

static func cylinder(parent: Node3D, id: String, at: Vector3, radius: float, height: float, mat: Material, segments: int = 16) -> MeshInstance3D:
	var mesh := MeshInstance3D.new()
	mesh.name = id
	var shape := CylinderMesh.new(); shape.top_radius = radius; shape.bottom_radius = radius
	shape.height = height; shape.radial_segments = segments; shape.rings = 1
	mesh.mesh = shape
	mesh.position = at
	mesh.material_override = mat
	parent.add_child(mesh)
	return mesh

## Thin emissive strip, for stage lips, desk edges and wall accents.
static func strip(parent: Node3D, id: String, at: Vector3, size: Vector3, color: Color, energy: float = 1.6) -> MeshInstance3D:
	var mesh := box(parent, id, at, size, material(color, energy, 0.4))
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mesh

## Square box truss along the x axis, built as ONE mesh (it has ~160 parts).
static func truss(parent: Node3D, id: String, center: Vector3, length: float, depth: float = 0.42, color: Color = Color("2a2f36")) -> MeshInstance3D:
	var parts: Array = []
	var half := depth * 0.5
	for y in [-half, half]:
		for z in [-half, half]:
			parts.append([Transform3D(Basis.IDENTITY, Vector3(0, y, z)), Vector3(length, 0.045, 0.045)])
	var bays := maxi(2, int(length / depth))
	var step := length / float(bays)
	for i in range(bays + 1):
		var x := -length * 0.5 + i * step
		for z in [-half, half]:
			parts.append([Transform3D(Basis.IDENTITY, Vector3(x, 0, z)), Vector3(0.03, depth, 0.03)])
		if i < bays:
			for z in [-half, half]:
				var angle := -atan2(step, depth) if i % 2 == 0 else atan2(step, depth)
				parts.append([Transform3D(Basis(Vector3.BACK, angle), Vector3(x + step * 0.5, 0, z)), Vector3(0.025, Vector2(step, depth).length(), 0.025)])
	var mesh := merged_boxes(parts)
	var node := MeshInstance3D.new(); node.name = id; node.mesh = mesh; node.position = center
	node.material_override = material(color, 0.0, 0.45, 0.6)
	node.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(node)
	return node

## Many boxes [Transform3D, size] baked into a single ArrayMesh surface.
static func merged_boxes(parts: Array) -> ArrayMesh:
	var tool := SurfaceTool.new()
	tool.begin(Mesh.PRIMITIVE_TRIANGLES)
	var unit := BoxMesh.new()
	for part in parts:
		var size: Vector3 = part[1]
		var at: Transform3D = part[0]
		unit.size = size
		tool.append_from(unit, 0, at)
	tool.generate_normals()
	return tool.commit()

## Bakes the direct MeshInstance3D children of `node` into one mesh with one
## surface per material (fewer draw calls). Label3Ds and other nodes stay.
static func merge_children(node: Node3D, keep: Array = []) -> MeshInstance3D:
	var tools: Dictionary = {}
	var materials_used: Dictionary = {}
	var merged: Array[Node] = []
	for child in node.get_children():
		if not child is MeshInstance3D or str(child.name) in keep: continue
		var instance := child as MeshInstance3D
		if instance.mesh == null or instance.material_override == null or instance.mesh.get_surface_count() != 1: continue
		var key := instance.material_override.get_instance_id()
		if not tools.has(key):
			var tool := SurfaceTool.new(); tool.begin(Mesh.PRIMITIVE_TRIANGLES)
			tools[key] = tool; materials_used[key] = instance.material_override
		(tools[key] as SurfaceTool).append_from(instance.mesh, 0, instance.transform)
		merged.append(instance)
	if merged.size() < 2: return null
	var mesh := ArrayMesh.new()
	for key in tools:
		var tool: SurfaceTool = tools[key]
		tool.commit(mesh)
		mesh.surface_set_material(mesh.get_surface_count() - 1, materials_used[key])
	for child in merged:
		node.remove_child(child); child.queue_free()
	var result := MeshInstance3D.new(); result.name = "MergedParts"; result.mesh = mesh
	node.add_child(result)
	return result

## Small moving-head fixture hanging under a truss; returns its lens position.
static func fixture(parent: Node3D, id: String, at: Vector3, aim: Vector3, lens: Color = Color("fff1d2")) -> Node3D:
	var head := Node3D.new(); head.name = id; head.position = at
	parent.add_child(head)
	var body := material(Color("1b1f25"), 0.0, 0.5, 0.4)
	box(head, "Yoke", Vector3(0, -0.08, 0), Vector3(0.26, 0.05, 0.12), body)
	cylinder(head, "Can", Vector3(0, -0.22, 0), 0.1, 0.24, body, 12)
	cylinder(head, "Lens", Vector3(0, -0.345, 0), 0.075, 0.012, material(lens, 2.2, 0.2), 12)
	var direction := (aim - at).normalized()
	if direction.length() > 0.01:
		var down := Vector3.DOWN
		var axis := down.cross(direction)
		if axis.length() > 0.001: head.basis = Basis(axis.normalized(), down.angle_to(direction))
	var merged := merge_children(head)
	if merged: merged.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return head

# ---------------------------------------------------------------- LED walls

## A flat LED wall showing a 2D Control tree rendered in a SubViewport.
## Returns the Control root to fill; it carries "screen_mesh" and "viewport" metas.
static func led_screen(parent: Node3D, id: String, at: Vector3, size: Vector2, pixels: Vector2i, angle: float = 0.0, brightness: float = 1.0, transparent: bool = false) -> Control:
	var viewport := SubViewport.new()
	viewport.name = id + "Pixels"
	viewport.size = pixels
	viewport.disable_3d = true
	viewport.transparent_bg = transparent
	viewport.gui_disable_input = true
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	parent.add_child(viewport)
	var root := Control.new()
	root.name = id + "Layout"
	root.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.size = Vector2(pixels)
	viewport.add_child(root)
	if not transparent:
		var back := ColorRect.new()
		back.name = "LedBackground"
		back.color = NIGHT
		back.mouse_filter = Control.MOUSE_FILTER_IGNORE
		back.size = Vector2(pixels)
		root.add_child(back)
	var mesh := MeshInstance3D.new()
	mesh.name = id
	var quad := QuadMesh.new(); quad.size = size
	mesh.mesh = quad
	mesh.position = at
	mesh.rotation.y = angle
	mesh.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	var mat := StandardMaterial3D.new()
	mat.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	mat.albedo_texture = viewport.get_texture()
	mat.albedo_color = Color(brightness, brightness, brightness, 1.0)
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR
	if transparent: mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mesh.material_override = mat
	parent.add_child(mesh)
	root.set_meta("screen_mesh", mesh)
	root.set_meta("viewport", viewport)
	refresh(root, 1.0)
	return root

## LED walls only re-render while their content is changing (fades, new
## layout); afterwards the last frame is kept. Call after drawing new content.
static func refresh(root: Control, seconds: float = 0.6) -> void:
	if not is_instance_valid(root) or not root.has_meta("viewport"): return
	var viewport: SubViewport = root.get_meta("viewport")
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	var token := int(viewport.get_meta("refresh_token", 0)) + 1
	viewport.set_meta("refresh_token", token)
	var tree := Engine.get_main_loop() as SceneTree
	if tree == null: return
	tree.create_timer(seconds, true).timeout.connect(func():
		if is_instance_valid(viewport) and int(viewport.get_meta("refresh_token", 0)) == token:
			viewport.render_target_update_mode = SubViewport.UPDATE_ONCE)

static func clear(root: Control) -> void:
	for child in root.get_children():
		if str(child.name) == "LedBackground": continue
		root.remove_child(child)
		child.queue_free()

## Full-size layer inside an LED root, with optional padding.
static func layer(root: Control, padding: Vector4 = Vector4.ZERO) -> Control:
	var node := Control.new()
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	node.position = Vector2(padding.x, padding.y)
	node.size = root.size - Vector2(padding.x + padding.z, padding.y + padding.w)
	root.add_child(node)
	return node

static func gradient(root: Control, top: Color, bottom: Color, at: Rect2 = Rect2()) -> TextureRect:
	var grad := Gradient.new()
	grad.set_color(0, top); grad.set_color(1, bottom)
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill_from = Vector2(0.5, 0.0); tex.fill_to = Vector2(0.5, 1.0)
	tex.width = 8; tex.height = 128
	var rect := TextureRect.new()
	rect.texture = tex
	rect.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	rect.stretch_mode = TextureRect.STRETCH_SCALE
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	if at.size == Vector2.ZERO: at = Rect2(Vector2.ZERO, root.size)
	rect.position = at.position; rect.size = at.size
	root.add_child(rect)
	return rect

static func rect(root: Control, at: Rect2, color: Color) -> ColorRect:
	var node := ColorRect.new()
	node.color = color
	node.position = at.position; node.size = at.size
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	root.add_child(node)
	return node

static func panel(root: Node, color: Color, radius: int = 18, border: Color = Color.TRANSPARENT, padding: int = 18) -> PanelContainer:
	var node := PanelContainer.new()
	node.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(radius)
	if border.a > 0.0:
		style.set_border_width_all(2)
		style.border_color = border
	style.content_margin_left = padding; style.content_margin_right = padding
	style.content_margin_top = padding * 0.6; style.content_margin_bottom = padding * 0.6
	node.add_theme_stylebox_override("panel", style)
	root.add_child(node)
	return node

static func text(parent: Node, value: String, size: int, color: Color = LED_TEXT, align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_CENTER) -> Label:
	var label := Label.new()
	label.text = value
	label.add_theme_font_override("font", Base.font())
	label.add_theme_font_size_override("font_size", size)
	label.add_theme_color_override("font_color", color)
	label.horizontal_alignment = align
	label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	parent.add_child(label)
	return label

## Text placed at an absolute rectangle inside an LED layout.
static func text_at(parent: Control, value: String, size: int, at: Rect2, color: Color = LED_TEXT, align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_CENTER) -> Label:
	var label := text(parent, value, size, color, align)
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.position = at.position; label.size = at.size
	label.clip_text = true
	return label

## Team mark on a cream tile so dark and light logos both read on an LED wall.
## Teams without local media get a monogram tile instead of an empty gap.
static func logo_tile(parent: Node, team: String, size: float, tint: Color = Color(0.97, 0.94, 0.88, 0.96)) -> PanelContainer:
	var tile := PanelContainer.new()
	tile.name = "TeamLogoTile"
	tile.mouse_filter = Control.MOUSE_FILTER_IGNORE
	tile.custom_minimum_size = Vector2(size, size)
	tile.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	tile.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	var style := StyleBoxFlat.new()
	style.bg_color = tint
	style.set_corner_radius_all(int(size * 0.22))
	var pad := int(size * 0.12)
	style.content_margin_left = pad; style.content_margin_right = pad
	style.content_margin_top = pad; style.content_margin_bottom = pad
	tile.add_theme_stylebox_override("panel", style)
	parent.add_child(tile)
	var mark := logo_texture(team, int(size * 1.5))
	if mark and bool(mark.get_meta("light_mark", false)):
		# White/pale marks would vanish on cream; give them a deep tile instead.
		style.bg_color = Color("1d2638")
	if mark:
		var art := TextureRect.new()
		art.texture = mark
		art.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
		art.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
		art.mouse_filter = Control.MOUSE_FILTER_IGNORE
		tile.add_child(art)
		tile.set_meta("team_logo", team)
	else:
		var letters := monogram(team)
		var label := text(tile, letters, int(size * (0.42 if letters.length() <= 2 else 0.3)), Color("22342b"))
		label.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	return tile

static func monogram(team: String) -> String:
	var words := team.strip_edges().split(" ", false)
	if words.is_empty(): return "?"
	if words.size() == 1: return words[0].substr(0, 3).to_upper()
	var out := ""
	for word in words.slice(0, 3): out += word.substr(0, 1).to_upper()
	return out

## Team mark rasterised near the requested pixel size (SVGs are re-rendered
## crisply instead of stretching their tiny default raster).
static func logo_texture(team: String, pixels: int = 256) -> Texture2D:
	if team.strip_edges().is_empty(): return null
	var paths: Dictionary = CareerBridge.context.get("media", {}).get("team_backgrounds", {})
	var path := str(paths.get(team, ""))
	if path.is_empty():
		for known in paths:
			if str(known).to_lower() == team.to_lower():
				path = str(paths[known]); break
	if path.is_empty() or not FileAccess.file_exists(path): return null
	var key := path + "@" + str(pixels)
	if _logos.has(key): return _logos[key]
	_logos[key] = null
	var image := Image.new()
	if path.get_extension().to_lower() == "svg":
		var bytes := FileAccess.get_file_as_bytes(path)
		var probe := Image.new()
		if probe.load_svg_from_buffer(bytes, 1.0) != OK: return null
		var longest := maxi(probe.get_width(), probe.get_height())
		var scale := clampf(float(pixels) / maxf(1.0, float(longest)), 0.25, 16.0)
		if image.load_svg_from_buffer(bytes, scale) != OK: return null
	else:
		if image.load(path) != OK: return null
		var longest := maxi(image.get_width(), image.get_height())
		if longest > pixels * 2:
			var factor := float(pixels * 2) / float(longest)
			image.resize(maxi(1, int(image.get_width() * factor)), maxi(1, int(image.get_height() * factor)), Image.INTERPOLATE_LANCZOS)
	var light := TeamVisuals._needs_backdrop(image)
	image.generate_mipmaps()
	var texture := ImageTexture.create_from_image(image)
	texture.set_meta("light_mark", light)
	_logos[key] = texture
	return texture

# ---------------------------------------------------------------- content

## A small in-game frame for a LAN monitor: sky, a map silhouette, HUD bars.
## Deterministic per seed so each seat shows a different but stable view.
static func game_frame(seed_value: int, warm: bool) -> ImageTexture:
	var w := 192; var h := 108
	var image := Image.create(w, h, false, Image.FORMAT_RGBA8)
	var rng := RandomNumberGenerator.new(); rng.seed = seed_value
	var sky_top := Color("7fa7c9") if not warm else Color("d9b48a")
	var sky_low := Color("c9d9e0") if not warm else Color("efd9b4")
	for y in range(h):
		var t := float(y) / float(h)
		var row := sky_top.lerp(sky_low, clampf(t * 1.8, 0, 1))
		if y > h * 0.55: row = Color("b99a6c").lerp(Color("8c714e"), (t - 0.55) * 2.2) if warm else Color("9a9a86").lerp(Color("6d7068"), (t - 0.55) * 2.2)
		image.fill_rect(Rect2i(0, y, w, 1), row)
	# Map blocks: walls, crates and a doorway, all in muted desert/stone tones.
	var tones := [Color("c8a978"), Color("b59366"), Color("a48a64"), Color("8f7a5b")] if warm else [Color("aeb4a8"), Color("979f96"), Color("838d88"), Color("6f7a78")]
	var x := -rng.randi_range(0, 30)
	while x < w:
		var bw := rng.randi_range(18, 46); var bh := rng.randi_range(18, 44)
		image.fill_rect(Rect2i(x, int(h * 0.58) - bh, bw, bh), tones[rng.randi_range(0, tones.size() - 1)])
		if rng.randf() < 0.35:
			image.fill_rect(Rect2i(x + bw / 3, int(h * 0.58) - bh / 2, bw / 3, bh / 2), Color("3b342b"))
		x += bw + rng.randi_range(0, 14)
	var crate := Color("9a6b3e")
	image.fill_rect(Rect2i(rng.randi_range(40, 120), int(h * 0.58) - 6, 22, 22), crate)
	# Weapon silhouette bottom-right.
	image.fill_rect(Rect2i(w - 70, h - 26, 56, 8), Color("2b2f33"))
	image.fill_rect(Rect2i(w - 40, h - 20, 12, 20), Color("23272b"))
	# HUD: top score strip, bottom health/ammo, crosshair.
	image.fill_rect(Rect2i(w / 2 - 30, 2, 60, 9), Color(0.05, 0.07, 0.09, 0.85))
	image.fill_rect(Rect2i(w / 2 - 28, 4, 10, 5), Color("6fa7d6"))
	image.fill_rect(Rect2i(w / 2 + 18, 4, 10, 5), Color("e2a45a"))
	image.fill_rect(Rect2i(4, h - 10, 34, 6), Color(0.05, 0.07, 0.09, 0.8))
	image.fill_rect(Rect2i(5, h - 9, rng.randi_range(14, 32), 4), Color("9fd27f"))
	image.fill_rect(Rect2i(w - 36, h - 10, 32, 6), Color(0.05, 0.07, 0.09, 0.8))
	var cross := Color("6dff8a")
	image.fill_rect(Rect2i(w / 2 - 5, h / 2, 3, 1), cross); image.fill_rect(Rect2i(w / 2 + 3, h / 2, 3, 1), cross)
	image.fill_rect(Rect2i(w / 2, h / 2 - 5, 1, 3), cross); image.fill_rect(Rect2i(w / 2, h / 2 + 3, 1, 3), cross)
	# Minimap top-left.
	image.fill_rect(Rect2i(3, 3, 26, 26), Color(0.06, 0.08, 0.1, 0.85))
	image.fill_rect(Rect2i(6, 12, 20, 3), Color("8d927f")); image.fill_rect(Rect2i(14, 6, 3, 20), Color("8d927f"))
	image.fill_rect(Rect2i(rng.randi_range(7, 22), rng.randi_range(7, 22), 2, 2), Color("ffe58a"))
	image.generate_mipmaps()
	return ImageTexture.create_from_image(image)

static func screen_material(texture: Texture2D, energy: float = 1.1) -> StandardMaterial3D:
	var mat := StandardMaterial3D.new()
	mat.albedo_texture = texture
	mat.albedo_color = Color(0.18, 0.18, 0.18)
	mat.roughness = 0.25
	mat.emission_enabled = true
	mat.emission_texture = texture
	mat.emission_operator = BaseMaterial3D.EMISSION_OP_MULTIPLY
	mat.emission = Color.WHITE
	mat.emission_energy_multiplier = energy
	mat.texture_filter = BaseMaterial3D.TEXTURE_FILTER_LINEAR_WITH_MIPMAPS
	return mat

## One-shot gold/white confetti burst over an area (call restart() to fire).
static func confetti(parent: Node3D, at: Vector3, extents: Vector3) -> CPUParticles3D:
	var particles := CPUParticles3D.new()
	particles.name = "Confetti"
	particles.position = at
	particles.emitting = false
	particles.one_shot = true
	particles.amount = 320
	particles.lifetime = 6.0
	particles.explosiveness = 0.82
	particles.emission_shape = CPUParticles3D.EMISSION_SHAPE_BOX
	particles.emission_box_extents = extents
	particles.direction = Vector3(0, 1, 0)
	particles.spread = 70.0
	particles.initial_velocity_min = 0.6
	particles.initial_velocity_max = 2.2
	particles.gravity = Vector3(0, -1.6, 0)
	particles.damping_min = 0.9
	particles.damping_max = 1.6
	particles.angle_min = 0.0; particles.angle_max = 360.0
	particles.angular_velocity_min = -280.0; particles.angular_velocity_max = 280.0
	particles.scale_amount_min = 0.7; particles.scale_amount_max = 1.25
	var colours := Gradient.new()
	colours.offsets = PackedFloat32Array([0.0, 0.3, 0.55, 0.8, 1.0])
	colours.colors = PackedColorArray([Color("f1cf7c"), Color("fff6dc"), Color("e0a843"), Color("f4f1ea"), Color("c99a46")])
	particles.color_initial_ramp = colours
	var quad := QuadMesh.new(); quad.size = Vector2(0.045, 0.07)
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.cull_mode = BaseMaterial3D.CULL_DISABLED
	mat.roughness = 0.35
	mat.metallic = 0.5
	mat.emission_enabled = true
	mat.emission = Color(0.35, 0.28, 0.14)
	quad.material = mat
	particles.mesh = quad
	particles.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	parent.add_child(particles)
	return particles

# ---------------------------------------------------------------- environment

## Venue look: soft bloom on emissive trims, gentle contrast, and on
## Forward+ also screen-space reflections and a faint haze for light beams.
## The compatibility renderer silently ignores the Forward+-only parts.
static func polish(env: Environment, haze: float = 0.0, reflections: bool = true) -> void:
	env.tonemap_mode = Environment.TONE_MAPPER_ACES
	env.tonemap_exposure = 1.0
	env.glow_enabled = true
	env.glow_intensity = 0.6
	env.glow_strength = 0.95
	env.glow_bloom = 0.03
	env.glow_hdr_threshold = 0.9
	env.set_glow_level(0, 0.0)
	env.set_glow_level(1, 0.6)
	env.set_glow_level(2, 1.0)
	env.set_glow_level(3, 0.7)
	env.set_glow_level(4, 0.35)
	env.adjustment_enabled = true
	env.adjustment_contrast = 1.06
	env.adjustment_saturation = 1.06
	env.ssr_enabled = reflections
	env.ssr_max_steps = 56
	env.ssr_fade_in = 0.12
	env.ssr_fade_out = 2.0
	env.ssr_depth_tolerance = 0.25
	if haze > 0.0:
		env.volumetric_fog_enabled = true
		env.volumetric_fog_density = haze
		env.volumetric_fog_albedo = Color(0.9, 0.86, 0.8)
		env.volumetric_fog_anisotropy = 0.55
		env.volumetric_fog_length = 32.0
		env.volumetric_fog_ambient_inject = 0.0
		env.volumetric_fog_sky_affect = 0.0

## Lights that should draw visible beams in the haze; the rest stay out of it.
static func beam(light: Light3D, amount: float = 1.0) -> void:
	light.light_volumetric_fog_energy = amount
