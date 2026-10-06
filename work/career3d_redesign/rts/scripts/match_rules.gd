extends RefCounted
## Generated rule data comes from cs2career/data/match_rules.json.
const PATH := "res://rts/data/match_rules.json"

static func definition() -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(PATH))

static func decided(a: int, b: int, overtime: bool = true) -> bool:
	var rules := definition()
	var half := int(rules.regulation_half)
	var ot_half := int(rules.overtime_half)
	var rounds := a + b
	if rounds <= half * 2:
		return maxi(a, b) > half or (rounds == half * 2 and not overtime)
	if not overtime: return true
	var block := floori(float(rounds - half * 2 - 1) / float(ot_half * 2))
	return maxi(a, b) >= half + (block + 1) * ot_half + 1
