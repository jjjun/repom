from datetime import datetime, timedelta
import random
import string  # 追加
import time



def generate_sample_task_data(num_samples,
                              done_at_start=None, done_at_end=None,
                              created_at_start=None, created_at_end=None):
    """
    指定した個数分のサンプルデータを生成する関数

    Args:
        num_samples (int): 生成するデータの個数
        done_at_start (datetime.date, optional): done_atの開始日。デフォルトは今日から1週間前。
        done_at_end (datetime.date, optional): done_atの終了日。デフォルトは今日。
        created_at_start (datetime, optional): created_atの開始日時。デフォルトは今日から1週間前。
        created_at_end (datetime, optional): created_atの終了日時。デフォルトは今日。

    Returns:
        list: 生成されたサンプルデータのリスト

    使用例:
        done_at_start = datetime.strptime('2023-12-21', "%Y-%m-%d").date()
        done_at_end = datetime.strptime('2024-03-23', "%Y-%m-%d").date()
        created_at_start = datetime(2023, 12, 21)
        created_at_end = datetime(2024, 2, 23)

        sample_data = generate_sample_task_data(9, done_at_start, done_at_end, created_at_start, created_at_end)
        for data in sample_data:
            print(data)
    """
    # デフォルト値の設定
    if done_at_start is None:
        done_at_start = (datetime.now() - timedelta(days=7)).date()
    if done_at_end is None:
        done_at_end = datetime.now().date()
    if created_at_start is None:
        created_at_start = datetime.now() - timedelta(days=7)
    if created_at_end is None:
        created_at_end = datetime.now()

    sample_data = []
    for i in range(num_samples):
        # done_atの期間内でランダムな日付を生成
        done_at = done_at_start + timedelta(days=random.randint(0, (done_at_end - done_at_start).days))
        # created_atの期間内でランダムな日時を生成
        created_at = created_at_start + timedelta(days=random.randint(0, (created_at_end - created_at_start).days))
        # サンプルデータをリストに追加
        sample_data.append({
            'name': f'sample{i+1}',
            'done_at': done_at,
            'created_at': created_at,
        })
    return sample_data


def generate_sample_roster_data(num_samples):
    """
    指定した個数分のRosterModel用のサンプルデータを生成する関数

    Args:
        num_samples (int): 生成するデータの個数

    Returns:
        list: 生成されたサンプルデータのリスト

    使用例:
        sample_data = generate_sample_roster_data(10)
        for data in sample_data:
            print(data)
    """
    sample_data = []
    for i in range(num_samples):
        # ランダムな英字列を生成
        key = ''.join(random.choices(string.ascii_lowercase, k=10))
        # サンプルデータをリストに追加
        sample_data.append({
            'key': key,
            'name': f'sample_name_{i+1}',
        })
    return sample_data


def save_model_instances(model_class, sample_data, db_session):
    """
    Save a list of dictionaries as instances of the specified model class to the database.

    Args:
        model_class (Base): The SQLAlchemy model class to be used for creating instances.
        sample_data (list): List of dictionaries containing the data to be saved.
        db_session (Session): The SQLAlchemy database session to be used for saving the instances.

    Raises:
        Exception: If there is an error during the database transaction, it will be rolled back and the exception will be raised.
    """
    try:
        for item in sample_data:
            instance = model_class(**item)
            db_session.add(instance)
        db_session.commit()
    except Exception as e:
        db_session.rollback()
        raise e


def timer(func):
    """
    デコレーター関数。指定された関数の実行時間を計測し、表示する。

    Args:
        func (function): 実行時間を計測する対象の関数。

    Returns:
        function: 実行時間を計測するラッパー関数。

    使用例:
        @timer
        def example_function():
            # 関数の処理
            pass
    """
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} 実行時間: {end - start:.6f}秒")
        return result

    return wrapper
