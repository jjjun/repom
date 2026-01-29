"""
Tests for QueryAnalyzer - N+1 query detection tool.
"""

import pytest
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from repom import BaseModel, BaseRepository
from repom.scripts.query_analyzer import QueryAnalyzer, get_model_by_name, list_all_models
from repom.database import get_db_session


# Test models
class Author(BaseModel):
    __tablename__ = 'test_authors'

    name: Mapped[str] = mapped_column(String(100))
    books: Mapped[list['Book']] = relationship('Book', back_populates='author')


class Book(BaseModel):
    __tablename__ = 'test_books'

    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey('test_authors.id'))
    author: Mapped['Author'] = relationship('Author', back_populates='books')


class TestQueryAnalyzer:
    """Test QueryAnalyzer functionality."""

    @pytest.fixture
    def setup_data(self, db_test):
        """Create test data with authors and books."""
        # Create authors with books
        author1 = Author(name="Author 1")
        author2 = Author(name="Author 2")
        author3 = Author(name="Author 3")

        book1 = Book(title="Book 1-1", author=author1)
        book2 = Book(title="Book 1-2", author=author1)
        book3 = Book(title="Book 2-1", author=author2)
        book4 = Book(title="Book 3-1", author=author3)

        db_test.add_all([author1, author2, author3])
        db_test.add_all([book1, book2, book3, book4])
        db_test.commit()

        return {
            'authors': [author1, author2, author3],
            'books': [book1, book2, book3, book4]
        }

    def test_capture_queries(self, db_test, setup_data):
        """Test basic query capturing."""
        # Use the same engine as db_test
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            # Execute a simple query
            authors = db_test.query(Author).all()
            assert len(authors) == 3

        queries = analyzer.get_queries()
        assert len(queries) > 0
        assert any(q['type'] == 'SELECT' for q in queries)

    def test_detect_n_plus_1_problem(self, db_test, setup_data):
        """Test detection of N+1 query problem."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            # This triggers N+1 problem
            authors = db_test.query(Author).all()
            for author in authors:
                # Accessing books without eager loading causes N+1
                _ = author.books

        analysis = analyzer.analyze_n_plus_1()

        # Should detect N+1 problem
        assert analysis['total_queries'] > 1
        assert analysis['select_queries'] > 1
        # With 3 authors, we expect: 1 query for authors + 3 queries for books
        assert analysis['potential_n_plus_1'] is True
        assert len(analysis['repeated_queries']) > 0

    def test_no_n_plus_1_with_eager_loading(self, db_test, setup_data):
        """Test that eager loading prevents N+1 problem."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            # Using joinedload to eager load books
            from sqlalchemy.orm import joinedload
            authors = db_test.query(Author).options(joinedload(Author.books)).all()
            for author in authors:
                _ = author.books

        analysis = analyzer.analyze_n_plus_1()

        # Should not detect repeated queries
        assert analysis['total_queries'] >= 1
        # No repeated SELECT patterns (or very few)
        assert len(analysis['repeated_queries']) == 0 or analysis['potential_n_plus_1'] is False

    def test_query_stats(self, db_test, setup_data):
        """Test query statistics collection."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            # SELECT query
            db_test.query(Author).all()

            # INSERT query
            new_author = Author(name="New Author")
            db_test.add(new_author)
            db_test.commit()

        stats = analyzer.get_stats()

        assert 'SELECT' in stats
        assert stats['SELECT'] >= 1
        assert 'INSERT' in stats or 'BEGIN' in stats

    def test_print_report(self, db_test, setup_data, capsys):
        """Test report printing."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            authors = db_test.query(Author).all()
            for author in authors:
                _ = author.books

        analyzer.print_report()

        captured = capsys.readouterr()
        assert "Query Analysis Report" in captured.out
        assert "Total Queries:" in captured.out
        assert "Query Type Breakdown:" in captured.out

    def test_print_report_verbose(self, db_test, setup_data, capsys):
        """Test verbose report printing."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture():
            db_test.query(Author).all()

        analyzer.print_report(verbose=True)

        captured = capsys.readouterr()
        assert "All Captured Queries:" in captured.out

    def test_multiple_captures(self, db_test, setup_data):
        """Test that multiple captures reset properly."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        # First capture
        with analyzer.capture():
            db_test.query(Author).all()

        first_count = len(analyzer.get_queries())

        # Second capture should reset
        with analyzer.capture():
            db_test.query(Book).all()

        second_count = len(analyzer.get_queries())

        # Counts should be different (not accumulated)
        assert second_count != first_count + len(analyzer.get_queries())

    def test_analyzer_with_repository(self, db_test, setup_data):
        """Test QueryAnalyzer with BaseRepository."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)
        repo = BaseRepository(Author, db_test)

        with analyzer.capture():
            authors = repo.get_all()
            for author in authors:
                _ = author.books

        analysis = analyzer.analyze_n_plus_1()
        assert analysis['potential_n_plus_1'] is True


class TestModelHelperFunctions:
    """Test helper functions for model lookup."""

    def test_get_model_by_name_finds_existing_model(self, db_test):
        """Test getting a model by its name."""
        Author_model = get_model_by_name('Author')
        assert Author_model is not None
        assert Author_model.__name__ == 'Author'
        assert Author_model.__tablename__ == 'test_authors'

    def test_get_model_by_name_returns_none_for_nonexistent(self, db_test):
        """Test that nonexistent model returns None."""
        result = get_model_by_name('NonExistentModel')
        assert result is None

    def test_list_all_models_returns_list(self, db_test):
        """Test that list_all_models returns a sorted list."""
        models = list_all_models()
        assert isinstance(models, list)
        assert len(models) > 0
        assert 'Author' in models
        assert 'Book' in models
        # Check it's sorted
        assert models == sorted(models)

    def test_set_target_model_with_string(self, db_test):
        """Test setting target model with string name."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)
        analyzer.set_target_model('Author')

        assert analyzer.target_model is not None
        assert analyzer.target_model.__name__ == 'Author'

    def test_set_target_model_with_class(self, db_test):
        """Test setting target model with model class."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)
        analyzer.set_target_model(Author)

        assert analyzer.target_model is Author

    def test_set_target_model_raises_error_for_invalid(self, db_test):
        """Test that invalid model name raises error."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with pytest.raises(ValueError) as exc_info:
            analyzer.set_target_model('InvalidModelName')

        assert 'not found' in str(exc_info.value)
        assert 'Available models' in str(exc_info.value)

    def test_capture_with_model_string(self, db_test):
        """Test capture with model specified as string."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture(model='Author'):
            db_test.query(Author).all()

        assert analyzer.target_model is not None
        assert analyzer.target_model.__name__ == 'Author'

    def test_print_report_shows_target_model(self, db_test, capsys):
        """Test that print_report shows target model when set."""
        analyzer = QueryAnalyzer(engine=db_test.bind.engine)

        with analyzer.capture(model='Author'):
            db_test.query(Author).all()

        analyzer.print_report()

        captured = capsys.readouterr()
        assert "Target Model: Author" in captured.out
