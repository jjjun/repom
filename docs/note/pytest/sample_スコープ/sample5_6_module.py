class SharedData:
    _data = []

    @classmethod
    def add_data(cls, value):
        cls._data.append(value)

    @classmethod
    def get_data(cls):
        return cls._data
