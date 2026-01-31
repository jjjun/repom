"""
マスターデータ同期スクリプト

data_master/ ディレクトリ配下の Python ファイルを読み込み、
定義されたマスターデータを DB に同期（Upsert）します。

使用方法:
    poetry run db_sync_master

    # 環境指定
    EXEC_ENV=dev poetry run db_sync_master
"""

import os
import sys
import importlib.util
from pathlib import Path
from typing import Generator, Tuple, Type, List, Dict, Any

from repom.utility import load_models
from repom.config import config
from repom.database import get_standalone_sync_transaction
from repom import BaseRepository


def load_master_data_files(directory: str) -> Generator[Tuple[Type, List[Dict[str, Any]]], None, None]:
    """
    マスターデータファイルを読み込む

    Args:
        directory: マスターデータディレクトリのパス

    Yields:
        (MODEL_CLASS, MASTER_DATA) のタプル

    Raises:
        ValueError: MODEL_CLASS または MASTER_DATA が定義されていない場合
        FileNotFoundError: ディレクトリが存在しない場合
    """
    if not os.path.exists(directory):
        raise FileNotFoundError(f"マスターデータディレクトリが見つかりません: {directory}")

    # .py ファイルをソート順に取得（001_, 002_ などのプレフィックスで順序制御可能）
    files = sorted([f for f in os.listdir(directory) if f.endswith('.py') and not f.startswith('_')])

    if not files:
        print(f"警告: マスターデータファイルが見つかりません（{directory}）")
        return

    for filename in files:
        filepath = os.path.join(directory, filename)

        # モジュールとして動的にロード
        spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
        if spec is None or spec.loader is None:
            print(f"警告: {filename} をロードできませんでした")
            continue

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # MODEL_CLASS の検証
        if not hasattr(module, 'MODEL_CLASS'):
            raise ValueError(f"{filename}: MODEL_CLASS が定義されていません")

        # MASTER_DATA の検証
        if not hasattr(module, 'MASTER_DATA'):
            raise ValueError(f"{filename}: MASTER_DATA が定義されていません")

        model_class = getattr(module, 'MODEL_CLASS')
        master_data = getattr(module, 'MASTER_DATA')

        # データ型の検証
        if not isinstance(master_data, list):
            raise ValueError(f"{filename}: MASTER_DATA は list 型である必要があります")

        yield model_class, master_data


def sync_master_data(model_class: Type, data_list: List[Dict[str, Any]], session) -> int:
    """
    マスターデータを同期（Upsert）

    Args:
        model_class: モデルクラス
        data_list: マスターデータのリスト
        session: SQLAlchemy セッション

    Returns:
        同期したレコード数
    """
    if not data_list:
        return 0

    count = 0

    for data in data_list:
        # session.merge() を使って Upsert
        # merge() は id が一致するレコードがあれば UPDATE、なければ INSERT
        instance = session.merge(model_class(**data))
        count += 1

    # flush() でデータベースに反映（commit は transaction() が行う）
    session.flush()

    return count


def main():
    """メイン処理"""
    print("=" * 60)
    print("マスターデータ同期開始")
    print("=" * 60)

    # モデルをロード
    print("\n[1/3] モデルをロード中...")
    load_models()
    print("✓ モデルのロード完了")

    # マスターデータディレクトリの確認
    master_data_dir = config.master_data_path
    print(f"\n[2/3] マスターデータディレクトリ: {master_data_dir}")

    if not master_data_dir:
        print("エラー: master_data_path が設定されていません")
        sys.exit(1)

    try:
        # トランザクション内で全ファイルを処理
        with get_standalone_sync_transaction() as session:
            total_count = 0
            file_count = 0

            print("\n[3/3] マスターデータを同期中...")

            for model_class, master_data in load_master_data_files(master_data_dir):
                model_name = model_class.__name__
                count = sync_master_data(model_class, master_data, session)

                print(f"  ✓ {model_name}: {count} 件")
                total_count += count
                file_count += 1

            print(f"\n{'=' * 60}")
            print(f"同期完了: {file_count} ファイル、{total_count} レコード")
            print(f"{'=' * 60}")

    except FileNotFoundError as e:
        print(f"\nエラー: {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"\nエラー: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nエラー: マスターデータの同期に失敗しました")
        print(f"詳細: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
