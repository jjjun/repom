# Issue Tracker - repom

こ�EチE��レクトリは、repom プロジェクト�E改喁E��案と課題管琁E�Eためのドキュメントを格納します、E

## チE��レクトリ構造

```
docs/issue/
├── README.md              # こ�Eファイル�E�Essue 管琁E��ンチE��クス�E�E
├── completed/             # 完亁E�E解決済み Issue
━E  ├── 001_*.md          # Issue #1�E�完亁E��E
━E  ├── 002_*.md          # Issue #2�E�完亁E��E
━E  └── 003_*.md          # Issue #3�E�完亁E��E
├── in_progress/           # 作業中の Issue
└── backlog/               # 計画中・未着手�E Issue
```

## Issue ライフサイクル

```
backlog/       ↁE計画と優先度付け
    ↁE
in_progress/   ↁE実裁E��業中
    ↁE
completed/     ↁE実裁E��亁E�EチE��ト済み
```

## 🚧 作業中の Issue

現在作業中の Issue はありません。

---

## 📝 計画中の Issue

### Issue #6: SQLAlchemy 2.0 スタイルへの移衁E

**ファイル**: `backlog/006_migrate_to_sqlalchemy_2_0_style.md`

**スチE�Eタス**: �E� Phase 1 実施中�E�E025-11-15�E�E

**概要E*:
repom プロジェクト�E体を SQLAlchemy 2.0 の推奨スタイル�E�EMapped[]` 型ヒンチE+ `mapped_column()`�E�に移行する。型安�E性の向上、エチE��タ補完�E改喁E��封E��のバ�Eジョン互換性を確保する、E

**進捁E*:
- ✁EPhase 1.1: BaseModel migration 完亁E(Commit: 964504d)
- ⚠�E�EKnown issue: test_forward_refs_generic_list_response_pattern (AutoDateTime 問顁E

**実裁E��画**:
- Phase 1: repom コアの移行！EaseModel, サンプルモチE���E�E
- Phase 2: チE��トコード�E移行！E00+ 箁E���E�E
- Phase 3: ドキュメント整傁E
- Phase 4: 外部プロジェクト移行ガイド作�E
- Phase 5: 実�Eロジェクト�E移衁E

---

### Issue #7: Annotation Inheritance の実裁E��証

**ファイル**: `backlog/007_annotation_inheritance_validation.md`

**スチE�Eタス**: 📝 調査征E���E�E025-11-15�E�E

**概要E*:
Issue #006 (Phase 1.1) で BaseModel の `__annotations__` 継承問題を修正したが、この実裁E��正しいのか、他�E影響がなぁE��を調査する忁E��がある、E

**調査頁E��**:
1. Python の `__annotations__` 継承動作�E確誁E
2. SQLAlchemy 2.0 の推奨パターンとの整合性
3. 他�Eフレームワークとの互換性�E�EastAPI, Pydantic�E�E
4. エチE��ケースの検証�E�多重継承, Mixin�E�E
5. パフォーマンスへの影響
6. 代替実裁E�E検訁E

**関連 Issue**: #006 (SQLAlchemy 2.0 migration)

**影響篁E��**:
- repom 冁E��: BaseModel, サンプルモチE��, チE��トコーチE
- 外部プロジェクチE repom を使用するすべてのプロジェクチE

**技術的決定事頁E*:
- `Column()` ↁE`mapped_column()` + `Mapped[]` 型ヒンチE
- relationship には斁E���Eで前方参�E�E�循環参�E回避�E�E
- 後方互換性を維持E��段階的移行！E
- 移行ガイド提供（外部プロジェクト向け！E

---

---

## 📋 完亁E��み Issue

### Issue #6: SQLAlchemy 2.0 スタイルへの移衁E

**ファイル**: `completed/006_migrate_to_sqlalchemy_2_0_style.md`

**スチE�Eタス**: ✁E完亁E��E025-11-15�E�E

**概要E*:
repom プロジェクト�E体を SQLAlchemy 2.0 の推奨スタイル�E�EMapped[]` 型ヒンチE+ `mapped_column()`�E�に移行。型安�E性の向上、エチE��タ補完�E改喁E��封E��のバ�Eジョン互換性を確保、E

**実裁E�E容**:
- Phase 1: repom コア移衁E✁E
  - BaseModel migration (Commit: 964504d)
  - Sample models migration (Commit: ae71332)
  - AutoDateTime docstring (Commit: a65f6fe)
  - BaseModelAuto docstring (Commit: c7d787a)
  
- Phase 2: チE��トコード移衁E✁E
  - 17 チE��トファイル、E5+ Column() 定義を移衁E
  - test_forward_refs_generic_list_response_pattern 修正 (Commit: 92f50d1)
  - Commits: 87b5fb8, d56f382, cbef52e, 92f50d1
  
- Phase 3: ドキュメント整傁E✁E
  - guides, README, copilot-instructions 更新
  - Commits: 168b70a, 1379ac0

**チE��ト結果**:
- 186/186 unit tests passing (1 skipped - FastAPI)
- 本番環墁E��チE��ト完亁E�E問題なぁE

**技術的成果**:
- Annotation inheritance バグの発見と修正
- AutoDateTime 設計仕様�E明確匁E
- 動的カラム追加と型ヒント�E統合手法確竁E

**関連コミッチE*: 964504d, ae71332, a65f6fe, c7d787a, 87b5fb8, d56f382, cbef52e, 92f50d1, 168b70a, 1379ac0

---

### Issue #5: 柔軟な auto_import_models 設宁E

**ファイル**: `completed/005_flexible_auto_import_models.md`

**スチE�Eタス**: ✁E完亁E��E025-11-15�E�E

**概要E*:
設定ファイルで褁E��のモチE��チE��レクトリを指定できる機�Eを実裁E��`models/__init__.py` への手動記述を不要にし、Alembic マイグレーションと db コマンドでのモチE��認識ミスを防ぐ、E

**実裁E�E容**:
- Phase 1: 基本機�E ✁E
  - `auto_import_models_by_package()` 関数�E�セキュリチE��検証付き�E�E
  - `auto_import_models_from_list()` 関数�E�バチE��インポ�Eト！E
  - `MineDbConfig` プロパティ�E�Eodel_locations, model_excluded_dirs, allowed_package_prefixes�E�E
  - `load_models()` 修正�E�設定�Eース対応！E
  - 27個�E単体テスト（すべて成功�E�E
  - ガイドドキュメント作�E

- Phase 1.5: 設定制御機�E ✁E
  - `model_import_strict` プロパティ追加�E�デフォルチE False = 警告�Eみ�E�E
  - `load_models()` での `fail_on_error` パラメータ連携
  - 4個�E単体テスト追加�E�合訁E1チE��ト！E
  - ドキュメント更新

**技術的決定事頁E*:
- Python コード！EONFIG_HOOK 経由�E��Eみサポ�EチE
- チE��ォルトで警告�Eみ�E�Emodel_import_strict=False`�E�E
- セキュリチE��検証�E�Eallowed_package_prefixes`、デフォルチE `{'repom.'}`�E�E
- セキュリチE��スキチE�Eは直接呼び出し�Eみ許可
- 後方互換性を維持E��Emodel_locations=None` で従来通り�E�E

**チE��トカバレチE��**:
- 合訁E1チE��ト（セキュリチE��6、パチE��ージインポ�EチE、Config8、統吁E、エラーハンドリング3、実世界3、Strict3�E�E
- すべてのチE��トが成功

**関連ドキュメンチE*:
- 使用ガイチE `docs/guides/auto_import_models_guide.md`
- 允E�EアイチE��ア: `docs/ideas/flexible_auto_import_models.md`�E�E80行に削減！E

---

### Issue #3: response_field 機�EめEBaseModelAuto に移衁E

**ファイル**: `completed/003_response_field_migration_to_base_model_auto.md`

**スチE�Eタス**: ✁E完亁E��E025-11-15�E�E

**概要E*:
Response スキーマ生成機�EめE`BaseModel` から `BaseModelAuto` に移行し、Create/Update/Response の3つのスキーマ生成を一允E��。Phase 6�E�ドキュメント更新�E�まで完亁E��E

**実裁E�E容**:
- Phase 1: 調査と準備 ✁E
- Phase 2: BaseModelAuto への移衁E✁E
- Phase 2.5: シスチE��カラムの自動更新と保護 ✁E
- Phase 3: `info['in_response']` の実裁E✁E
- Phase 4: BaseModel からの削除とカスタム型リネ�Eム�E�保留�E�E
- Phase 5: チE��ト（�EチE��ト合格�E�✅
- Phase 6: ドキュメント更新 ✁E
  - `docs/guides/base_model_auto_guide.md` 作�E�E�E00行！E
  - `docs/guides/repository_and_utilities_guide.md` 作�E�E�E00行！E
  - `README.md` 簡略化！E,388衁EↁE291行！E
  - `.github/copilot-instructions.md` 更新
  - `docs/technical/ai_context_management.md` 作�E
- Phase 7: 外部プロジェクトへの移行通知�E�未実施�E�E

**ドキュメント�E果物**:
- 2つの匁E��皁E��ガイド！Ease_model_auto_guide.md, repository_and_utilities_guide.md�E�E
- AI エージェントが効玁E��に参�Eできる構造
- ト�Eクン消費量�E最適化！E9%で全ガイド同時アクセス可能�E�E

**関連ドキュメント**:
- 実装ガイド: `docs/guides/base_model_auto_guide.md`
- リポジトリガイド: `docs/guides/repository_and_utilities_guide.md`
- 技術詳細: `docs/technical/get_response_schema_technical.md`
- AI コンテキスト管理: `docs/technical/ai_context_management.md`

### Issue #8: Alembic マイグレーションファイルの保存場所制御

**ファイル**: `completed/008_alembic_migration_path_conflict.md`

**ステータス**: ✅ 完了（2025-11-16）

**概要**:
外部プロジェクトで repom を使用する際、マイグレーションファイルの保存場所を制御できない問題を解決。Alembic の制約により `alembic.ini` の `version_locations` を唯一の設定源とする実装に変更。

**最終的な解決策**:
- `alembic.ini` に `version_locations` を明示的に記述
- ファイル作成と実行の両方で同じ設定を使用
- `MineDbConfig._alembic_versions_path` を削除（env.py での動的設定は効かないため）

**実装変更**:
- `config.py`: `_alembic_versions_path` フィールドを完全削除
- `alembic/env.py`: `version_locations` の動的設定を削除
- `alembic.ini`: `version_locations = alembic/versions` を追加
- テスト: `test_alembic_config.py` を削除（機能が存在しなくなったため）

**外部プロジェクト設定**:
```ini
# mine-py/alembic.ini
[alembic]
script_location = submod/repom/alembic
version_locations = %(here)s/alembic/versions
```

**関連ドキュメント**:
- 技術調査: `docs/technical/alembic_version_locations_limitation.md`
- ユーザーガイド: `README.md#alembic-マイグレーション`
- 開発者ガイド: `AGENTS.md#alembic-configuration`

### Issue #1: get_response_schema() の前方参照改善

**ファイル**: `completed/001_get_response_schema_forward_refs_improvement.md`

**スチE�Eタス**: ✁E完亁E��E025-11-14�E�E

**概要E*:
`BaseModel.get_response_schema()` メソチE��の前方参�E解決改喁E��Phase 1�E�標準型の自動解決�E�と Phase 2�E�エラーメチE��ージ改喁E+ 環墁E��エラーハンドリング�E�を実裁E��E

**結果**:
- Phase 1: 標準型�E�Eist, Dict, Optional 等）�E自動解決
- Phase 2: 未定義型�E自動検�EとエラーメチE��ージ改喁E
- チE��チE 31/31 パス�E�Ehase 1: 3チE��チE+ Phase 2: 4チE��ト！E
- ドキュメンチE 匁E��皁E�� README セクション + research チE��レクトリ

**関連ドキュメンチE*:
- 調査: `docs/research/auto_forward_refs_resolution.md`
- 実裁E メイン `README.md` の Phase 1 & 2 セクション参�E
- 技術詳細: `docs/technical/get_response_schema_technical.md`

### Issue #2: SQLAlchemy カラム継承制紁E��よる use_id 設計�E課顁E

**ファイル**: `completed/002_sqlalchemy_column_inheritance_constraint.md`

**スチE�Eタス**: ✁E完亁E��E025-11-14�E�E

**概要E*:
`BaseModel` と `BaseModelAuto` で `use_id` パラメータのチE��ォルト値を制御する際、SQLAlchemy のカラム継承制紁E��より褁E��主キーモチE��で `id` カラムが意図せず継承される問題を解決、E

**結果**:
- 抽象クラス�E�E__tablename__` なし）にはカラムを追加しなぁE��訁E
- 具象クラスのみに `use_id` に基づぁE�� `id` カラムを追加
- `BaseModel` と `BaseModelAuto` の両方でチE��ォルチE`use_id=True` を維持E
- 褁E��主キーモチE��で `use_id=False` を�E示皁E��持E��すれ�E `id` カラムなぁE
- チE��チE 全 103 チE��ト合格

**関連ドキュメンチE*:
- 実裁E `repom/base_model.py` と `repom/base_model_auto.py`
- チE��チE `tests/unit_tests/test_model_no_id.py`

---

## 新しい Issue の作�E

新しい Issue を作�Eする際�E:

1. **Backlog 段隁E*: `backlog/XXX_issue_name.md` にファイル作�E
2. **作業開姁E*: 着手時に `in_progress/XXX_issue_name.md` へ移勁E
3. **完亁E*: 完亁E��に `completed/NNN_issue_name.md` へ移動（連番付与！E

完亁E��み Issue には連番�E�E01, 002, 003...�E�を付与してください、E

---

## 🔧 Issue チE��プレーチE

新しい Issue を追加する際�E、以下�Eフォーマットを使用してください�E�E

```markdown
# Issue #N: [タイトル]

**スチE�Eタス**: 🔴 未着扁E/ 🟡 提案中 / 🟢 進行中 / ✁E完亁E

**作�E日**: YYYY-MM-DD

**優先度**: 髁E/ 中 / 佁E

## 問題�E説昁E

[現状の問題点を説明]

## 提案される解決筁E

[解決策�E提桁E

## 影響篁E��

- 影響を受けるファイル
- 影響を受ける機�E

## 実裁E��画

1. スチE��チE
2. スチE��チE
3. ...

## チE��ト計画

[チE��ト戦略とチE��トケースの説明]

## 関連リソース

- 関連ファイル
- 参老E��E��
```

---

## 🎯 Issue 管琁E�E方釁E

### Issue の作�E
- 改喁E��案、バグ報告、機�E追加リクエストなどめEIssue として管琁E
- 1つの Issue につぁE1つのマ�Eクダウンファイルを作�E
- ファイル名�E `[issue_name].md` の形式（スネ�Eクケース推奨�E�E

### スチE�Eタス管琁E
- 🔴 **未着扁E*: Issue が提起されたが作業開始してぁE��ぁE
- 🟡 **提案中**: 設計�E調査中
- 🟢 **進行中**: 実裁E��業中
- ✁E**完亁E*: 実裁E�EチE��ト�Eドキュメント化が完亁E

### 優先度
- **髁E*: 重大な問題、ブロチE��ー
- **中**: 重要だが緊急ではなぁE
- **佁E*: 改喁E��案、封E��皁E��機�E

---

## 📝 Issue の更新

Issue の進捗があった場合�E、該当ファイルを更新し、このREADME.mdの一覧も更新してください、E

---

最終更新: 2025-11-15
