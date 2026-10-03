extends Translation
## Godot translates native controls at text changes and locale notifications.
## This resource extends exact messages with authored whole-message templates.
var owner: Node

func _get_message(source: StringName, _context: StringName) -> StringName:
	return StringName(owner.text(str(source))) if is_instance_valid(owner) else source

func _get_plural_message(source: StringName, _plural: StringName, _number: int, context: StringName) -> StringName:
	return _get_message(source, context)
