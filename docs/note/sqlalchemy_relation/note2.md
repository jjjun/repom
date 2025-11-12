## N:1, 1:N, 1:1 構造のテーブルは、本当に必要な時以外は使わない

私の場合次のような事をしていました。そして、そのような構造を止めました。

- コアなデータとその他のデータのテーブルを分ける(1:1) 
- カラム構造が似たテーブルを、中間テーブルを使う事で纏める(1:n, n:1)


## 1:1 構造のテーブル を止めた

先ず、自分用のメモです。1:1構造時に、親モデルのインスタンス生成時に、子モデルのインスタンスも生成する為に次の様に書く事を学びました。`__init__` で初期値を設定できる事は分かっていましたが、`**kwargs` を使うと良い感じに書く事が出来る事を見落としていたのです。書き換えコストは嫌だったけど、よかったね！

```py
def __init__(self, wiki_detail=None, **kwargs):
    super().__init__(**kwargs)
    if ani_wiki_tv_detail:
        self.wiki_detail = wiki_detail
    else:
        self.wiki_detail = WikiDetailModel()
```

私の環境では、次のようなモデルがありました。

- [各アニメのデータ(WikiListModel)](note2_models/wiki_list.py)
- [アニメ詳細ページ(WikiGroupModel)](note2_models/wiki_detail.py)


タスク単位で処理を分けていて、タスク1でWikiListModelにデータが入ります。タスク2でWikiDetailModelにデータが入ります。


`__init__` 内で、初期値として設定したい値を指定する。

```py
def __init__(self, ani_wiki_tv_detail=None, **kwargs):
    super().__init__(**kwargs)
    if ani_wiki_tv_detail:
        self.ani_wiki_tv_detail = ani_wiki_tv_detail
    else:
        self.ani_wiki_tv_detail = AniWikiTvDetailModel()
```


## N:1, 1:N 構造のテーブルを辞めた
...
