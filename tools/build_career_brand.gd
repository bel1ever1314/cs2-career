extends SceneTree
## Render the code-native wordmark once. No autoload, service or player save.
func _initialize() -> void:
	call_deferred("build")

func build() -> void:
	var source := ""
	var output := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--source="): source = arg.trim_prefix("--source=")
		if arg.begins_with("--output="): output = arg.trim_prefix("--output=")
	if source.is_empty() or output.is_empty(): quit(2); return
	var script := load(source) as Script
	var viewport := SubViewport.new()
	viewport.size = Vector2i(600, 300)
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	root.add_child(viewport)
	viewport.add_child(script.new())
	await process_frame
	await RenderingServer.frame_post_draw
	DirAccess.make_dir_recursive_absolute(output.get_base_dir())
	var result := viewport.get_texture().get_image().save_png(output)
	print("CAREER_BRAND_RESULT ", result)
	quit(0 if result == OK else 1)
