extends RefCounted
## One named roster suggestion, not ownership of the club.
const UI = preload("res://scripts/computer_ui.gd")
var host: Node
var owner_ref: WeakRef
var business:
	get: return owner_ref.get_ref()
var pending: Dictionary = {}

func attach(device: Node, owner) -> void:
	host = device
	owner_ref = weakref(owner)

static func allowed(data: Dictionary, replace_id: String) -> bool:
	if not data.get("club_allowed", false): return false
	var value: Dictionary = data.get("recruitment", {})
	if not value.get("required", false): return true
	var grant = value.get("grant")
	return grant is Dictionary and str(grant.get("replace_id", "")) == replace_id

func render(data: Dictionary) -> void:
	var value: Dictionary = data.get("recruitment", {})
	if not value.get("required", false): return
	var card := UI.card(host.content)
	card.name = "ClubRecruitmentPanel"
	UI.label(card, "与俱乐部商量换人", 20)
	UI.label(card, "效力越久、实力越突出，你的建议越有分量；俱乐部也会考虑队友的实力和近期表现。", 13, UI.MUTED)
	UI.label(card, "商量不收费，每 14 个游戏日一次。获批只针对选中的队友，签约成功后使用；谈判未成则保留。", 13, UI.MUTED)
	var grant = value.get("grant")
	if grant is Dictionary and not grant.is_empty():
		UI.label(card, "已获批准：替换 %s，可完成一次引援。" % grant.get("name", ""), 16, UI.GREEN)
		if str(grant.get("replace_id", "")) != business.replace_id:
			host._button(card, "选择已获批的队友", func():
				business.replace_id = str(grant.replace_id)
				business.pending_purchase.clear()
				host._rebuild(), false).name = "RecruitmentUseGrant"
		return
	var selected: Dictionary = {}
	for candidate in value.get("candidates", []):
		if str(candidate.get("replace_id", "")) == business.replace_id: selected = candidate
	if selected.is_empty(): return
	UI.label(card, "已效力 %d 天 · 你的实力 %.1f" % [int(value.get("tenure_days", 0)), float(value.get("ability", 0))], 14)
	UI.label(card, "%s · 实力 %.1f · 商量成功率 %.0f%%" % [selected.get("name", ""), float(selected.get("ability", 0)), float(selected.get("chance", 0)) * 100], 16)
	if selected.get("recent_rating") != null:
		UI.label(card, "近 30 天 %d 图 · Rating %.2f" % [int(selected.get("recent_maps", 0)), float(selected.recent_rating)], 14, UI.MUTED)
	else:
		UI.label(card, "近期暂无完整战绩，不按表现加减成功率。", 13, UI.MUTED)
	UI.label(card, "成功率影响：效力时间 %+.0f%% · 你的实力 %+.0f%% · 队友实力 %+.0f%% · 近期表现 %+.0f%%" % [float(selected.get("tenure_bonus", 0))*100, float(selected.get("ability_bonus", 0))*100, float(selected.get("teammate_modifier", 0))*100, float(selected.get("form_modifier", 0))*100], 12, UI.MUTED)
	if float(selected.get("form_modifier", 0)) < 0:
		UI.label(card, "这名队友近期发挥出色，俱乐部更希望留住他。", 13, UI.MUTED)
	var last = value.get("last_attempt")
	if last is Dictionary and not last.get("approved", false):
		UI.label(card, "上次商量：俱乐部希望暂时保留 %s。" % last.get("name", ""), 13, UI.MUTED)
	var reason := str(value.get("reason", ""))
	if not reason.is_empty(): UI.label(card, reason, 13, UI.MUTED)
	if pending.get("quote_id") == selected.get("quote_id"):
		UI.label(card, "确认向俱乐部提出调整 %s 的建议？这次商量后需等待 14 个游戏日。" % selected.get("name", ""), 14)
		var confirm: Button = host._button(card, "确认商量", func(): host._device_command("/api/3d/transfers/discuss", pending.duplicate(true)))
		confirm.name = "RecruitmentConfirm"
		confirm.disabled = not value.get("available", false)
		UI.primary(confirm)
		host._button(card, "取消", func(): pending.clear(); host._rebuild(), false)
	else:
		var propose: Button = host._button(card, "提出换人建议", func():
			pending = {"replace_id":selected.replace_id, "quote_id":selected.quote_id}
			host._rebuild(), false)
		propose.name = "RecruitmentPropose"
		propose.disabled = not value.get("available", false)

func finished(path: String, result: Dictionary) -> void:
	if path == "/api/3d/transfers/discuss" and result.get("ok", false): pending.clear()
