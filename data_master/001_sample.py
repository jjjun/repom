"""
Sample モデルのマスターデータ

このファイルは db_sync_master コマンドで読み込まれ、
データベースに同期（Upsert）されます。
"""

from repom.examples.models.sample import SampleModel

# どのモデルクラスに対するマスターデータかを指定
MODEL_CLASS = SampleModel

# マスターデータ（辞書のリスト）
MASTER_DATA = [
    {
        "id": 1,
        "value": "Sample Master Data 1",
        "done_at": None,
    },
    {
        "id": 2,
        "value": "Sample Master Data 2",
        "done_at": None,
    },
    {
        "id": 3,
        "value": "Sample Master Data 3",
        "done_at": None,
    },
]
