"""UTF-8 JSON boundary. Native encoder is bundled; source installs can fall back."""
import json
try:
    import orjson
except ImportError:
    orjson = None


def encode(value):
    if orjson is not None:
        return orjson.dumps(value, option=orjson.OPT_NON_STR_KEYS)
    return json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
