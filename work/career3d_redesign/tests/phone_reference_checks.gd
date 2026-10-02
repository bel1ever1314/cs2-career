extends RefCounted
## Observable UI constraints from the player's approved phone reference.
const Visuals = preload("res://scripts/phone_visuals.gd")

func glyphs(node: Node, kind: String) -> int:
	var count := 1 if node is Visuals.Glyph and node.kind == kind else 0
	for child in node.get_children():
		count += glyphs(child, kind)
	return count

func evaluate(phone) -> Array[Dictionary]:
	var checks: Array[Dictionary] = []
	var shell: StyleBoxFlat = phone.panel.get_theme_stylebox("panel")
	checks.append({"ok": shell.bg_color == Color("e3e7db") and shell.border_color == Color("bdc6b8"), "label": "phone uses the approved soft green shell"})
	checks.append({"ok": shell.corner_radius_top_left >= 30, "label": "phone shell keeps rounded reference proportions"})
	var glass = phone.panel.find_child("PhoneScreen", true, false)
	checks.append({"ok": glass != null and glass.get_theme_stylebox("panel").bg_color == Color("f8f4e9"), "label": "inner screen is cream, not blue-white"})
	var landscape = phone.content.find_child("HomeLandscape", true, false)
	checks.append({"ok": landscape != null and landscape.size.y >= 100 and landscape.mouse_filter == Control.MOUSE_FILTER_IGNORE, "label": "home includes the non-interactive hills and sun wallpaper"})
	var navigation = phone.panel.find_child("PhoneNavigation", true, false)
	checks.append({"ok": navigation != null and navigation.is_visible_in_tree() and navigation.size.y <= 64, "label": "return and home form a visible compact bottom navigation"})
	var status_icons = phone.panel.find_child("PhoneStatusIcons", true, false)
	checks.append({"ok": status_icons != null and glyphs(status_icons, "signal") == 1 and glyphs(status_icons, "wifi") == 1 and glyphs(status_icons, "battery") == 1, "label": "status bar has line signal, wifi and battery icons"})
	for app in phone.APPS:
		var tile: Button = phone.nav_buttons[app["id"]]
		checks.append({"ok": tile.text.is_empty() and glyphs(tile, str(app["id"])) == 1, "label": "app uses a line icon instead of a letter tile: " + str(app["name"])})
		checks.append({"ok": tile.size.x >= 56 and tile.size.y >= 56 and tile.size.x < 85 and tile.size.y < 85, "label": "app icon keeps a compact square touch area: " + str(app["name"])})
		checks.append({"ok": tile.get_theme_stylebox("normal").bg_color == Color("fffdf6"), "label": "app icon uses the approved paper surface: " + str(app["name"])})
	return checks
