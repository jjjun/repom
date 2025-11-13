# repom SQLAlchemy Issue Investigation

このディレクトリには、mine-py から報告された repom パッケージの SQLAlchemy relationship 解決問題に関する調査資料が含まれています。

## ファイル一覧

### 1. `repom-sqlalchemy-relationship-issue.md`
- **用途**: 問題の詳細レポート
- **内容**: 
  - 問題概要と再現方法
  - エラーメッセージとスタックトレース
  - 想定される解決方向性
  - 調査が必要な箇所

### 2. `diagnose_repom_issue.py`
- **用途**: 問題再現・診断スクリプト
- **使用方法**:
  1. repom リポジトリにコピー
  2. `your_models` を実際のモデルパッケージに置き換え
  3. `ModelA`, `ModelB` を実際の相互参照モデルに置き換え
  4. 実行して問題を再現・診断

## 調査の優先順位

### High Priority
1. **repom/base_model.py の `get_response_schema()` メソッド**
   - Line 188: `inspect(cls).mapper.column_attrs` の動作
   - SQLAlchemy マッパー初期化タイミングの問題

### Medium Priority  
2. **SQLAlchemy レジストリ管理**
   - クラス登録順序の問題
   - `mine_db` との差異分析

### Low Priority
3. **代替実装の検討**
   - 遅延評価やエラーハンドリングの追加

## 期待される成果

- `get_response_schema()` での SQLAlchemy relationship エラーの解決
- `mine_db` から `repom` への移行時の互換性向上
- 循環参照のあるモデルでも正常動作するような改善

## 報告元プロジェクト情報

- **プロジェクト**: mine-py
- **GitHub**: jjjun/py-mine
- **ブランチ**: migrate/mine-db-to-repom
- **連絡先**: mine-py project team