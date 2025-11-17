from repom.db import engine, Base
from repom.config import load_models


def main():
    load_models()
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    main()
