# NUL byte の検証

repom は、SQLAlchemy の mapped column の型が `TypeDecorator` を通した場合も含めて
`String` または `JSON` 系の型に解決されるとき、値に NUL byte (`0x00`) が含まれることを
拒否します。対象には `CustomJSON`、`ListJSON`、`ARRAY(String)` と、入れ子になった dict の
key / value が含まれます。`NulByteError` は column 名と byte offset を示します。document
のエラーには key path も含まれるため、アプリケーションで 4xx response に対応付けられます。

この検証は、sync / async のどちらでも、`BaseModel` subclass に登録された mapper の
`before_insert` / `before_update` listener により、SQLAlchemy の unit-of-work `flush` 時に実行されます。
検証対象の値は `str` と、入れ子になった `dict`、`list`、`tuple` です。更新時は検証だけのために
deferred column を読み込まないよう、未ロードまたは変更されていない attribute を skip します。
`BaseRepository.bulk_update` と `AsyncBaseRepository.bulk_update` も plain value を検証しますが、
SQL expression value は検証しません。

`session.execute(insert(...))` / `session.execute(update(...))`（ORM bulk parameter list を含む）、
`bulk_insert_mappings`、`bulk_save_objects` はこの検証を通りません。また、plain
`repom.database.Base` を基底にする model には mapper listener が登録されません。このほかの経路で
書き込まれた値には NUL byte が含まれる可能性があります。dict や list の in-place mutation は、
SQLAlchemy の mutable tracking（例: `MutableDict`）を使うか、新しい値を代入しない限り書き込まれず、
検証もされません。

String 型の式を使う `column_property()` がある model では、現在 `_string_columns()` が式に `.table`
を参照して `AttributeError` を起こし、flush に失敗します。これは検証をすり抜けるものではなく、
書き込みを止める fail-closed の不具合です。

## 既存の PostgreSQL JSON / JSON-over-TEXT 値の検出

この検証が導入される前に書き込まれた値が残っている可能性のある `json` または `jsonb` column
では、pattern を使わない検索で候補を広く拾います。

```sql
SELECT id
FROM my_table
WHERE strpos(payload::text, chr(92) || 'u0000') > 0;
```

各候補を `jsonb` に cast して確認します。cast が失敗すれば保存できない値です。cast が成功
すれば、`\\u0000` について説明する文章のような通常の escape sequence です。

```sql
SELECT payload::jsonb
FROM my_table
WHERE id = :id;
```

`TEXT` を基底型とする `TypeDecorator` で JSON document を保存している場合、`jsonb` cast は
使えません。同じ escape sequence を text column から検索します。

```sql
SELECT id, payload
FROM my_table
WHERE strpos(payload, chr(92) || 'u0000') > 0;
```

その後、各候補を `json.loads` で parse し、document を再帰的に調べて実際の NUL byte があるか
確認します。ここでも text 検索は候補を広く拾うため、`\\u0000` を含む通常の文章は false
positive です。parse 後に実際の NUL byte が見つからない限り、保存できない値として扱わないでください。

## 性能

この repository の benchmark では、scalar string value を使った 1,000 row の insert は平均
45.3018 ms でした。100 個の nested JSON item を含む payload で同じ insert を行うと平均
352.1811 ms となり、約 7.8 倍、row あたり約 307 microseconds の検証コストが追加されました。
大きな crawl 済み JSON payload を保存する利用側では、この document の走査コストを考慮してください。
