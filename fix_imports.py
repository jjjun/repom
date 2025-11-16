import pathlib

# tests/unit_tests 配下の全 .py ファイルを検索
files = list(pathlib.Path('tests/unit_tests').rglob('*.py'))

# 不要なインポート文を削除
target_import = 'from tests.db_test_fixtures import db_test\n'
processed = 0
skipped = 0

for f in files:
    try:
        # UTF-8で試す
        content = f.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            # Shift-JISで試す
            content = f.read_text(encoding='shift-jis')
        except UnicodeDecodeError:
            print(f'⚠ Skipped (encoding issue): {f}')
            skipped += 1
            continue

    if target_import in content:
        new_content = content.replace(target_import, '')
        try:
            f.write_text(new_content, encoding='utf-8')
            processed += 1
            print(f'✓ {f}')
        except Exception as e:
            print(f'✗ Error writing {f}: {e}')

print(f'\n処理完了: {processed}ファイル, スキップ: {skipped}ファイル')
