import base64
import json
import pickle  # nosec: B301,B403
from typing import Any, Union

from tortoise.indexes import Index


class JsonEncoder(json.JSONEncoder):
    def default(self, obj) -> Any:
        if isinstance(obj, Index):
            return {
                "type": "index",
                "val": base64.b64encode(pickle.dumps(obj)).decode(),  # nosec: B301
            }
        else:
            return super().default(obj)


def object_hook(obj) -> Any:
    _type = obj.get("type")
    if not _type:
        return obj
    return pickle.loads(base64.b64decode(obj["val"]))  # nosec: B301


def encoder(obj: dict) -> str:
    return json.dumps(obj, cls=JsonEncoder)


def decoder(obj: Union[str, bytes]) -> Any:
    return json.loads(obj, object_hook=object_hook)
