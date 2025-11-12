## `check_ok` を付け無いと警告が出る

この警告は、SQLAlchemy の TypeDecorator に cache_ok 属性が設定されていないために発生しています。cache_ok 属性を True に設定することで、この警告を解消できます。

```sh
# SAWarning: TypeDecorator ListJSON() will not produce a cache key because the ``cache_ok`` attribute is not set to True.  This can have significant performance implications including some performance degradations in comparison to prior SQLAlchemy versions.  Set this attribute to True if this type object's state is safe to use in a cache key, or False to disable this warning. (Background on this warning at: https://sqlalche.me/e/20/cprf)
# -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
```

cache_ok は、SQLAlchemy の TypeDecorator クラスの属性で、この型がキャッシュキーとして安全に使用できるかどうかを示します。cache_ok を True に設定することで、SQLAlchemy はこの型をキャッシュキーとして使用できるようになります。これにより、パフォーマンスの向上が期待できます。

詳細
cache_ok = True: この型がキャッシュキーとして安全に使用できることを示します。SQLAlchemy はこの型をキャッシュキーとして使用し、パフォーマンスを向上させます。
cache_ok = False: この型がキャッシュキーとして安全に使用できないことを示します。SQLAlchemy はこの型をキャッシュキーとして使用しません。

キャッシュキーは、キャッシュされたデータを一意に識別するために使用されるキーです。SQLAlchemy では、クエリの結果や計算された値をキャッシュすることで、パフォーマンスを向上させることができます。このとき、キャッシュキーを使用してキャッシュされたデータを一意に識別します。

キャッシュキーの役割
一意性の保証: キャッシュキーは、キャッシュされたデータを一意に識別するために使用されます。同じキャッシュキーを持つデータは、同じキャッシュエントリを指します。
パフォーマンスの向上: キャッシュキーを使用することで、同じクエリや計算を繰り返し実行する必要がなくなり、パフォーマンスが向上します。



## StatementError 

リスト以外を代入できない型を定義した。

```
class ListJSON(TypeDecorator):
    """
    
    """
    impl = JSON
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return json.dumps([])
        if not isinstance(value, list):
            raise ValueError("Expected a list, but got a different type")
        return json.dumps(value)
```

上記をテストする為に次のようなコードを書いたんだけど意図した挙動と違った。

```
class ListModel(BaseModel):
    __tablename__ = 'test_list_model'
    id = Column(Integer, primary_key=True)
    option_list = Column(ListJSON)

def test_list_json_raises_error_on_non_list(db_test):
    """
    ListJSON 型の場合、List以外を入れたらエラーが出る事を保証
    """
    with pytest.raises(ValueError):
        log = ListModel(option_list={"key": "value"})
        db_test.add(log)
        db_test.commit()
```

```
sqlalchemy.exc.StatementError: (builtins.ValueError) Expected a list, but got a different type
```

`StatementError` をキャッチすれば良い。

StatementError は、SQLAlchemy がデータベース操作中に発生するエラーをキャッチして再スローする例外クラスです。具体的には、SQL文の実行中に発生したエラーをラップして提供します。StatementError は、元のエラー（この場合は ValueError）を含むため、デバッグ情報として有用です。

元の ValueError を直接キャッチする方法を推奨します。これにより、エラーの原因を特定しやすく、テストの意図が明確になります。

```
def test_list_json_raises_error_on_non_list(db_test):
    """
    ListJSON 型の場合、List以外を入れたらエラーが出る事を保証
    """
    with pytest.raises(ValueError):
        log = ListModel(option_list={"key": "value"})
        db_test.add(log)
        db_test.flush()
```

flush メソッドを使用: flush メソッドを使用して、データベースに変更を反映させます。



commit() と flush() の違い

commit()
動作: commit() メソッドは、セッション内のすべての変更をデータベースに永続的に保存し、トランザクションを終了します。
トランザクションの終了: commit() を呼び出すと、現在のトランザクションが終了し、新しいトランザクションが開始されます。
例外処理: commit() 中にエラーが発生すると、トランザクション全体がロールバックされます。
flush()
動作: flush() メソッドは、セッション内の変更をデータベースに一時的に反映させますが、トランザクションは終了しません。
トランザクションの継続: flush() を呼び出しても、トランザクションは継続されます。つまり、flush() の後にさらに変更を加えて commit() することができます。
例外処理: flush() 中にエラーが発生すると、そのエラーが即座に発生し、トランザクションはロールバックされません。
違いのまとめ
commit(): 変更を永続的に保存し、トランザクションを終了する。
flush(): 変更を一時的に反映させ、トランザクションを継続する。



flush()とcommit() の違いによって、発生するエラーの種類が異なる理由は、SQLAlchemy のエラーハンドリングの仕組みにあります。

flush() の動作
flush(): セッション内の変更をデータベースに一時的に反映させますが、トランザクションは終了しません。flush() は、データベースに対して実際に SQL 文を発行し、エラーが発生した場合は即座にそのエラーを発生させます。この場合、ListJSON 型のカラムにリスト以外の値を挿入しようとすると、process_bind_param メソッド内で ValueError が発生します。
commit() の動作
commit(): セッション内の変更をデータベースに永続的に保存し、トランザクションを終了します。commit() は、内部的に flush() を呼び出してからトランザクションをコミットします。flush() 中に発生したエラーは、SQLAlchemy によってキャッチされ、StatementError として再スローされます。StatementError は、元のエラー（この場合は ValueError）をラップして提供します。
エラーハンドリングの違い
flush(): 直接的なエラー（ValueError）を発生させます。
commit(): 内部的に flush() を呼び出し、発生したエラーをキャッチして StatementError として再スローします。


結果的に `StatementError` で捕捉するようにした。

```
def test_list_json_raises_error_on_non_list(db_test):
    """
    ListJSON 型の場合、List以外を入れたらエラーが出る事を保証
    """
    # commit の場合 StatementErrorが出る
    with pytest.raises(StatementError):
        log = ListModel(option_list={"key": "value"})
        db_test.add(log)
        db_test.commit()
```
