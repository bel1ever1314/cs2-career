extends RefCounted
## Shared normalization for local user marks and the offline asset builder.
const BACKGROUND := Color("202428b3")
const DARK_MARK_KEYLINE := Color("b7c0ca")

static func panel(source: Image) -> Image:
	var image := source.duplicate() as Image
	image.convert(Image.FORMAT_RGBA8)
	var bounds := image.get_used_rect()
	if not bounds.has_area(): return null
	image = image.get_region(bounds)
	var ratio := minf(1.0, 512.0 / maxf(image.get_width(), image.get_height()))
	image.resize(maxi(1, roundi(image.get_width() * ratio)), maxi(1, roundi(image.get_height() * ratio)), Image.INTERPOLATE_LANCZOS)
	return image

static func avatar(source: Image) -> Image:
	var image := panel(source)
	if image == null: return null
	var ratio := 56.0 / maxf(image.get_width(), image.get_height())
	image.resize(maxi(1, roundi(image.get_width() * ratio)), maxi(1, roundi(image.get_height() * ratio)), Image.INTERPOLATE_LANCZOS)
	var luminance := 0.0
	var coverage := 0.0
	for y in image.get_height():
		for x in image.get_width():
			var p := image.get_pixel(x, y)
			luminance += (p.r * .2126 + p.g * .7152 + p.b * .0722) * p.a
			coverage += p.a
	var canvas := Image.create(64, 64, false, Image.FORMAT_RGBA8)
	canvas.fill(BACKGROUND)
	var origin := Vector2i((64 - image.get_width()) / 2, (64 - image.get_height()) / 2)
	if luminance / maxf(coverage, .001) < .23:
		var edge := Image.create(64, 64, false, Image.FORMAT_RGBA8)
		edge.fill(Color.TRANSPARENT)
		for y in image.get_height():
			for x in image.get_width():
				var alpha := image.get_pixel(x, y).a * .72
				if alpha <= 0: continue
				for dy in range(-1, 2):
					for dx in range(-1, 2):
						var point := origin + Vector2i(x + dx, y + dy)
						var tint := DARK_MARK_KEYLINE
						tint.a = maxf(alpha, edge.get_pixelv(point).a)
						edge.set_pixelv(point, tint)
		canvas.blend_rect(edge, Rect2i(Vector2i.ZERO, edge.get_size()), Vector2i.ZERO)
	canvas.blend_rect(image, Rect2i(Vector2i.ZERO, image.get_size()), origin)
	return canvas
