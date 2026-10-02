extends Node
## Fresh-directory release smoke test. No live CS2 or installation is requested.
var elapsed := 0.0

func _process(delta: float) -> void:
	elapsed += delta
	if CareerBridge.connected:
		var row: Dictionary = CareerBridge.context
		for key in ["player", "team", "settings", "media", "start", "calendar"]:
			if not row.has(key):
				push_error("Distribution context missing: " + key)
				get_tree().quit(2)
				return
		if str(CareerBridge.settings.get("backend_exe", "")).is_empty():
			push_error("Distribution did not use the frozen backend")
			get_tree().quit(2)
			return
		print("DISTRIBUTION_CONNECTION_OK: frozen backend + fresh career + public media")
		get_tree().quit(0)
	elif elapsed > 75.0:
		push_error("Distribution connection timeout: " + CareerBridge.message)
		get_tree().quit(2)
