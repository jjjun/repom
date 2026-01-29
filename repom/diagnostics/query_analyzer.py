"""
Query Analyzer for detecting N+1 query problems.

This module provides tools to capture and analyze SQLAlchemy queries
to detect potential N+1 query problems.

Usage:
    from repom.diagnostics.query_analyzer import QueryAnalyzer
    from repom.database import db_session
    from myapp.models import User
    
    analyzer = QueryAnalyzer()
    
    with analyzer.capture():
        users = db_session.query(User).all()
        for user in users:
            print(user.posts)  # May trigger N+1 if not eager loaded
    
    analyzer.print_report()
"""

from contextlib import contextmanager
from typing import Union, Type, List, Optional, Any
from collections import defaultdict
import re

from sqlalchemy import event
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.orm import DeclarativeMeta

from repom.database import get_sync_engine


def get_model_by_name(model_name: str) -> Optional[Type]:
    """
    指定した文字列からモデルクラスを取得するヘルパー関数。

    Args:
        model_name: モデル名（例: 'User', 'Author'）

    Returns:
        モデルクラス、見つからない場合は None

    Example:
        >>> from repom.diagnostics.query_analyzer import get_model_by_name
        >>> User = get_model_by_name('User')
        >>> if User:
        ...     print(f"Found model: {User.__tablename__}")
    """
    from repom.models.base_model import Base

    # Base.registry.mappers から全てのマッパーを取得
    for mapper in Base.registry.mappers:
        model_class = mapper.class_
        # クラス名が一致するか確認
        if model_class.__name__ == model_name:
            return model_class

    return None


def list_all_models() -> List[str]:
    """
    登録されている全てのモデル名を取得するヘルパー関数。

    Returns:
        モデル名のリスト

    Example:
        >>> from repom.diagnostics.query_analyzer import list_all_models
        >>> models = list_all_models()
        >>> print(f"Available models: {', '.join(models)}")
    """
    from repom.models.base_model import Base

    model_names = []
    for mapper in Base.registry.mappers:
        model_class = mapper.class_
        model_names.append(model_class.__name__)

    return sorted(model_names)


class QueryAnalyzer:
    """
    Analyzes SQLAlchemy queries to detect N+1 query problems.

    Attributes:
        queries: List of captured SQL queries
        query_stats: Dictionary of query types and their counts
        target_model: Optional model to filter queries (currently not implemented)
    """

    def __init__(self, engine: Optional[Engine] = None):
        """
        Initialize QueryAnalyzer.

        Args:
            engine: SQLAlchemy engine to monitor. Defaults to repom's default engine.
        """
        self.engine = engine or get_sync_engine()
        self.queries: List[dict] = []
        self.query_stats: dict = defaultdict(int)
        self._listener_registered = False
        self.target_model: Optional[Type] = None

    def _query_listener(self, conn: Connection, cursor: Any, statement: str,
                        parameters: Any, context: Any, executemany: bool) -> None:
        """
        Event listener that captures SQL queries.

        Args:
            conn: Database connection
            cursor: Database cursor
            statement: SQL statement being executed
            parameters: Query parameters
            context: Execution context
            executemany: Whether this is an executemany call
        """
        # Normalize the query (remove extra whitespace)
        normalized = re.sub(r'\s+', ' ', statement.strip())

        # Extract query type (SELECT, INSERT, UPDATE, DELETE)
        match = re.match(r'^(\w+)', normalized)
        query_type = match.group(1).upper() if match else 'UNKNOWN'

        # Store query information
        self.queries.append({
            'statement': normalized,
            'type': query_type,
            'parameters': parameters
        })

        # Update statistics
        self.query_stats[query_type] += 1

    def set_target_model(self, model: Union[str, Type]) -> None:
        """
        特定のモデルをターゲットとして設定（将来的な機能拡張用）。

        Args:
            model: モデル名（文字列）またはモデルクラス

        Example:
            >>> analyzer = QueryAnalyzer()
            >>> analyzer.set_target_model('User')
            >>> # または
            >>> analyzer.set_target_model(User)
        """
        if isinstance(model, str):
            self.target_model = get_model_by_name(model)
            if self.target_model is None:
                available = list_all_models()
                raise ValueError(
                    f"Model '{model}' not found. "
                    f"Available models: {', '.join(available[:10])}"
                    f"{' ...' if len(available) > 10 else ''}"
                )
        else:
            self.target_model = model

    @contextmanager
    def capture(self, model: Optional[Union[str, Type]] = None):
        """
        Context manager to capture queries.

        Args:
            model: Optional model to focus analysis on (string name or class)

        Yields:
            QueryAnalyzer instance

        Example:
            with analyzer.capture():
                users = session.query(User).all()
                for user in users:
                    print(user.posts)

            analyzer.print_report()
        """
        # Reset previous capture
        self.queries = []
        self.query_stats = defaultdict(int)

        # Set target model if provided
        if model is not None:
            self.set_target_model(model)

        # Register event listener
        event.listen(self.engine, "after_cursor_execute", self._query_listener)
        self._listener_registered = True

        try:
            yield self
        finally:
            # Unregister event listener
            if self._listener_registered:
                event.remove(self.engine, "after_cursor_execute", self._query_listener)
                self._listener_registered = False

    def analyze_n_plus_1(self) -> dict:
        """
        Analyze captured queries for N+1 patterns.

        Returns:
            Dictionary with analysis results including:
            - total_queries: Total number of queries executed
            - select_queries: Number of SELECT queries
            - potential_n_plus_1: Whether N+1 pattern detected
            - similar_queries: Groups of similar queries
        """
        total_queries = len(self.queries)
        select_queries = self.query_stats.get('SELECT', 0)

        # Group similar queries (ignoring parameters)
        similar_patterns = defaultdict(list)
        for i, query in enumerate(self.queries):
            if query['type'] == 'SELECT':
                # Create a pattern by removing parameter values
                pattern = re.sub(r'\d+', '?', query['statement'])
                similar_patterns[pattern].append(i)

        # Detect N+1: Multiple similar SELECT queries
        repeated_queries = {
            pattern: indices
            for pattern, indices in similar_patterns.items()
            if len(indices) > 1
        }

        potential_n_plus_1 = len(repeated_queries) > 0 and select_queries > 2

        return {
            'total_queries': total_queries,
            'select_queries': select_queries,
            'potential_n_plus_1': potential_n_plus_1,
            'repeated_queries': repeated_queries,
            'query_stats': dict(self.query_stats)
        }

    def print_report(self, verbose: bool = False) -> None:
        """
        Print analysis report to console.

        Args:
            verbose: If True, print all captured queries
        """
        analysis = self.analyze_n_plus_1()

        print("\n" + "="*70)
        print("Query Analysis Report")
        print("="*70)

        if self.target_model:
            print(f"\nTarget Model: {self.target_model.__name__}")

        print(f"\nTotal Queries: {analysis['total_queries']}")
        print("\nQuery Type Breakdown:")
        for query_type, count in sorted(analysis['query_stats'].items()):
            print(f"  {query_type}: {count}")

        if analysis['potential_n_plus_1']:
            print("\n⚠️  Potential N+1 Problem Detected!")
            print(f"   Found {len(analysis['repeated_queries'])} repeated query patterns")

            print("\nRepeated Query Patterns:")
            for pattern, indices in list(analysis['repeated_queries'].items())[:3]:
                print(f"\n  Pattern (repeated {len(indices)} times):")
                # Show first 100 chars of pattern
                display_pattern = pattern[:100] + "..." if len(pattern) > 100 else pattern
                print(f"    {display_pattern}")
        else:
            print("\n✅ No obvious N+1 problems detected")

        if verbose and self.queries:
            print("\n" + "-"*70)
            print("All Captured Queries:")
            print("-"*70)
            for i, query in enumerate(self.queries, 1):
                print(f"\n{i}. [{query['type']}]")
                print(f"   {query['statement'][:200]}")
                if len(query['statement']) > 200:
                    print("   ...")

        print("\n" + "="*70 + "\n")

    def get_queries(self) -> List[dict]:
        """
        Get all captured queries.

        Returns:
            List of query dictionaries
        """
        return self.queries

    def get_stats(self) -> dict:
        """
        Get query statistics.

        Returns:
            Dictionary of query types and counts
        """
        return dict(self.query_stats)
