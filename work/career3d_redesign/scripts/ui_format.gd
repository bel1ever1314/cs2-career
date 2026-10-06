extends RefCounted
## Display-only number formatting shared by phone, computer and HUD.
## Godot parses every JSON number as float, so "#1.0" or "2026.0 年" leaked into
## the UI. normalize() turns integral floats from the service back into ints;
## the helpers below format values for people. Nothing here changes career data.

## Recursively converts integral floats (1.0 -> 1) inside service projections.
## Fractional values (ratings, ADR, ability 78.6) stay untouched.
static func normalize(value: Variant) -> Variant:
	match typeof(value):
		TYPE_FLOAT:
			var number: float = value
			if is_finite(number) and number == floorf(number) and absf(number) < 9.0e15:
				return int(number)
			return number
		TYPE_DICTIONARY:
			var source: Dictionary = value
			for key in source.keys():
				source[key] = normalize(source[key])
			return source
		TYPE_ARRAY:
			var items: Array = value
			if items.is_typed(): return items
			for index in range(items.size()):
				items[index] = normalize(items[index])
			return items
	return value

static func is_number(value: Variant) -> bool:
	return typeof(value) in [TYPE_INT, TYPE_FLOAT] and is_finite(float(value))

## Plain number. digits < 0: integers print without decimals, others with one.
static func num(value: Variant, digits: int = -1, empty: String = "—") -> String:
	if not is_number(value): return empty
	var number := float(value)
	if digits < 0:
		if number == floorf(number): return _group(str(int(number)))
		digits = 1
	if digits == 0: return _group(str(roundi(number)))
	var text := ("%." + str(digits) + "f") % number
	var parts := text.split(".")
	return _group(parts[0]) + "." + parts[1]

static func integer(value: Variant, empty: String = "—") -> String:
	return _group(str(roundi(float(value)))) if is_number(value) else empty

## Ability-style one-decimal value that hides a trailing ".0".
static func score(value: Variant, empty: String = "—") -> String:
	if not is_number(value): return empty
	var number := snappedf(float(value), 0.1)
	return str(int(number)) if number == floorf(number) else "%.1f" % number

static func rank(value: Variant, empty: String = "—") -> String:
	return "#" + str(roundi(float(value))) if is_number(value) else empty

static func rating(value: Variant, empty: String = "—") -> String:
	return "%.2f" % float(value) if is_number(value) else empty

static func signed(value: Variant, digits: int = 1, empty: String = "—") -> String:
	if not is_number(value): return empty
	return ("%+." + str(digits) + "f") % float(value)

static func percent(value: Variant, ratio: bool = true, empty: String = "—") -> String:
	if not is_number(value): return empty
	return "%s%%" % score(float(value) * (100.0 if ratio else 1.0))

static func percent_fixed(value: Variant, digits: int = 1, empty: String = "—") -> String:
	return num(float(value) * 100, digits, empty) + "%" if is_number(value) else empty

## The career service writes every amount in US dollars.
static func money(value: Variant, signed: bool = false, empty: String = "—") -> String:
	if not is_number(value): return empty
	var amount := roundi(float(value))
	var sign := "-" if amount < 0 else ("+" if signed and amount > 0 else "")
	return sign + "$" + _group(str(absi(amount)), 3)

## Compact money for tiles: $47,230 · $276.8K · $1.25M
static func money_short(value: Variant, empty: String = "—") -> String:
	if not is_number(value): return empty
	var amount := float(value)
	var sign := "-" if amount < 0 else ""
	amount = absf(amount)
	if amount >= 1000000.0: return sign + "$%.2fM" % (amount / 1000000.0)
	if amount >= 100000.0: return sign + "$%.1fK" % (amount / 1000.0)
	return sign + "$" + _group(str(roundi(amount)), 3)

static func record(wins: Variant, losses: Variant) -> String:
	return "%s 胜 · %s 负" % [integer(wins, "0"), integer(losses, "0")]

static func kda(stats: Dictionary) -> String:
	return "%s / %s / %s" % [integer(stats.get("k"), "—"), integer(stats.get("d"), "—"), integer(stats.get("a"), "—")]

## Thousands separators. Plain counts keep 4-digit values (years, Elo) intact;
## money passes min_digits = 3 so $7,230 matches $47,230.
static func _group(digits: String, min_digits: int = 4) -> String:
	var negative := digits.begins_with("-")
	var body := digits.trim_prefix("-")
	if body.length() <= min_digits: return digits
	var out := ""
	var count := 0
	for index in range(body.length() - 1, -1, -1):
		out = body[index] + out
		count += 1
		if count % 3 == 0 and index > 0: out = "," + out
	return ("-" if negative else "") + out
