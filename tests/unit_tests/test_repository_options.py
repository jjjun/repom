"""
BaseRepository の options パラメータ（eager loading）のテスト

N+1 問題を解決するための joinedload, selectinload などの
SQLAlchemy の load options をテストします。
"""
from tests._init import *
from sqlalchemy import Integer, String, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, joinedload, selectinload
import pytest
from repom.base_model import BaseModel
from repom.base_repository import BaseRepository


# テスト用モデル定義
class EagerAuthorModel(BaseModel):
    __tablename__ = 'eager_test_authors'

    name: Mapped[str] = mapped_column(String(100))
    books: Mapped[list["EagerBookModel"]] = relationship(back_populates="author")


class EagerBookModel(BaseModel):
    __tablename__ = 'eager_test_books'

    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey('eager_test_authors.id'))

    author: Mapped[EagerAuthorModel] = relationship(back_populates="books")
    reviews: Mapped[list["EagerReviewModel"]] = relationship(back_populates="book")


class EagerReviewModel(BaseModel):
    __tablename__ = 'eager_test_reviews'

    comment: Mapped[str] = mapped_column(String(500))
    book_id: Mapped[int] = mapped_column(ForeignKey('eager_test_books.id'))

    book: Mapped[EagerBookModel] = relationship(back_populates="reviews")


# Repository 定義
class AuthorRepository(BaseRepository[EagerAuthorModel]):
    def __init__(self, session):
        super().__init__(EagerAuthorModel, session)


class BookRepository(BaseRepository[EagerBookModel]):
    def __init__(self, session):
        super().__init__(EagerBookModel, session)


class ReviewRepository(BaseRepository[EagerReviewModel]):
    def __init__(self, session):
        super().__init__(EagerReviewModel, session)


@pytest.fixture
def setup_test_data(db_test):
    """テストデータのセットアップ"""
    # Author を作成
    author1 = EagerAuthorModel(name="Author One")
    author2 = EagerAuthorModel(name="Author Two")
    db_test.add_all([author1, author2])
    db_test.flush()

    # Book を作成
    book1 = EagerBookModel(title="Book 1", author_id=author1.id)
    book2 = EagerBookModel(title="Book 2", author_id=author1.id)
    book3 = EagerBookModel(title="Book 3", author_id=author2.id)
    db_test.add_all([book1, book2, book3])
    db_test.flush()

    # Review を作成
    review1 = EagerReviewModel(comment="Great!", book_id=book1.id)
    review2 = EagerReviewModel(comment="Good!", book_id=book1.id)
    review3 = EagerReviewModel(comment="Nice!", book_id=book2.id)
    db_test.add_all([review1, review2, review3])
    db_test.commit()

    return {
        'authors': [author1, author2],
        'books': [book1, book2, book3],
        'reviews': [review1, review2, review3]
    }


def test_find_without_options_works_as_before(db_test, setup_test_data):
    """
    options を指定しない場合、既存の動作が変わらないことを確認（後方互換性）
    """
    repo = BookRepository(session=db_test)

    # options なし（既存の動作）
    books = repo.find()

    assert isinstance(books, list)
    assert len(books) == 3
    assert all(isinstance(book, EagerBookModel) for book in books)


def test_find_with_joinedload_single_relationship(db_test, setup_test_data):
    """
    joinedload を使って関連モデルを eager load できることを確認
    """
    repo = BookRepository(session=db_test)

    # joinedload で author を取得
    books = repo.find(
        options=[joinedload(EagerBookModel.author)]
    )

    assert len(books) == 3

    # N+1 なしで author にアクセスできる
    for book in books:
        assert book.author is not None
        assert isinstance(book.author.name, str)
        # author が正しく load されている
        assert book.author.id in [setup_test_data['authors'][0].id, setup_test_data['authors'][1].id]


def test_find_with_selectinload_collection(db_test, setup_test_data):
    """
    selectinload を使ってコレクション（1対多）を eager load できることを確認
    """
    repo = BookRepository(session=db_test)

    # selectinload で reviews を取得
    books = repo.find(
        options=[selectinload(EagerBookModel.reviews)]
    )

    assert len(books) == 3

    # N+1 なしで reviews にアクセスできる
    book1 = next(b for b in books if b.title == "Book 1")
    assert len(book1.reviews) == 2

    book2 = next(b for b in books if b.title == "Book 2")
    assert len(book2.reviews) == 1

    book3 = next(b for b in books if b.title == "Book 3")
    assert len(book3.reviews) == 0


def test_find_with_multiple_options(db_test, setup_test_data):
    """
    複数の options を同時に指定できることを確認
    """
    repo = BookRepository(session=db_test)

    # 複数の relationships を eager load
    books = repo.find(
        options=[
            joinedload(EagerBookModel.author),
            selectinload(EagerBookModel.reviews)
        ]
    )

    assert len(books) == 3

    # 両方の関連モデルにアクセスできる
    for book in books:
        assert book.author is not None
        assert isinstance(book.author.name, str)
        assert isinstance(book.reviews, list)


def test_find_with_options_and_filters(db_test, setup_test_data):
    """
    options とフィルタを組み合わせて使用できることを確認
    """
    repo = BookRepository(session=db_test)

    author1_id = setup_test_data['authors'][0].id

    # フィルタと options を組み合わせ
    books = repo.find(
        filters=[EagerBookModel.author_id == author1_id],
        options=[joinedload(EagerBookModel.author)]
    )

    assert len(books) == 2
    for book in books:
        assert book.author_id == author1_id
        assert book.author.name == "Author One"


def test_find_with_options_and_pagination(db_test, setup_test_data):
    """
    options とページネーション（offset, limit）を組み合わせて使用できることを確認
    """
    repo = BookRepository(session=db_test)

    # options + offset + limit
    books = repo.find(
        options=[joinedload(EagerBookModel.author)],
        offset=0,
        limit=2,
        order_by='id:asc'
    )

    assert len(books) == 2
    for book in books:
        assert book.author is not None


def test_find_with_options_and_order_by(db_test, setup_test_data):
    """
    options とソート（order_by）を組み合わせて使用できることを確認
    """
    repo = BookRepository(session=db_test)

    # options + order_by
    books = repo.find(
        options=[joinedload(EagerBookModel.author)],
        order_by='title:desc'
    )

    assert len(books) == 3
    assert books[0].title == "Book 3"
    assert books[1].title == "Book 2"
    assert books[2].title == "Book 1"


def test_find_with_single_option_not_list(db_test, setup_test_data):
    """
    options を list ではなく単一の option として渡せることを確認
    """
    repo = BookRepository(session=db_test)

    # 単一の option（list にしない）
    books = repo.find(
        options=joinedload(EagerBookModel.author)
    )

    assert len(books) == 3
    for book in books:
        assert book.author is not None


def test_find_with_nested_joinedload(db_test, setup_test_data):
    """
    ネストした joinedload を使用できることを確認
    """
    repo = ReviewRepository(session=db_test)

    # review → book → author とネストして eager load
    reviews = repo.find(
        options=[
            joinedload(EagerReviewModel.book).joinedload(EagerBookModel.author)
        ]
    )

    assert len(reviews) == 3
    for review in reviews:
        assert review.book is not None
        assert review.book.author is not None


def test_get_by_with_options(db_test, setup_test_data):
    """
    get_by メソッドの制限事項を確認

    Note: get_by は内部で find を呼ぶが、**kwargs を渡していないため、
    現状では options を使用できない。
    options を使用する場合は find() メソッドを直接使用する必要がある。
    """
    repo = BookRepository(session=db_test)

    # get_by は options をサポートしていない（設計上の制限）
    # 代わりに find() を使用する
    books = repo.find(
        filters=[EagerBookModel.title == "Book 1"],
        options=[joinedload(EagerBookModel.author)]
    )

    assert isinstance(books, list)
    assert len(books) == 1
    assert books[0].title == "Book 1"
    assert books[0].author is not None


def test_options_none_behavior(db_test, setup_test_data):
    """
    options=None を明示的に渡した場合、通常の動作をすることを確認
    """
    repo = BookRepository(session=db_test)

    # options=None を明示的に指定
    books = repo.find(options=None)

    assert isinstance(books, list)
    assert len(books) == 3
