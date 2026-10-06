extends RefCounted
## Read-only scheduling. Writes never enter this queue or retry policy.
var paths: Array[String] = []
var failures: Dictionary = {}
var due: Dictionary = {}

func enqueue(path: String) -> bool:
	if path in paths: return true
	if paths.size() >= 32: return false
	paths.append(path)
	return true

func ready(path: String, now: int) -> bool:
	return now >= int(due.get(path, 0))

func take(now: int) -> String:
	for path in paths:
		if ready(path, now):
			paths.erase(path)
			return path
	return ""

func failed(path: String, now: int) -> void:
	enqueue(path)
	var count := mini(6, int(failures.get(path, 0)) + 1)
	failures[path] = count
	due[path] = now + int(minf(30.0, pow(2.0, count - 1))) * 1000

func succeeded(path: String) -> void:
	failures.erase(path)
	due.erase(path)

func clear() -> void:
	paths.clear()
	failures.clear()
	due.clear()
