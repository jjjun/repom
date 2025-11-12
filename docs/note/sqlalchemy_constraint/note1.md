# sqlalchemy


## 制約、テーブル側かモデル側、どっちで掛ける？

テーブル側で制約を掛けるか、モデル側で制約を掛けるか、どっちにしようかと考えました。

`WikiRevModel` というモデルがあるとします。これは、wikipediaのapiを叩いて、該当ページの編集履歴を保存する目的で作ったモデルです。

```py
class WikiRevModel(BaseModel):
    """
    """
    __tablename__ = get_plural_tablename(__file__)

    key = Column(String(255), nullable=False, unique=True)
    title = Column(String(255), nullable=False, default='')
    content = Column(Text)
    status = Column(String(255), nullable=False, default='waiting')

    # 特定の値のみ受け付ける様に
    @validates('status')
    def validate_status(self, key, value):
        if value not in ('waiting', 'reject', 'merged'):
            raise ValueError("Invalid status value")
        return value

    # 空文字列が入らない様に
    __table_args__ = (
        CheckConstraint("key != ''", name='check_key_not_empty'),
        CheckConstraint("url != ''", name='check_url_not_empty'),
    )
```

モデル側で制約を掛ける、というのは `validates` デコレータを使って、モデルが受ける値を絞る事を指しています(便宜上制約と言っています)。`CheckConstraint` を使って入る値を絞るのは、テーブルに対して制約を掛けます。

`validates` デコレータを使っている所をテーブルに対して制約を掛けるとしたら、次の様になりますね。

```py
__table_args__ = (
    CheckConstraint("status IN ('waiting', 'reject', 'merged')", name='check_status_valid'),
)
```

### モデル側で制約を掛ける(`validates` デコレータ)

メリット

- 柔軟性: Pythonのコード内で複雑なバリデーションロジックを実装できるため、柔軟な制約を設定できます。
- 即時フィードバック: データベースに保存する前にバリデーションが行われるため、ユーザーに即時フィードバックを提供できます。
- 一貫性: アプリケーション全体で一貫したバリデーションロジックを適用できます。

デメリット

- データベースの整合性: データベースレベルでの制約がないため、他のアプリケーションや直接データベースにアクセスする場合に不正なデータが挿入される可能性があります。
- パフォーマンス: 大量のデータをバリデーションする場合、Pythonのコードでバリデーションを行うため、パフォーマンスが低下する可能性があります。

### データベース側で制約を掛ける (CheckConstraint)

メリット

- データベースの整合性: データベースレベルで制約が適用されるため、他のアプリケーションや直接データベースにアクセスする場合でも不正なデータが挿入されるのを防ぎます。
- パフォーマンス: データベースエンジンが制約を処理するため、大量のデータをバリデーションする場合でもパフォーマンスが向上します。
- 一貫性: データベース全体で一貫した制約を適用できます。

デメリット
- 柔軟性の欠如: データベースの制約は比較的単純なものに限られるため、複雑なバリデーションロジックを実装するのが難しいです。
- 即時フィードバックの欠如: データベースに保存する際にエラーが発生するため、ユーザーに即時フィードバックを提供するのが難しいです。

### 私はどうしたか

`status` に関しては `validates` デコレータを付ける事で対応しました。後からステータスを増やす可能性があったので、テーブルに対して制約を掛けると、更新した時にテーブルの制約を設定し直すというコストが生まれてしまうからです。

ただ、`CheckConstraint` を使わずに `validates` デコレータを使った場合にエラーの発生タイミングに注意しなくてはいけません。

`CheckConstraint` の場合は、`session.commit()` 時にエラーが発生するのに対して、`validates` デコレータを使うと、インスタンス生成時にエラーが出ます。その為、次のようなテストを書くと、テストを通りません。

```py
# この部分(インスタンス生成時)で ValueError が発生する
rev = TmpWikiRevModel(rev_id=10, user='test_user', comment='test_comment', status='invalid_status')
db_test.add(rev)

with pytest.raises(ValueError):
    db_test.commit()
```
