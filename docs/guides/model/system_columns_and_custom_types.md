# システムカラムとカスタム型

`BaseModel` では、共通の primary key と timestamp column を必要なものだけ追加できます。
既定で追加される column は最小限にしてあり、利用側アプリケーションが schema を選べます。

## システムカラムの設定

class parameter として設定します。

```python
from repom import BaseModel


class Article(
    BaseModel,
    use_created_at=True,
    use_updated_at=True,
):
    __tablename__ = "articles"
```

| オプション | 既定値 | 動作 |
| --- | --- | --- |
| `use_id` | `True` | integer 型の `id` primary key を追加します。 |
| `use_uuid` | `False` | string 型の UUID primary key を追加し、既定の integer key を無効にします。 |
| `use_created_at` | `False` | 作成 timestamp を追加します。 |
| `use_updated_at` | `False` | SQLAlchemy event で更新される timestamp を追加します。 |

`use_id` と `use_uuid` を両方明示的に `True` にするとエラーになります。composite key または
アプリケーション独自の key を使う場合は、自動生成 key を無効にして primary-key column を
自分で宣言します。

```python
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModel


class Membership(BaseModel, use_id=False):
    __tablename__ = "memberships"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
```

flag は class attribute としても宣言できます。subclass はその値を継承し、両方を指定した場合は
class parameter が優先されます。`__tablename__` のない中間 abstract class には column は生成
されません。その concrete subclass を map するときに、継承した flag が適用されます。

```python
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModel


class CompositeModel(BaseModel):
    __abstract__ = True
    use_id = False


class ExternalMembership(CompositeModel):
    __tablename__ = "external_memberships"

    account_id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(primary_key=True)
```

UUID value は instance の生成時に設定されます。timestamp column に Python または server default は
ありません。INSERT の bind 時に `AutoDateTime` が値を設定するため、flush 後も model attribute は
`None` のままです。保存された timestamp を読み込むには `session.refresh(instance)` を呼びます。
UPDATE 時は flush の前に `updated_at` event が値を設定します。`repo.save()` は internal session を
使った場合にだけ refresh します。

## カスタム SQLAlchemy 型

再利用可能な型は [`repom/custom_types`](../../../repom/custom_types) にあります。
日付・時刻の変換 helper や JSON 値を扱う型が含まれます。`repom.custom_types` package が
公開するのは `UTCDateTime` だけです。その他の型はそれぞれの module から import してください。
永続 schema に採用する前に、実装と test を確認してください。

```python
from sqlalchemy.orm import Mapped, mapped_column

from repom import BaseModel
from repom.custom_types.CustomJSON import CustomJSON


class Event(BaseModel):
    __tablename__ = "events"

    payload: Mapped[dict] = mapped_column(CustomJSON)
```

`CustomJSON` は object 型の JSON、`ListJSON` は list 型の JSON に使います。custom type の挙動は
migration 出力や database 間の互換性に影響するため、利用する各 database engine で round-trip test
を追加してください。

`AutoDateTime` は `UTCDateTime` の subclass で、bind 時と result の読み込み時に同じ UTC 正規化を
行います。timezone-aware value は `astimezone(timezone.utc)` で変換し、naive value は UTC とみなして
`tzinfo` だけを付けます。SQLite のように UTC offset を保持できない backend でも保存する instant は
変わりません。読み込み時は、naive value に `timezone.utc` を付け、tzinfo がある value
（例: PostgreSQL の `timestamptz`）は UTC に変換します。`AutoDateTime` は bind value が
`None` の場合に現在時刻を設定します。`UTCDateTime` は `None` をそのまま保持するため、常に
UTC-aware value として読み込みたい nullable datetime column に適しています。

```python
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column

from repom.custom_types import UTCDateTime

started_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
```

`ISO8601DateTime` (`impl = DateTime`) は dialect の native `DateTime` column type で
`datetime` を保存し、ISO 8601 string には変換しません。bind 時の `datetime` value はそのまま渡し
（`None` は `None` のまま、その他の型では `ValueError`）、読み込み時も dialect が返す
`datetime` value をそのまま使います。driver が `str` を返した場合だけ
`datetime.fromisoformat()` で parse します。`ISO8601DateTimeStr` (`impl = String`) は別の
string 保存型で、bind 時に `datetime.isoformat()` で serialize し、読み込み時に
`datetime.fromisoformat()` で parse します。text column が必要なら `ISO8601DateTimeStr`、
native datetime column なら `ISO8601DateTime`（または `AutoDateTime`）を選んでください。

`ListJSON` の `listjson_filter(model_column, values)` は、「column に指定したすべての値が含まれる」
query の filter condition を作ります。異なる各値は outer query に table-valued join を追加せず、
`json_each` の展開に対する相関 `EXISTS` になります。そのため、array 内の重複値や複数の検索値で
outer model row が増えたり、`count()` が膨らんだり、該当 row が `limit` / `offset` の page から
押し出されたりしません。要素の照合には PostgreSQL で `json_array_elements_text()`、SQLite で
`json_each()` を使います。空 list の照合では両 dialect とも `json_array_length(...) == 0` を使うため、
呼び出し側で dialect を分岐する必要はありません。

## 一意制約違反の判定

`repom.exceptions.is_unique_violation()` は SQLAlchemy の `IntegrityError` が一意制約違反かを
判定します。psycopg / asyncpg では SQLSTATE `23505`、sqlite3 / aiosqlite では
`sqlite_errorname` を確認し、driver 情報がない場合は error message に fallback します。
`unique_violation_constraint_name()` は driver が提供する制約名を返し、取得できない場合は
`None` を返します。

endpoint では一意制約違反を HTTP 409 などの conflict response に変換し、制約名が取得できれば
どの入力項目の重複かを選ぶために使えます。その他の `IntegrityError` は再送出してください。
transaction の rollback は session を管理する呼び出し側の責務です。

## 一括代入とシリアライズの allowlist

`update_from_dict()` には明示的な allowlist が必要です。`allowed_fields` を渡すか、class
attribute `updatable_fields` を設定してください。どちらもない場合は `ValueError` が発生します。
`updatable_fields`、`sensitive_fields`、`serializable_fields` はモデルクラスで設定します。
インスタンスの属性でこれらの値を上書きしても、更新やシリアライズの制限は変わりません。
`BaseModel` の constructor はこれらの設定名と、マップされていない属性名を keyword argument として
受け付けません。

```python
from sqlalchemy import String, create_engine
from sqlalchemy.orm import Mapped, Session, mapped_column

from repom import BaseModel


class Profile(BaseModel):
    __tablename__ = "profiles"
    updatable_fields = {"display_name", "bio"}

    display_name: Mapped[str] = mapped_column(String(100))
    bio: Mapped[str] = mapped_column(String(500))
    is_admin: Mapped[bool] = mapped_column(default=False)


engine = create_engine("sqlite:///:memory:")
BaseModel.metadata.create_all(engine)

with Session(engine) as session:
    profile = Profile(display_name="User", bio="", is_admin=False)
    session.add(profile)
    session.flush()
    profile.update_from_dict({"display_name": "New name", "is_admin": True})
    assert profile.display_name == "New name"
    assert profile.is_admin is False
```

primary-key column（mapper から解決し、column 名は問いません）、`created_at`、`updated_at`、
および model にある場合の `deleted_at` は、`updatable_fields` や `allowed_fields` に含まれていても
常に除外されます。`exclude_fields` は1回の呼び出しに限って allowlist をさらに狭めますが、
対象を広げることはできません。

`to_dict()` は既定ですべての column を返します。password hash などの column を出力から除くには
`sensitive_fields` を設定してください。`serializable_fields` を設定すると、明示した項目だけを
返せます。`sensitive_fields` に含まれる column は、`serializable_fields` にも含まれていても
常に出力されません。

```python
from repom import BaseModel


class Profile(BaseModel):
    __tablename__ = "profiles"
    sensitive_fields = {"password_hash"}
```

## 関連資料

- [Soft Delete ガイド](soft_delete_guide.md)
- [モデルガイド一覧](README.md)
