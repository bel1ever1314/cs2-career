# Arena soundscape

The playable arena generates four original sound layers in memory in
`scripts/arena_atmosphere.gd`: a ventilation/passage bed, filtered crowd noise
with applause accents, a twelve-second original synthesized entrance motif,
and a six-second synthesized cheer. These are not field recordings, sampled
voices, commercial music, or remotely downloaded audio.

The prototype uses mono 12 kHz, 16-bit PCM streams. Two ambient layers loop;
the entrance music and cheer play once when the visitor first crosses the
public tunnel into the bowl. Walking out and returning does not retrigger them.
Pausing ducks the sound; the phone can use `set_master_volume(0..1)` and
`set_muted(bool)` to control all four layers. The room/crowd sound is a stylized
placeholder that can later be replaced with licensed recordings.

Geometry is a low-poly conceptual sports venue at the existing prototype's
scale, with a 25.6 m eave and 29 m roof crown. It is not a measured replica or
a construction plan.
