import pytest


class Greeter:
    @staticmethod
    def greet():
        return 'hello!!'

print(Greeter.greet())
