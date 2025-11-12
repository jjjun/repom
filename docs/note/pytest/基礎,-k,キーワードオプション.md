# `-k` オプション、キーワードオプション

`-k` オプションというのは `keyword` オプションの略です。テスト関数名、クラス名、またはファイル名に特定のキーワードが含まれているテストをフィルタリングして実行する為のオプションですね。

次のようなファイルがあるとします。

```py
# docs/test_note1.py
def test_sample1():
    print('\n\n test_sample1 \n\n')

def test_sample2():
    print('\n\n test_sample2 \n\n')
```

```py
# docs/test_note2.py
def test_sample3():
    print('\n\n test_sample3 \n\n')

def test_sample4():
    print('\n\n test_sample4 \n\n')

def test_note1():
    print('\n\n test_note1 at test_note2 \n\n')
```

次の様に実行をしました。

```bash
pytest -k 'note1'
# pytest -k 'test_note1'
# pytest -k 'test_note1.py'
```

この場合、`test_note1.py` に含まれている全てのテストと、`note1` を含んでいる全てのテスト関数やクラスが実行されます。今回の例で言うと、次のテスト関数が実行されるね。

- test_note1.py: `test_sample1()`
- test_note1.py: `test_sample2()`
- test_note2.py: `test_note1()`

次のようにして実行した場合、`test_note2.py: test_note1()` は実行されず、`test_note1.py` に含まれる全てのテストを実行します。

```
pytest -k 'test_note1.py'
```

もし `pytest -k 'note'` としたなら、`test_note1.py` と `test_note2.py` 内の全てのテストが実行されます。


## テストファイルと `-k` オプションを併用する(指定テストファイル内の特定のキーワードに一致するテストを実行)

```
pytest 'docs/pytest/tests/test_note1.py' -k 'sample'
```

## 複数のキーワードを指定する

`-k` オプションはキーワードオプションなので、実行するテストファイルを指定するものではないです。ただ、ファイル名もキーワードとして考慮してくれるので、特定のテストファイル下のテストを実行する事が出来ます。

```
pytest -k 'note1.py and sample1'

# 条件として not も使える。note1.py に含まれない
# pytest -k 'not note1.py and sample1'
```

上記の様に書くと、事実上 `note1.py` に含まれる `sample1` が含まれるテストを実行します。条件として `not` も使う事が出来ますし、`or` も使う事が出来ます。

また、ディレクトリ名もキーワードとして考慮するので、`docs and test_note1.py` と書けば、一応 `docs` 配下の `test_note1.py` を指定する事が出来ます(厳密には `docs` と `test_note1.py` が含まれるテストを指定してるだけなので、`docs` 配下という訳です)。

ただ、`-k` オプションは実行するテストファイルを指定する物では無いので、あくまで特定のキーワードを指定する目的で使うのが良きです。

