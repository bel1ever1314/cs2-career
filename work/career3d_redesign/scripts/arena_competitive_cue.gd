extends RefCounted
## Original procedural walk-in sting. No recordings, sampled voices or songs.
const BPM := 136.0
const BEAT := 60.0 / BPM
const RATE := 22050
const SECONDS := BEAT * 32.0 + 2.0
static var cached: AudioStreamWAV

static func stream() -> AudioStreamWAV:
	if cached != null: return cached
	var frames := int(SECONDS * RATE)
	var data := PackedByteArray(); data.resize(frames * 2)
	var random := RandomNumberGenerator.new(); random.seed = 20261002
	var high_noise := 0.0; var low_noise := 0.0
	for i in range(frames):
		var t := float(i) / RATE; var beat := int(t / BEAT); var phase := fmod(t, BEAT)
		var noise := random.randf_range(-1.0,1.0)
		low_noise = lerpf(low_noise,noise,.085); high_noise = noise - low_noise
		var build := beat < 8; var active := beat < 32
		var kick := sin(TAU * (49.0 * phase + .82 * (1.0 - exp(-phase * 32.0)))) * exp(-phase * 18.0) * .42
		var snare := high_noise * exp(-phase * 34.0) * .24 if beat % 4 in [1,3] else 0.0
		var eighth := fmod(t,BEAT * .5)
		var hats := high_noise * exp(-eighth * 115.0) * (.052 if build else .083)
		var roots := [38,38,34,36]; var root: int = roots[int(beat / 4) % 4]
		var bass_hz := 440.0 * pow(2.0,(root - 69.0) / 12.0)
		var bass_wave := sin(TAU * bass_hz * t) + .30 * sin(TAU * bass_hz * 2.0 * t)
		var bass := tanh(bass_wave * 2.0) * exp(-phase * 6.0) * .16
		var stab := (sin(TAU * bass_hz * 4.0 * t) + .55 * sin(TAU * bass_hz * 6.0 * t)) * exp(-phase * 10.0) * .075 if beat % 4 == 0 else 0.0
		var riser := high_noise * pow(clampf(t / (BEAT * 8.0),0,1),2) * .065 if build else 0.0
		var sample := ((kick * .45 + hats + bass * .55 + riser) if build else (kick + snare + hats + bass + stab)) if active else 0.0
		# A unique opening impact at the portal and a final sustained low chord.
		var drop := t - BEAT * 8.0
		if drop >= 0.0 and drop < .65: sample += (low_noise * .36 + sin(TAU * 42.0 * drop) * .20) * exp(-drop * 6.0)
		var tail := t - BEAT * 32.0
		if tail >= 0.0: sample += (sin(TAU * 73.42 * t) + .35 * sin(TAU * 110.0 * t)) * .12 * exp(-tail * 2.8)
		var fade := minf(1.0,t / .025) * minf(1.0,(SECONDS - t) / .6)
		data.encode_s16(i * 2,int(clampf(tanh(sample * 1.28) * fade,-.83,.83) * 32767.0))
	cached = AudioStreamWAV.new(); cached.format = AudioStreamWAV.FORMAT_16_BITS
	cached.mix_rate = RATE; cached.stereo = false; cached.data = data
	return cached
