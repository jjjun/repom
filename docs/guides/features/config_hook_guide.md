# CONFIG_HOOK ガイド

## 概要

**CONFIG_HOOK** は、設定オブジェクトを起動時に差し替えるための仕組みです。
環境変数で関数を指定するだけで、パッケージの設定を柔軟に変更できます。
repom でもこの仕組みを採用していますが、フレームワークやパッケージに依存しません。

---

## 目次

- [基本的な使い方](#基本的な使い方)
- [動作の仕組み](#動作の仕組み)
- [トラブルシューティング](#トラブルシューティング)
- [ベストプラクティス](#ベストプラクティス)
- [関連ドキュメント](#関連ドキュメント)

---

## 基本的な使い方

### 1. hook 関数を定義

設定オブジェクトを受け取り、変更して返す関数を用意します。

```python
# myapp/config.py
def hook_config(config):
    config.feature_flag = True
    return config
```

### 2. 環境変数で指定

`.env` または環境変数で hook 関数を指定します。

```bash
# .env
CONFIG_HOOK=myapp.config:hook_config
```

```powershell
$env:CONFIG_HOOK='myapp.config:hook_config'
```

---

## 動作の仕組み

### 初期化フロー

```
1. パッケージの設定モジュールが読み込まれる
   ↓
2. 設定オブジェクトが生成される
   ↓
3. CONFIG_HOOK の読み取り処理が呼ばれる
   ↓
4. 環境変数 CONFIG_HOOK を読み取る
   ↓
5. 指定された関数を動的にインポート
   ↓
6. 関数を実行して config を変更
   ↓
7. 変更後の config が返される
   ↓
8. 初期化が完了する
```

---

## トラブルシューティング

### Q1: CONFIG_HOOK が適用されない

**症状**: 環境変数を設定したのに、設定が反映されない

**確認方法**:

```python
import os

print("CONFIG_HOOK:", os.getenv("CONFIG_HOOK"))
```

**原因と対処**:

1. **環境変数が設定されていない**
   ```powershell
   # 確認
   echo $env:CONFIG_HOOK
   
   # 設定
   $env:CONFIG_HOOK='mine_py.config:hook_config'
   ```

2. **.env ファイルが読み込まれていない**
   ```python
    from dotenv import load_dotenv
    load_dotenv("/path/to/.env")
   ```

3. **関数のパスが間違っている**
   ```bash
   # 正しい: module.path:function_name
   CONFIG_HOOK=mine_py.config:hook_config
   
   # 間違い: ファイルパスやスラッシュ
   CONFIG_HOOK=mine_py/config.py:hook_config  # ❌
   ```

### Q2: ImportError が発生する

**症状**: `ModuleNotFoundError: No module named 'mine_py'`

**原因**: Python パスにモジュールが含まれていない

**対処**:

```python
# プロジェクトルートを PYTHONPATH に追加
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
```

または `pyproject.toml` で設定：

```toml
[tool.poetry]
packages = [
    { include = "mine_py", from = "src" }
]
```

### Q3: 設定が部分的にしか反映されない

**症状**: 一部の設定だけが適用されている

**原因**: hook 関数で `return config` を忘れている

```python
# ❌ 間違い: return を忘れている
def hook_config(config):
    config.feature_flag = True
    # return config

# ✅ 正しい
def hook_config(config):
    config.feature_flag = True
    return config
```

### Q4: 関数が見つからない

**症状**: `AttributeError: module 'mine_py.config' has no attribute 'hook_config'`

**原因**: 関数名のスペルミス

```bash
# 環境変数の関数名と実際の関数名を確認
CONFIG_HOOK=mine_py.config:hook_config

# Python ファイル内
def hook_config(config):  # ← 名前が一致しているか確認
    ...
```

## ベストプラクティス

1. hook 関数は軽量に保つ
2. 必ず `return config` を返す
3. 機密情報は環境変数から取得する
4. 変更は必要最小限に留める

---

## 関連ドキュメント

- [README.md の設定概要](../../../README.md#環境変数)
- [モデル自動インポートガイド](auto_import_models_guide.md)
- [ロギングガイド](logging_guide.md)
- [PostgreSQL セットアップガイド](../postgresql/postgresql_setup_guide.md)
