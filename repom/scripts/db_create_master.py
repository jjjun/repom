from repom.db import db_session
from repom.config import load_set_model_hook_function


def main():
    # 初期データの挿入
    load_set_model_hook_function()
    pass


if __name__ == "__main__":
    main()
