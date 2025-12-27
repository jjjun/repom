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


def test_get_by_id_with_options(db_test, setup_test_data):
    """
    get_by_id() で options を使って eager loading できることを確認
    """
    data = setup_test_data
    repo = BookRepository(session=db_test)

    book_id = data['books'][0].id

    # options なし（既存の動作）
    book = repo.get_by_id(book_id)
    assert book is not None
    assert book.title == "Book 1"

    # options あり（eager loading）
    book = repo.get_by_id(
        book_id,
        options=[
            joinedload(EagerBookModel.author),
            selectinload(EagerBookModel.reviews)
        ]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで関連モデルにアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


def test_get_by_with_options_single(db_test, setup_test_data):
    """
    get_by() で single=True と options を使って eager loading できることを確認
    """
    repo = BookRepository(session=db_test)

    # get_by with options
    book = repo.get_by(
        'title',
        'Book 1',
        single=True,
        options=[joinedload(EagerBookModel.author)]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで author にアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"


def test_get_by_with_options_multiple(db_test, setup_test_data):
    """
    get_by() で複数レコードを取得する際に options を使えることを確認
    """
    data = setup_test_data
    author_id = data['authors'][0].id
    repo = BookRepository(session=db_test)

    # get_by (single=False) with options
    books = repo.get_by(
        'author_id',
        author_id,
        options=[selectinload(EagerBookModel.reviews)]
    )

    assert isinstance(books, list)
    assert len(books) == 2
    # N+1 なしで reviews にアクセスできる
    for book in books:
        assert isinstance(book.reviews, list)


def test_find_one_with_options(db_test, setup_test_data):
    """
    find_one() で options を使って eager loading できることを確認
    """
    repo = BookRepository(session=db_test)

    # find_one with options
    book = repo.find_one(
        filters=[EagerBookModel.title == "Book 1"],
        options=[
            joinedload(EagerBookModel.author),
            selectinload(EagerBookModel.reviews)
        ]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで関連モデルにアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


# =============================================================================
# default_options のテスト
# =============================================================================

def test_default_options_in_constructor(db_test, setup_test_data):
    """
    コンストラクタで default_options を設定し、
    find() で自動的に適用されることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            # デフォルトで author を eager load
            self.default_options = [
                joinedload(EagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # options を指定せずに find を呼ぶ
    books = repo.find()

    assert len(books) == 3
    # default_options により author がロード済み
    for book in books:
        assert book.author is not None
        assert isinstance(book.author, EagerAuthorModel)


def test_default_options_with_find_one(db_test, setup_test_data):
    """
    default_options が find_one でも適用されることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            self.default_options = [
                joinedload(EagerBookModel.author),
                selectinload(EagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # find_one でも default_options が適用される
    book = repo.find_one(filters=[EagerBookModel.title == "Book 1"])

    assert book is not None
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


def test_default_options_with_get_by_id(db_test, setup_test_data):
    """
    default_options が get_by_id でも適用されることを確認
    """
    data = setup_test_data
    book_id = data['books'][0].id

    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            self.default_options = [
                joinedload(EagerBookModel.author),
                selectinload(EagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # get_by_id でも default_options が適用される
    book = repo.get_by_id(book_id)

    assert book is not None
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


def test_default_options_with_get_by(db_test, setup_test_data):
    """
    default_options が get_by でも適用されることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            self.default_options = [
                joinedload(EagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # get_by（複数件）
    books = repo.get_by('author_id', setup_test_data['authors'][0].id)
    assert len(books) == 2
    for book in books:
        assert book.author is not None

    # get_by（単一件）
    book = repo.get_by('title', 'Book 1', single=True)
    assert book is not None
    assert book.author is not None


def test_explicit_options_override_default_options(db_test, setup_test_data):
    """
    明示的に options を指定すると default_options が無視されることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            # デフォルトでは author のみ
            self.default_options = [
                joinedload(EagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # 明示的に reviews のみ指定（author は無視される）
    books = repo.find(options=[selectinload(EagerBookModel.reviews)])

    assert len(books) == 3
    # reviews はロード済み
    for book in books:
        if book.reviews:
            assert isinstance(book.reviews[0], EagerReviewModel)


def test_empty_options_disables_default_options(db_test, setup_test_data):
    """
    options=[] を明示的に渡すと default_options がスキップされることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            self.default_options = [
                joinedload(EagerBookModel.author),
                selectinload(EagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    # 空リストを渡すと eager loading なし
    books = repo.find(options=[])

    assert len(books) == 3
    # 関連モデルはロードされていない（後方互換性確認）
    assert isinstance(books[0], EagerBookModel)


def test_default_options_with_multiple_relationships(db_test, setup_test_data):
    """
    複数の relationship を default_options で設定できることを確認
    """
    class BookRepositoryWithDefaults(BaseRepository[EagerBookModel]):
        def __init__(self, session):
            super().__init__(EagerBookModel, session)
            self.default_options = [
                joinedload(EagerBookModel.author),
                selectinload(EagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=db_test)

    books = repo.find(filters=[EagerBookModel.title == "Book 1"])

    assert len(books) == 1
    book = books[0]
    # 両方の関連モデルがロード済み
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2
    assert all(isinstance(r, EagerReviewModel) for r in book.reviews)


def test_default_options_empty_by_default(db_test, setup_test_data):
    """
    default_options を設定しない場合は空リストがデフォルトであることを確認
    """
    repo = BookRepository(session=db_test)

    # default_options が存在し、空リストであることを確認
    assert hasattr(repo, 'default_options')
    assert repo.default_options == []

    # 既存の動作は変わらない
    books = repo.find()
    assert len(books) == 3
