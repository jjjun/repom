# Issue: docker_manager テストの絵文字エンコードエラー（Windows cp932）

## Status
- **Created**: 2026-05-05
- **Priority**: High
- **Complexity**: Low

## Problem Description

`poetry run pytest tests/unit_tests` を実行すると、`TestDockerManagerStart::test_start_compose_file_not_found` が `UnicodeEncodeError` で失敗する。`pyproject.toml` の `-x` フラグにより、以降の全テスト（700件以上）が実行されなくなる。

### 実際のエラー

```
FAILED tests/unit_tests/docker_manager/test_docker_manager.py::TestDockerManagerStart::test_start_compose_file_not_found
- UnicodeEncodeError: 'cp932' codec can't encode character '\U0001f433' in position 0: illegal multibyte sequence

!!!!!!!!!!!!!!!!!!!!!!!!!! stopping after 1 failures !!!!!!!!!!!!!!!!!!!!!!!!!!
======================== 1 failed, 31 passed in 2.69s =========================
```

## Root Cause

### 発生条件

失敗は **単体実行では再現しない**。**テストスイート全体での実行時のみ発生**する。

### 再現ステップ

1. `test_start_success`（capsys 使用）が実行される
2. capsys テスト完了後、pytest が `--capture=tee-sys` モードを復元
3. 復元された tee ラッパーが実 stdout（Windows cp932 コンソール）への参照を持つ
4. `test_start_compose_file_not_found`（capsys なし）が実行される
5. `manager.start()` が `print_message("🐳", ...)` を呼び出す
6. pytest の `_pytest/capture.py:219` で `self._other.write(s)` が cp932 エンコードに失敗

```
repom\_\docker_manager.py:370: in start
    print_message("\U0001f433", f"Starting {self.get_container_name()} container...")
repom\_\docker_manager.py:251: in print_message
    print(f"{symbol} {message}")
_pytest/capture.py:219: in write
    return self._other.write(s)
E   UnicodeEncodeError: 'cp932' codec can't encode character '\U0001f433'
```

### なぜ単体実行では通るか

単体実行時は capsys による tee-sys の状態変化が起きないため、実 stdout への書き込みが直接行われ、絵文字が正常に出力される。

## Expected Behavior

`poetry run pytest tests/unit_tests` が全テスト失敗なく完走する。

## Actual Behavior

31 テスト通過後に `test_start_compose_file_not_found` で `UnicodeEncodeError` が発生し、`-x` フラグにより全テストが停止する。

## Impact

- `tests/unit_tests` で **700件以上のテストが実行されない**
- `test_repom_info_command_runs` など後続テストがすべてスキップされる
- CI/CD 環境（Windows）でのテスト実行が完全にブロックされる

## Solution

以下の 2 つのアプローチがある。

### 案 A: `PYTHONUTF8=1` 環境変数で解決（推奨）

`pyproject.toml` の pytest 設定に環境変数を追加：

```toml
[tool.pytest.ini_options]
env = ["PYTHONUTF8=1"]
```

または pytest 実行時に指定：

```powershell
$env:PYTHONUTF8='1'; poetry run pytest tests/unit_tests
```

### 案 B: `print_message()` にエンコードエラー対策を追加

`repom/_/docker_manager.py` の `print_message()` を修正：

```python
def print_message(symbol, message, details=None):
    try:
        print(f"{symbol} {message}")
    except UnicodeEncodeError:
        print(f"[{symbol}] {message}".encode('ascii', errors='replace').decode())
    if details:
        for detail in details:
            print(f"  {detail}")
```

### 推奨: 案 A

`PYTHONUTF8=1` は Python 3.7+ でサポートされており、標準的な解決策。`print_message()` の変更が不要で影響範囲が最小。

## Affected Files

- `repom/_/docker_manager.py` — `print_message()` 関数（絵文字使用）
- `tests/unit_tests/docker_manager/test_docker_manager.py` — `TestDockerManagerStart` クラス
- `pyproject.toml` — pytest 設定（`-x`, `--capture=tee-sys`）

## Reproduction Command

```powershell
# 失敗する（テストスイート全体）
poetry run pytest tests/unit_tests

# 通る（単体実行）
poetry run pytest "tests/unit_tests/docker_manager/test_docker_manager.py::TestDockerManagerStart::test_start_compose_file_not_found"
```

## Related

- `test_repom_info_command_runs` — この失敗のせいで `-x` により到達不能になっているテスト
- Windows cp932 / UTF-8 エンコード問題
