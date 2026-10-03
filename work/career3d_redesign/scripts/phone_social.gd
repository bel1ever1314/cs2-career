extends RefCounted
## Conversation bodies are saved server projections, never a second local ledger.
const UI = preload("res://scripts/phone_ui.gd")

static func contacts(context: Dictionary) -> Array[Dictionary]:
	var rows: Array[Dictionary] = []
	for row in context.get("contacts", []):
		if row is Dictionary:
			rows.append(row)
	return rows

static func render(phone) -> void:
	var rows := contacts(CareerBridge.context)
	if phone.selected_contact.is_empty():
		if not CareerBridge.context.get("stories", []).is_empty():
			phone._list_row(phone.content, "队内事件", "有件事想和你商量", phone._route.bind("stories"), "", "chat", true)
		for contact in rows:
			phone._list_row(phone.content, str(contact.get("name", "联系人")), Locale.field(contact, "preview"), phone._open_chat.bind(str(contact["id"])), str(contact.get("name", "")).left(1))
		if rows.is_empty():
			UI.label(phone.content, "联系人正在同步。", 14, UI.MUTED)
		return
	var contact: Dictionary = {}
	for row in rows:
		if str(row.get("id", "")) == phone.selected_contact:
			contact = row
			break
	if contact.is_empty():
		phone.selected_contact = ""
		render(phone)
		return
	phone.title.text = str(contact.get("name", "联系人"))
	UI.label(phone.content, "曾经的联系人" if contact.get("archived", false) else "聊天记录", 12, UI.MUTED)
	UI.space(phone.content, 14)
	var messages: Array = contact.get("messages", [])
	if messages.is_empty() and not str(contact.get("greeting", "")).is_empty():
		var greeting := UI.card(phone.content)
		UI.label(greeting, Locale.field(contact, "greeting"), 14)
	for line in messages:
		UI.space(phone.content, 10)
		var bubble := UI.card(phone.content)
		var shell := bubble.get_parent() as PanelContainer
		shell.set_meta("social_message_id", str(line.get("id", "")))
		if line.get("sender") == "you":
			shell.add_theme_stylebox_override("panel", UI.style(UI.MINT, 16, 18))
		elif line.get("sender") == "narrator":
			shell.add_theme_stylebox_override("panel", UI.style(UI.CREAM, 16, 18, UI.LINE))
		UI.label(bubble, str(line.get("name", "")) + " · " + str(line.get("date", "")), 12, UI.MUTED)
		# A full-height, wrapped body remains readable in the phone's outer scroll.
		var body := UI.label(bubble, Locale.field(line, "text"), 14)
		body.name = "SocialMessageBody"
		body.max_lines_visible = -1
		body.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	if not CareerBridge.context.get("stories", []).is_empty():
		UI.space(phone.content, 14)
		phone._button(phone.content, "继续处理队内事件", phone._route.bind("stories"), false)
	if not contact.get("replies", []).is_empty():
		UI.space(phone.content, 16)
		UI.label(phone.content, "快捷回复", 12, UI.MUTED)
		for reply in contact.get("replies", []):
			UI.space(phone.content, 8)
			phone._button(phone.content, Locale.field(reply, "label", "继续"), phone._reply.bind(contact, reply))

static func _find_message(node: Node, id: String) -> Control:
	if node is Control and str(node.get_meta("social_message_id", "")) == id:
		return node as Control
	for child in node.get_children():
		var found := _find_message(child, id)
		if found != null:
			return found
	return null

static func focus_message(phone, id: String) -> void:
	var bubble := _find_message(phone.content, id)
	if bubble != null:
		phone.scroll.scroll_vertical = maxi(0, int(bubble.get_global_rect().position.y - phone.content.get_global_rect().position.y) - 10)
