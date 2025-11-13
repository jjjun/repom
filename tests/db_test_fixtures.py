import pytest
from repom.db import db_session
from repom.scripts.db_create import main as db_create
from repom.scripts.db_delete import main as db_delete

"""
scope
スコープは、フィクスチャがどのタイミングでセットアップおよびティアダウンされるかを制御します。

function:
デフォルトのスコープです。
各テスト関数の実行前にフィクスチャがセットアップされ、実行後にティアダウンされます。
class:
各テストクラスの実行前にフィクスチャがセットアップされ、実行後にティアダウンされます。
クラス内のすべてのテストメソッドで同じフィクスチャインスタンスが共有されます。
module:
各テストモジュール（ファイル）の実行前にフィクスチャがセットアップされ、実行後にティアダウンされます。
モジュール内のすべてのテスト関数およびクラスで同じフィクスチャインスタンスが共有されます。
package:
各テストパッケージ（ディレクトリ）の実行前にフィクスチャがセットアップされ、実行後にティアダウンされます。
パッケージ内のすべてのテストモジュールで同じフィクスチャインスタンスが共有されます。
session:
テストセッション全体の実行前にフィクスチャがセットアップされ、実行後にティアダウンされます。
テストセッション内のすべてのテストで同じフィクスチャインスタンスが共有されます。
"""


@pytest.fixture()
def db_test():
    db_create()
    yield db_session
    db_delete()
    db_session.remove()
