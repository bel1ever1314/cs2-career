extends RefCounted
## Remember real scrolling, not the temporary zero while a page is rebuilt.
## Page modules can still explicitly set page_scroll[page] = 0 for new content.
var host: Node
var rebuilding := false
var generation := 0

func attach(value: Node) -> void:
	host = value
	host.scroll.get_v_scroll_bar().value_changed.connect(_scrolled)

func _scrolled(_value: float) -> void:
	remember()

func remember() -> void:
	if not rebuilding:
		host.page_scroll[host.active_page] = host.scroll.scroll_vertical

func begin() -> void:
	generation += 1
	rebuilding = true

func restore() -> void:
	var ticket := generation
	var page: String = host.active_page
	var position := int(host.page_scroll.get(page, 0))
	# Containers need a layout pass; restore after deferred focus restoration too.
	await host.get_tree().process_frame
	await host.get_tree().process_frame
	if ticket != generation or page != host.active_page: return
	host.scroll.scroll_vertical = position
	rebuilding = false
