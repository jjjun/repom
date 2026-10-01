# モデルガイド一覧

共有のモデル基盤と、必要に応じて追加する振る舞いについて説明します。

## ガイド

- [システムカラムとカスタム型](system_columns_and_custom_types.md)
- [Soft Delete](soft_delete_guide.md)
- [ManyToManyMixin](many_to_many_guide.md)
- [一意制約違反の判定](system_columns_and_custom_types.md#一意制約違反の判定)

## 関連ガイド

- [NUL byte の検証](../features/nul_byte_validation.md)

アプリケーション固有のモデルは利用側プロジェクトで定義してください。
`BaseModel` を継承し、必要な共有機能だけを追加します。FastAPI 用の Pydantic schema
生成は利用側 framework の責務です。
