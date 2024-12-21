from tortoise.indexes import Index


class CustomIndex(Index):
    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        self._foo = ""
