extends SceneTree
## Offline asset builder. Run outside a Godot game project (no autoloads).
## godot --headless --path <empty folder> --script <this file> -- --manifest=<team-media.json> --output=<directory>

const BACKGROUND := Color("202428b3")
const DARK_MARK_KEYLINE := Color("b7c0ca")

func _initialize() -> void:
	var manifest := ""
	var output := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--manifest="): manifest = arg.trim_prefix("--manifest=")
		if arg.begins_with("--output="): output = arg.trim_prefix("--output=")
	if manifest.is_empty() or output.is_empty():
		fail("Supply --manifest and --output"); return
	var data = JSON.parse_string(FileAccess.get_file_as_string(manifest))
	if not data is Dictionary or not data.get("team_backgrounds") is Dictionary:
		fail("Invalid local team-media manifest"); return
	if DirAccess.make_dir_recursive_absolute(output) != OK:
		fail("Cannot create output directory"); return
	var keys := RegEx.create_from_string("[^a-z0-9]")
	var teams := {}
	for team in data.team_backgrounds:
		var row: Dictionary = data.team_backgrounds[team]
		var path: String = row.path
		if not path.is_absolute_path(): path = manifest.get_base_dir().path_join(path)
		if FileAccess.get_sha256(path) != str(row.sha256):
			fail("Changed source logo: " + team); return
		var image := Image.new()
		if image.load(path) != OK or image.get_used_rect().has_area() == false:
			fail("Cannot render logo: " + team); return
		image = image.get_region(image.get_used_rect())
		var ratio := 56.0 / maxf(image.get_width(), image.get_height())
		image.resize(maxi(1, roundi(image.get_width() * ratio)), maxi(1, roundi(image.get_height() * ratio)), Image.INTERPOLATE_LANCZOS)
		image.convert(Image.FORMAT_RGBA8)
		# One subdued, translucent HUD tile for every club. Dark marks get a
		# local one-pixel keyline, never a bright rectangle behind the whole logo.
		var luminance := 0.0
		var coverage := 0.0
		for y in image.get_height():
			for x in image.get_width():
				var p := image.get_pixel(x, y)
				luminance += (p.r * .2126 + p.g * .7152 + p.b * .0722) * p.a
				coverage += p.a
		var canvas := Image.create(64, 64, false, Image.FORMAT_RGBA8)
		canvas.fill(BACKGROUND)
		var origin := Vector2i((64 - image.get_width()) / 2, (64 - image.get_height()) / 2)
		var keyline := luminance / maxf(coverage, .001) < .23
		if keyline:
			# Dilate only the alpha silhouette; the original mark goes on top.
			# Build a single mask so overlapping edges do not accumulate opacity.
			var edge := Image.create(64, 64, false, Image.FORMAT_RGBA8)
			edge.fill(Color.TRANSPARENT)
			for y in image.get_height():
				for x in image.get_width():
					var alpha := image.get_pixel(x, y).a * .72
					if alpha <= 0: continue
					for dy in range(-1, 2):
						for dx in range(-1, 2):
							var point := origin + Vector2i(x + dx, y + dy)
							var tint := DARK_MARK_KEYLINE
							tint.a = maxf(alpha, edge.get_pixelv(point).a)
							edge.set_pixelv(point, tint)
			canvas.blend_rect(edge, Rect2i(Vector2i.ZERO, edge.get_size()), Vector2i.ZERO)
		canvas.blend_rect(image, Rect2i(Vector2i.ZERO, image.get_size()), origin)
		var key := keys.sub(str(team).to_lower(), "", true)
		if key.is_empty() or teams.has(key): fail("Duplicate/empty club key: " + team); return
		var filename := key + ".png"
		var target := output.path_join(filename)
		if canvas.save_png(target) != OK: fail("Cannot save " + filename); return
		var png := FileAccess.get_file_as_bytes(target)
		if png.is_empty() or png.size() > 16384: fail("PNG exceeds BotHider limit: " + team); return
		# Check the saved PNG, not just the in-memory canvas: export must keep
		# the translucent tile instead of flattening it onto white.
		var saved := Image.load_from_file(target)
		if saved == null or saved.get_size() != Vector2i(64, 64):
			fail("Invalid saved avatar: " + team); return
		for corner in [Vector2i(0, 0), Vector2i(63, 0), Vector2i(0, 63), Vector2i(63, 63)]:
			if saved.get_pixelv(corner).to_html() != BACKGROUND.to_html():
				fail("Avatar background lost alpha: " + team); return
		teams[key] = {"name": team, "file": filename, "sha256": FileAccess.get_sha256(target),
			"source": row.get("source", ""), "source_sha256": row.sha256, "dark_mark_keyline": keyline}
	var file := FileAccess.open(output.path_join("manifest.json"), FileAccess.WRITE)
	if file == null: fail("Cannot save manifest"); return
	file.store_string(JSON.stringify({"schema_version": 1, "size": 64,
		"appearance": "graphite_translucent_v1", "background": BACKGROUND.to_html(), "teams": teams}, "  ") + "\n")
	file.close()
	print("TEAM_LOGO_AVATARS_RESULT ", JSON.stringify({"count": teams.size(), "max_bytes": 16384, "ok": true}))
	quit(0)

func fail(reason: String) -> void:
	push_error(reason)
	quit(1)
