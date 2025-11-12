from mine_db.db import engine, Base
from mine_db.config import load_set_model_hook_function


def main():
    load_set_model_hook_function()
    Base.metadata.drop_all(bind=engine)


if __name__ == "__main__":
    main()
