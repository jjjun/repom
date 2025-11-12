import dataclasses
import json


@dataclasses.dataclass
class BaseStaticModel:
    id: int = dataclasses.field(init=False)

    _id_counter: int = dataclasses.field(init=False, default=0, repr=False)

    def __post_init__(self):
        type(self)._id_counter += 1
        self.id = self._id_counter

    def to_dict(self):
        # _id_counter を除外して辞書に変換
        return {k: v for k, v in dataclasses.asdict(self).items() if k != '_id_counter'}

    def to_json(self):
        return json.dumps(self.to_dict())
