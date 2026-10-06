extends RefCounted
## One seated-spectator chicken design shared by every crowd (Major bowl,
## arena tiers, awards guests). It follows the player chicken: big round head,
## glossy dot eyes with a glint, blush cheeks, tiny comb and beak, pear body.
##
## Vertex colour alpha marks what may be re-tinted per spectator:
## alpha 1 = keep (eyes, beak, comb, seats), alpha 0 = feather colour.
## crowd_material() applies the per-instance feather tint from custom data.
const FEATHER := Color("f6efe1")
const BELLY := Color("fffaf0")
const COMB := Color("e0503f")
const BEAK := Color("f0ab45")
const EYE := Color("1e2229")
const GLINT := Color("ffffff")
const BLUSH := Color("f4a7a0")
## Seat height for a chicken: a low cushion so the short legs reach the floor.
const BODY_BOTTOM := 0.30
const TINTS := [Color("ffffff"),Color("f2d9b0"),Color("c9dde6"),Color("f0c3a6"),Color("bfcfb4"),Color("f3e2a0"),Color("d9cbe8"),Color("e8c9b8"),Color("b9c6c4"),Color("f6d2c8")]

static func material() -> ShaderMaterial:
	var shader := Shader.new()
	shader.code = """shader_type spatial;
varying vec3 feather_tint;
void vertex() {
	feather_tint = INSTANCE_CUSTOM.rgb;
}
void fragment() {
	vec3 tint = feather_tint;
	if (tint.r + tint.g + tint.b < 0.01) { tint = vec3(1.0); }
	float tintable = 1.0 - COLOR.a;
	ALBEDO = COLOR.rgb * mix(vec3(1.0), tint, tintable);
	ROUGHNESS = 0.8;
}
"""
	var result := ShaderMaterial.new()
	result.shader = shader
	return result

static func tint(index: int) -> Color:
	return TINTS[(index * 7 + int(index / 9)) % TINTS.size()]

static func vertex(surface: SurfaceTool, at: Vector3, normal: Vector3, color: Color) -> void:
	surface.set_color(color)
	surface.set_normal(normal)
	surface.add_vertex(at)

static func ellipsoid(surface: SurfaceTool, center: Vector3, radii: Vector3, color: Color, sides: int, rings: int) -> void:
	for row in range(rings):
		for side in range(sides):
			var directions: Array[Vector3] = []
			for ij in [[row, side], [row + 1, side], [row + 1, side + 1], [row, side + 1]]:
				var latitude := PI * float(ij[0]) / rings
				var longitude := TAU * float(ij[1]) / sides
				directions.append(Vector3(sin(latitude) * cos(longitude), cos(latitude), sin(latitude) * sin(longitude)))
			for tri in ([[0, 1, 2]] if row == 0 else ([[0, 2, 3]] if row == rings - 1 else [[0, 1, 2], [0, 2, 3]])):
				for index in tri:
					var direction: Vector3 = directions[index]
					vertex(surface, center + direction * radii, (direction / radii).normalized(), color)

static func _keep(color: Color) -> Color:
	return Color(color.r, color.g, color.b, 1.0)

static func _feather(color: Color) -> Color:
	return Color(color.r, color.g, color.b, 0.0)

## Body + head + face. detail: 2 = near/hero, 1 = mid, 0 = far terraces.
static func seated_chicken(detail: int = 2, wings: bool = true) -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	add_seated_chicken(surface, Vector3.ZERO, detail, wings)
	return surface.commit()

static func add_seated_chicken(surface: SurfaceTool, at: Vector3, detail: int = 2, wings: bool = true) -> void:
	# The face/feather layout below was authored for a 0.475 m seat.
	at += Vector3(0, BODY_BOTTOM - 0.475, 0)
	var big: Array = [[8, 5], [14, 9], [20, 12]][clampi(detail, 0, 2)]
	var small: Array = [[5, 3], [8, 5], [10, 6]][clampi(detail, 0, 2)]
	var s: int = big[0]; var r: int = big[1]
	var ss: int = small[0]; var sr: int = small[1]
	# Round body settled on the cushion, plus a pale belly.
	ellipsoid(surface, at + Vector3(0, 0.475 + 0.205, -0.03), Vector3(0.245, 0.205, 0.22), _feather(FEATHER), s, r)
	# Sitting pose: two feathered thighs lie forward along the seat to the
	# knees at its front edge (z = 0.29); legs bend down from there.
	for side in [-1.0, 1.0]:
		ellipsoid(surface, at + Vector3(side * 0.105, 0.475 + 0.065, 0.15), Vector3(0.088, 0.065, 0.14), _feather(FEATHER.darkened(0.02)), ss + 2, sr + 1)
	if detail > 0:
		ellipsoid(surface, at + Vector3(0, 0.665, 0.095), Vector3(0.175, 0.165, 0.13), Color(BELLY.r, BELLY.g, BELLY.b, 0.55), s, r)
	# Big round head.
	ellipsoid(surface, at + Vector3(0, 0.995, 0.025), Vector3(0.205, 0.195, 0.19), _feather(FEATHER), s, r)
	# Tail feathers.
	for x in [-0.07, 0.0, 0.07]:
		ellipsoid(surface, at + Vector3(x, 0.79 + (0.03 if x == 0.0 else 0.0), -0.225), Vector3(0.045, 0.1, 0.06), _feather(FEATHER), ss, sr)
	if wings:
		for side in [-1.0, 1.0]:
			ellipsoid(surface, at + Vector3(side * 0.235, 0.675, 0.01), Vector3(0.06, 0.14, 0.11), _feather(FEATHER.darkened(0.06)), ss + 2, sr + 1)
	# Comb: three round lobes.
	for lobe in [[-0.06, 1.165, 0.034], [0.01, 1.19, 0.04], [0.08, 1.16, 0.032]]:
		ellipsoid(surface, at + Vector3(0, lobe[1], lobe[0]), Vector3(lobe[2], lobe[2] * 1.5, lobe[2] * 1.15), _keep(COMB), ss, sr)
	# Beak (upper and lower), wattle.
	ellipsoid(surface, at + Vector3(0, 0.965, 0.21), Vector3(0.046, 0.03, 0.055), _keep(BEAK), ss, sr)
	ellipsoid(surface, at + Vector3(0, 0.94, 0.198), Vector3(0.034, 0.02, 0.04), _keep(BEAK.darkened(0.12)), ss, sr)
	ellipsoid(surface, at + Vector3(0, 0.9, 0.185), Vector3(0.022, 0.034, 0.018), _keep(COMB), ss, sr)
	# Dot eyes with a glint, and blush.
	for side in [-1.0, 1.0]:
		ellipsoid(surface, at + Vector3(side * 0.078, 1.01, 0.195), Vector3(0.027, 0.036, 0.014), _keep(EYE), ss, sr)
		if detail > 0:
			ellipsoid(surface, at + Vector3(side * 0.07, 1.026, 0.205), Vector3(0.009, 0.01, 0.006), _keep(GLINT), 6, 3)
			ellipsoid(surface, at + Vector3(side * 0.138, 0.955, 0.162), Vector3(0.036, 0.022, 0.012), _keep(BLUSH), ss, sr)

## Lower legs of a seated chicken: knee over the seat's front edge, shin down
## to the floor in front of it, foot flat on the floor pointing forward.
static func legs(surface: SurfaceTool, at: Vector3, sole_y: float = 0.018) -> void:
	var shin := _keep(Color("e2963a"))
	var foot := _keep(Color("efa949"))
	for side in [-1.0, 1.0]:
		var knee_y := BODY_BOTTOM + 0.04
		var bottom := sole_y + 0.035
		ellipsoid(surface, at + Vector3(side * 0.105, knee_y, 0.3), Vector3(0.032, 0.032, 0.032), shin, 8, 5)
		ellipsoid(surface, at + Vector3(side * 0.105, (knee_y + bottom) * 0.5, 0.315), Vector3(0.03, (knee_y - bottom) * 0.5, 0.03), shin, 8, 5)
		ellipsoid(surface, at + Vector3(side * 0.105, sole_y + 0.023, 0.37), Vector3(0.07, 0.023, 0.1), foot, 8, 4)

static func legs_mesh() -> ArrayMesh:
	var surface := SurfaceTool.new()
	surface.begin(Mesh.PRIMITIVE_TRIANGLES)
	legs(surface, Vector3.ZERO)
	return surface.commit()

static func _box(surface: SurfaceTool, center: Vector3, size: Vector3, color: Color) -> void:
	var corners: Array[Vector3] = []
	for x in [-1.0, 1.0]:
		for y in [-1.0, 1.0]:
			for z in [-1.0, 1.0]:
				corners.append(center + size * Vector3(x, y, z) * 0.5)
	for face in [[0, 1, 3, 2], [4, 6, 7, 5], [0, 4, 5, 1], [2, 3, 7, 6], [0, 2, 6, 4], [1, 5, 7, 3]]:
		var a: Vector3 = corners[face[0]]; var b: Vector3 = corners[face[1]]; var c: Vector3 = corners[face[2]]; var d: Vector3 = corners[face[3]]
		var normal := (b - a).cross(c - a).normalized()
		for v in [a, b, c, a, c, d]: vertex(surface, v, normal, color)
