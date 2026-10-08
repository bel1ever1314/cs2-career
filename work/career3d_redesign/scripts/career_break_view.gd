extends RefCounted
## Read-only break agenda. Choices use the same guarded story command as the phone.
const UI = preload("res://scripts/computer_ui.gd")

static func mount(parent: Node, owner) -> void:
	var state: Dictionary = owner.quick_state()
	var queue: Array = CareerBridge.context.get("stories", [])
	var reason := str(state.get("block_reason", ""))
	var card := UI.card(parent)
	card.name = "CareerBreakAgenda"
	UI.label(card, "Major 休赛期 · 待办清单", 20)
	UI.label(card, "处理完必须决定的事项后即可继续。属性点可以留到以后，不要求全部花完。", 13, UI.MUTED)
	if not queue.is_empty():
		UI.label(card, "待处理事件 · %d 项" % queue.size(), 17, UI.AMBER)
		var story: Dictionary = queue[0]
		UI.label(card, Locale.field(story, "title", Locale.source("page.stories")), 18)
		UI.label(card, Locale.field(story, "text"), 14)
		for choice in story.get("choices", []):
			owner.host._button(card, Locale.field(choice, "label", Locale.source("device.choose")),
				owner.host._command.bind("/api/3d/story", {"id":story["id"], "choice":choice["id"]}))
		if story.get("choices", []).is_empty():
			owner.host._button(card, Locale.source("device.got_it"),
				owner.host._command.bind("/api/3d/story", {"id":story["id"], "choice":""}))
		for i in range(1, queue.size()):
			UI.label(card, "%d. %s" % [i + 1, Locale.field(queue[i], "title", Locale.source("page.stories"))], 13, UI.MUTED)
	elif not reason.is_empty():
		UI.label(card, reason, 15, UI.AMBER)
		owner.host._button(card, "查看待办事项", owner.pace.open_pending, false)
	else:
		UI.label(card, "没有必须处理的事项，可以结束休赛停留。", 15, UI.GREEN)
	var optional := UI.card(parent)
	optional.name = "CareerBreakOptional"
	UI.label(optional, "可选安排", 17)
	UI.label(optional, "剩余属性点：%s · 未使用点数继续保留" % str(CareerBridge.context.get("attr_points", 0)), 14)
	owner.host._button(optional, "分配属性点", owner.host._navigate.bind("profile"), false)
	UI.label(optional, "日常自动训练维持地图熟练度；也可以离开电脑，自由活动。", 13, UI.MUTED)
	var finish = owner.host._button(parent, "结束休赛停留", owner.resume_quick)
	finish.name = "EndCareerBreak"
	finish.disabled = finish.disabled or not queue.is_empty() or not reason.is_empty()
