"""JSON-only checkpoints for the existing gameplay random streams.

The app has one active ApplicationState and serialises mutations. Match RNG is
separate from career/skin RNG. Capturing either stream must not consume it.
Never deserialize executable pickle data from a save or an extension.
"""
import math
import random


def capture():
    from .engine.match import RNG
    return {'version': 1, 'career': random.getstate(), 'match': RNG.getstate()}


def _validated(value):
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError('随机进度结构无效')
    version, words, gaussian = value
    if type(version) is not int or version != 3 or not isinstance(words, (list, tuple)) or len(words) != 625:
        raise ValueError('随机进度版本或长度无效')
    if any(type(n) is not int or not 0 <= n <= 0xFFFFFFFF for n in words[:-1]):
        raise ValueError('随机进度内容无效')
    if type(words[-1]) is not int or not 0 <= words[-1] <= 624:
        raise ValueError('随机进度索引无效')
    if gaussian is not None and (type(gaussian) not in (float, int) or not math.isfinite(gaussian)):
        raise ValueError('随机高斯缓存无效')
    return version, tuple(words), gaussian


def restore(checkpoint):
    if checkpoint is None:
        return  # Optional v2 field; there is no historic sequence to reconstruct.
    if not isinstance(checkpoint, dict) or type(checkpoint.get('version')) is not int or checkpoint['version'] != 1:
        raise ValueError('随机进度格式无效')
    # Validate both before mutating either global stream.
    career = _validated(checkpoint.get('career'))
    match = _validated(checkpoint.get('match'))
    from .engine.match import RNG
    random.setstate(career)
    RNG.setstate(match)
