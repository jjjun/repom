# Repository Guides

リポジトリパターンとセッション管理に関するガイドです。

## 📖 ガイド一覧

### 初級編
- **[BaseRepository 基礎ガイド](base_repository_guide.md)**  
  リポジトリの作成、CRUD操作の基本

### 中級編
- **[検索・クエリガイド](repository_advanced_guide.md)**  
  find(), ソート、ページネーション、カウント、Eager Loading（N+1問題の解決）

- **[FilterParams ガイド](repository_filter_params_guide.md)**  
  FastAPI との統合、検索パラメータの型安全な処理

- **[SoftDelete ガイド](repository_soft_delete_guide.md)**  
  論理削除（復元可能な削除）、soft_delete(), restore(), permanent_delete()

### その他
- **[セッションパターン](repository_session_patterns.md)** - セッション管理パターンとベストプラクティス
- **[非同期リポジトリ](async_repository_guide.md)** - AsyncBaseRepository の使い方


---

## 🎯 このディレクトリの対象

- BaseRepository / AsyncBaseRepository の使い方
- セッション管理のパターン
- トランザクション制御
- FastAPI との統合
- Eager Loading（default_options）によるパフォーマンス最適化
- FilterParams による型安全な検索パラメータ
- SoftDelete による論理削除機能
