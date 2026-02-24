"""Docker コンテナ管理の統一基盤

repom と外部プロジェクト（fast-domain など）で共通利用する Docker 操作基盤です。
docker-compose コマンド実行、readiness check、コンテナステータス確認などを
抽象化し、サービス固有の実装は subclass で行います。

Example:
    >>> from repom._.docker_manager import DockerManager
    >>> from repom.config import config
    >>> 
    >>> class PostgresManager(DockerManager):
    ...     def __init__(self, config):
    ...         self.config = config
    ...     
    ...     def get_container_name(self) -> str:
    ...         return self.config.postgres.container.get_container_name()
    >>> 
    >>> manager = PostgresManager(config)
    >>> manager.start()  # PostgreSQL を起動
    >>> manager.stop()   # PostgreSQL を停止
"""

import subprocess
import time
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Callable, Optional


class DockerCommandExecutor:
    """docker/docker-compose コマンド実行の共通ユーティリティ

    全メソッドはスタティックで、ステートレスな設計です。
    subprocess.run をラップし、共通のエラーハンドリングと
    メッセージング を提供します。
    """

    @staticmethod
    def run_docker_compose(
        command: str,
        compose_file: Path,
        cwd: Optional[Path] = None,
        capture_output: bool = False,
        project_name: Optional[str] = None,
    ) -> Optional[str]:
        """docker-compose コマンドを実行

        Args:
            command: 実行コマンド（例: "up -d", "stop", "down -v"）
            compose_file: docker-compose.yml のパス
            cwd: 作業ディレクトリ（デフォルト: compose_file の親）
            capture_output: True なら stdout を返す
            project_name: Docker Compose プロジェクト名（-p オプション）

        Returns:
            capture_output=True の場合は stdout、否則 None

        Raises:
            subprocess.CalledProcessError: コマンド失敗（exit code != 0）
            FileNotFoundError: docker-compose コマンド不在
        """
        if cwd is None:
            cwd = compose_file.parent

        cmd = ["docker-compose"]
        if project_name:
            cmd.extend(["-p", project_name])
        cmd.extend(["-f", str(compose_file)])
        cmd.extend(command.split())

        try:
            result = subprocess.run(
                cmd,
                check=True,
                cwd=str(cwd),
                capture_output=capture_output,
                text=True,
            )
            return result.stdout if capture_output else None
        except FileNotFoundError as e:
            raise FileNotFoundError(
                "docker-compose command not found. "
                "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
            ) from e

    @staticmethod
    def get_container_status(container_name: str) -> str:
        """docker ps でコンテナのステータスを取得

        Args:
            container_name: コンテナ名

        Returns:
            ステータス文字列（例: "Up 10 minutes"）
            見つからない場合は空文字列

        Raises:
            FileNotFoundError: docker コマンド不在
        """
        try:
            result = subprocess.run(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"name={container_name}",
                    "--format",
                    "{{.Status}}",
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except FileNotFoundError as e:
            raise FileNotFoundError(
                "docker command not found. "
                "Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
            ) from e

    @staticmethod
    def wait_for_readiness(
        check_func: Callable[[], bool],
        max_retries: int = 30,
        interval_sec: int = 1,
        service_name: str = "Service",
    ) -> None:
        """Readiness check（汎用ループ）

        サービスの起動を待機します。定期的に check_func を呼び出し、
        True を返すまで待機します。5秒ごとに進捗を表示します。

        Args:
            check_func: 健全性確認関数（True = 起動完了、False = まだ起動中）
            max_retries: 最大リトライ回数（秒単位）
            interval_sec: リトライ間隔（秒、デフォルト: 1秒）
            service_name: サービス名（メッセージ表示用）

        Raises:
            TimeoutError: max_retries 秒以内に起動しなかった
        """
        for attempt in range(max_retries):
            if check_func():
                return

            # 5秒ごとに進捗表示
            if (attempt + 1) % 5 == 0:
                print(f"  Still waiting... ({attempt + 1}/{max_retries}s)")

            time.sleep(interval_sec)

        raise TimeoutError(
            f"{service_name} did not start within {max_retries} seconds"
        )


def print_message(
    symbol: str, message: str, details: Optional[list[str]] = None
) -> None:
    """ユーザーメッセージ表示

    Args:
        symbol: 絵文字（🐳, ✅, ❌ など）
        message: メインメッセージ
        details: 詳細情報（行頭スペース付き）

    Example:
        >>> print_message("🐳", "Starting PostgreSQL container...")
        >>> print_message("✅", "PostgreSQL is ready", [
        ...     "Host: localhost",
        ...     "Port: 5432"
        ... ])
    """
    print(f"{symbol} {message}")
    if details:
        for detail in details:
            print(f"  {detail}")


def validate_compose_file_exists(compose_file: Path, service_name: str) -> None:
    """Compose ファイル存在チェック

    Args:
        compose_file: ファイルパス
        service_name: サービス名（エラーメッセージ用）

    Raises:
        FileNotFoundError: ファイルが見つからない
    """
    if not compose_file.exists():
        print(
            f"⚠️  docker-compose.generated.yml が見つかりません"
        )
        print(f"   Expected: {compose_file}")
        print()
        print(
            f"ヒント: 先に 'poetry run {service_name.lower()}_generate' を実行してください"
        )
        raise FileNotFoundError(f"Compose file not found: {compose_file}")


def format_connection_info(**kwargs) -> list[str]:
    """接続情報をフォーマット

    Args:
        **kwargs: キー値ペア（キーが表示名として使用される）

    Returns:
        整形済みの情報行リスト

    Example:
        >>> format_connection_info(
        ...     Host="localhost",
        ...     Port=5432,
        ...     User="postgres"
        ... )
        ['Host: localhost', 'Port: 5432', 'User: postgres']
    """
    return [f"{key}: {value}" for key, value in kwargs.items()]


class DockerManager(ABC):
    """Docker コンテナ管理の基盤クラス

    サブクラスが実装すべき抽象メソッド:
    - get_container_name()
    - get_compose_file_path()
    - wait_for_service()

    共通メソッド（このクラスが実装）:
    - start()
    - stop()
    - remove()
    - status()
    - is_running()
    """

    @abstractmethod
    def get_container_name(self) -> str:
        """コンテナ名を返す

        Returns:
            コンテナの実行名（docker ps で見える名前）
        """
        pass

    @abstractmethod
    def get_compose_file_path(self) -> Path:
        """docker-compose ファイルのパスを返す

        Returns:
            ファイルパス

        Raises:
            FileNotFoundError: compose ファイルが見つからない
        """
        pass

    @abstractmethod
    def wait_for_service(self, max_retries: int = 30) -> None:
        """サービス起動を待機（サービス固有の健全性確認）

        Args:
            max_retries: 最大リトライ回数（秒単位）

        Raises:
            TimeoutError: max_retries 秒以内に起動しなかった
        """
        pass

    def get_project_name(self) -> str:
        """Docker Compose プロジェクト名を取得

        container_name をそのままプロジェクト名として使用。
        これにより各サービス（Redis/PostgreSQL）が独立したプロジェクトになり、
        orphan container の警告を防止できる。

        Returns:
            コンテナ名（get_container_name() の値）
        """
        return self.get_container_name()

    def start(self) -> None:
        """コンテナを起動

        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose up -d 実行
        3. wait_for_service() で起動待機
        4. ユーザーメッセージ表示
        """
        print()
        print_message("🐳", f"Starting {self.get_container_name()} container...")

        try:
            compose_file = self.get_compose_file_path()
        except FileNotFoundError as e:
            print_message("❌", str(e))
            sys.exit(1)

        try:
            DockerCommandExecutor.run_docker_compose(
                "up -d", compose_file, cwd=compose_file.parent,
                project_name=self.get_project_name()
            )
        except subprocess.CalledProcessError as e:
            print_message("❌", f"Failed to start container: {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            print_message("❌", str(e))
            sys.exit(1)

        print("⏳ Waiting for service to be ready...")

        try:
            self.wait_for_service()
            print_message("✅", f"{self.get_container_name()} is ready")
        except TimeoutError as e:
            print_message("❌", str(e))
            sys.exit(1)

    def stop(self) -> None:
        """コンテナを停止（削除しない）

        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose stop 実行
        3. ユーザーメッセージ表示
        """
        try:
            compose_file = self.get_compose_file_path()
            validate_compose_file_exists(
                compose_file, self.get_container_name()
            )
        except FileNotFoundError:
            return

        print_message("🛑", f"Stopping {self.get_container_name()} container...")

        try:
            DockerCommandExecutor.run_docker_compose(
                "stop", compose_file, cwd=compose_file.parent,
                project_name=self.get_project_name()
            )
            print_message("✅", f"{self.get_container_name()} stopped")
        except subprocess.CalledProcessError as e:
            print_message("❌", f"Failed to stop container: {e}")
            sys.exit(1)

    def remove(self) -> None:
        """コンテナとボリュームを削除

        処理流れ:
        1. get_compose_file_path() で file 確認
        2. docker-compose down -v 実行（ボリューム削除）
        3. ユーザーメッセージ表示
        """
        try:
            compose_file = self.get_compose_file_path()
            validate_compose_file_exists(
                compose_file, self.get_container_name()
            )
        except FileNotFoundError:
            return

        print_message(
            "🧹", f"Removing {self.get_container_name()} container and volumes..."
        )

        try:
            DockerCommandExecutor.run_docker_compose(
                "down -v", compose_file, cwd=compose_file.parent,
                project_name=self.get_project_name()
            )
            print_message("✅", f"{self.get_container_name()} removed")
        except subprocess.CalledProcessError as e:
            print_message("❌", f"Failed to remove container: {e}")
            sys.exit(1)

    def status(self) -> bool:
        """ステータス確認（実行中か）

        Returns:
            True = 実行中、False = 停止中/見つからない
        """
        try:
            status_text = DockerCommandExecutor.get_container_status(
                self.get_container_name()
            )
            return bool(status_text)
        except FileNotFoundError:
            return False

    def is_running(self) -> bool:
        """実行中か確認（status() の alias）

        Returns:
            True = 実行中、False = 停止中
        """
        return self.status()
