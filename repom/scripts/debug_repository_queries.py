"""
デバッグ用スクリプト: リポジトリの find() と to_dict() のクエリログを確認

使い方:
1. python -m repom.scripts.debug_repository_queries を実行
   （引数なしの場合は repom.examples.repositories.sample.SampleRepository を調査）
2. python -m repom.scripts.debug_repository_queries myapp.repositories:UserRepository
   （"module:ClassName" 形式で調査対象のリポジトリクラスを指定）

出力内容:
- find() 実行時のクエリログ
- 最初の結果に対する to_dict() 実行時のクエリログ
- 各ステップごとのクエリ統計
"""

from typing import Type
import inspect
from repom.diagnostics.query_analyzer import QueryAnalyzer
from repom.database import _db_manager
from repom import BaseRepository


def debug_repository_queries(repo_class: Type[BaseRepository]) -> None:
    """
    リポジトリの find() と to_dict() のクエリを分析

    Args:
        repo_class: 調査対象のリポジトリクラス
    """
    print("=" * 70)
    print(f"[INFO] Debug Repository: {repo_class.__name__}")
    print("=" * 70)
    print()

    analyzer = QueryAnalyzer()

    with analyzer.capture():
        with _db_manager.get_sync_session() as session:
            # ✅ 自動推論を活用: session=... で渡す
            repo = repo_class(session=session)

            # ステップ1: find() の実行
            print("[INFO] Step 1: repo.find() を実行中...")
            print("-" * 70)

            # find() メソッドのシグネチャを確認
            sig = inspect.signature(repo.find)
            params = sig.parameters

            # 必須の位置引数があるか確認
            required_params = [
                name for name, param in params.items()
                if param.default == inspect.Parameter.empty
                and param.kind in (inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.POSITIONAL_ONLY)
                and name != 'self'
            ]

            query_count_before = len(analyzer.get_queries())

            # 必須パラメータがある場合はデフォルトインスタンスを渡す
            if required_params:
                # 最初のパラメータの型アノテーションを取得
                first_param_name = required_params[0]
                first_param = params[first_param_name]

                if first_param.annotation != inspect.Parameter.empty:
                    try:
                        # FilterParams などのデフォルトインスタンスを作成
                        param_instance = first_param.annotation()
                        print(f"[INFO] find() に必須パラメータ '{first_param_name}' があります")
                        print(f"   型: {first_param.annotation.__name__}")
                        print(f"   デフォルトインスタンスを渡します: {param_instance}")
                        print()
                        results = repo.find(param_instance)
                    except Exception as e:
                        print(f"[WARN] パラメータインスタンスの作成に失敗: {e}")
                        print("   filters=[] で呼び出します")
                        print()
                        results = repo.find(filters=[])
                else:
                    # 型アノテーションがない場合は filters=[] で試す
                    print(f"[INFO] find() に必須パラメータ '{first_param_name}' がありますが型が不明です")
                    print("   filters=[] で呼び出します")
                    print()
                    results = repo.find(filters=[])
            else:
                # 必須パラメータがない場合は引数なしで呼び出し
                results = repo.find()

            query_count_after_find = len(analyzer.get_queries())

            print(f"[OK] find() 完了: {len(results)} 件取得")
            print(
                f"[INFO] クエリ実行数: {query_count_after_find - query_count_before} 件"
            )
            print()

            # ステップ2: 最初の結果で to_dict() を実行
            if results:
                print("[INFO] Step 2: results[0].to_dict() を実行中...")
                print("-" * 70)

                first_result = results[0]
                print(f"対象レコード ID: {getattr(first_result, 'id', 'N/A')}")

                query_count_before_dict = len(analyzer.get_queries())
                result_dict = first_result.to_dict()
                query_count_after_dict = len(analyzer.get_queries())

                print("[OK] to_dict() 完了")
                print(
                    f"[INFO] クエリ実行数: {query_count_after_dict - query_count_before_dict} 件"
                )
                print()

                # 結果のサマリー表示
                print("[INFO] to_dict() の結果:")
                print("-" * 70)
                for key, value in result_dict.items():
                    # 長い値は省略
                    if isinstance(value, str) and len(value) > 50:
                        display_value = f"{value[:47]}..."
                    elif isinstance(value, list) and len(value) > 3:
                        display_value = f"[{len(value)} items]"
                    else:
                        display_value = value
                    print(f"  {key}: {display_value}")
                print()
            else:
                print("[WARN] find() の結果が空のため、to_dict() をスキップします")
                print()

    # 詳細レポート表示
    print("=" * 70)
    print("[INFO] 詳細クエリレポート")
    print("=" * 70)
    analyzer.print_report(verbose=True)


def main():
    """エントリーポイント"""
    import argparse
    import importlib

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "target",
        nargs="?",
        default=None,
        help='調査対象のリポジトリクラス（"module:ClassName" 形式）。'
             '省略時は repom.examples.repositories.sample.SampleRepository を使用する。',
    )
    args = parser.parse_args()

    if args.target:
        module_name, _, class_name = args.target.partition(":")
        if not class_name:
            parser.error('target は "module:ClassName" 形式で指定してください')
        module = importlib.import_module(module_name)
        repo_class = getattr(module, class_name)
    else:
        from repom.examples.repositories.sample import SampleRepository
        repo_class = SampleRepository

    debug_repository_queries(repo_class)


if __name__ == "__main__":
    main()
