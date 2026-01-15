"""
AsyncBaseRepository の options パラメータ（eager loading）のテスト

test_repository_options.py の全テストケースを非同期版に変換したもの。
N+1 問題を解決するための joinedload, selectinload などの
SQLAlchemy の load options をテストします。
"""
from tests._init import *
from sqlalchemy import Integer, String, ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, relationship, joinedload, selectinload
import pytest
import pytest_asyncio
from repom.base_model import BaseModel
from repom.repositories import AsyncBaseRepository


# テスト用モデル定義
class AsyncEagerAuthorModel(BaseModel):
    __tablename__ = 'async_eager_test_authors'

    name: Mapped[str] = mapped_column(String(100))
    books: Mapped[list["AsyncEagerBookModel"]] = relationship(back_populates="author")


class AsyncEagerBookModel(BaseModel):
    __tablename__ = 'async_eager_test_books'

    title: Mapped[str] = mapped_column(String(200))
    author_id: Mapped[int] = mapped_column(ForeignKey('async_eager_test_authors.id'))

    author: Mapped[AsyncEagerAuthorModel] = relationship(back_populates="books")
    reviews: Mapped[list["AsyncEagerReviewModel"]] = relationship(back_populates="book")


class AsyncEagerReviewModel(BaseModel):
    __tablename__ = 'async_eager_test_reviews'

    comment: Mapped[str] = mapped_column(String(500))
    book_id: Mapped[int] = mapped_column(ForeignKey('async_eager_test_books.id'))

    book: Mapped[AsyncEagerBookModel] = relationship(back_populates="reviews")


# Repository 定義
class AsyncAuthorRepository(AsyncBaseRepository[AsyncEagerAuthorModel]):
    def __init__(self, session):
        super().__init__(AsyncEagerAuthorModel, session)


class AsyncBookRepository(AsyncBaseRepository[AsyncEagerBookModel]):
    def __init__(self, session):
        super().__init__(AsyncEagerBookModel, session)


class AsyncReviewRepository(AsyncBaseRepository[AsyncEagerReviewModel]):
    def __init__(self, session):
        super().__init__(AsyncEagerReviewModel, session)


@pytest_asyncio.fixture(scope="function")
async def setup_async_test_data(async_db_test):
    """テストデータのセットアップ（非同期版）"""
    # Author を作成
    author1 = AsyncEagerAuthorModel(name="Author One")
    author2 = AsyncEagerAuthorModel(name="Author Two")
    async_db_test.add_all([author1, author2])
    await async_db_test.flush()

    # Book を作成
    book1 = AsyncEagerBookModel(title="Book 1", author_id=author1.id)
    book2 = AsyncEagerBookModel(title="Book 2", author_id=author1.id)
    book3 = AsyncEagerBookModel(title="Book 3", author_id=author2.id)
    async_db_test.add_all([book1, book2, book3])
    await async_db_test.flush()

    # Review を作成
    review1 = AsyncEagerReviewModel(comment="Great!", book_id=book1.id)
    review2 = AsyncEagerReviewModel(comment="Good!", book_id=book1.id)
    review3 = AsyncEagerReviewModel(comment="Nice!", book_id=book2.id)
    async_db_test.add_all([review1, review2, review3])
    await async_db_test.commit()

    return {
        'authors': [author1, author2],
        'books': [book1, book2, book3],
        'reviews': [review1, review2, review3]
    }


@pytest.mark.asyncio
async def test_find_without_options_works_as_before(async_db_test, setup_async_test_data):
    """
    options を指定しない場合、既存の動作が変わらないことを確認（後方互換性）
    """
    repo = AsyncBookRepository(session=async_db_test)

    # options なし（既存の動作）
    books = await repo.find()

    assert isinstance(books, list)
    assert len(books) == 3
    assert all(isinstance(book, AsyncEagerBookModel) for book in books)


@pytest.mark.asyncio
async def test_find_with_joinedload_single_relationship(async_db_test, setup_async_test_data):
    """
    joinedload を使って関連モデルを eager load できることを確認
    """
    data = setup_async_test_data
    repo = AsyncBookRepository(session=async_db_test)

    # joinedload で author を取得
    books = await repo.find(
        options=[joinedload(AsyncEagerBookModel.author)]
    )

    assert len(books) == 3

    # N+1 なしで author にアクセスできる
    for book in books:
        assert book.author is not None
        assert isinstance(book.author.name, str)
        # author が正しく load されている
        assert book.author.id in [data['authors'][0].id, data['authors'][1].id]


@pytest.mark.asyncio
async def test_find_with_selectinload_collection(async_db_test, setup_async_test_data):
    """
    selectinload を使ってコレクション（1対多）を eager load できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # selectinload で reviews を取得
    books = await repo.find(
        options=[selectinload(AsyncEagerBookModel.reviews)]
    )

    assert len(books) == 3

    # N+1 なしで reviews にアクセスできる
    book1 = next(b for b in books if b.title == "Book 1")
    assert len(book1.reviews) == 2

    book2 = next(b for b in books if b.title == "Book 2")
    assert len(book2.reviews) == 1

    book3 = next(b for b in books if b.title == "Book 3")
    assert len(book3.reviews) == 0


@pytest.mark.asyncio
async def test_find_with_multiple_options(async_db_test, setup_async_test_data):
    """
    複数の options を同時に指定できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # 複数の relationships を eager load
    books = await repo.find(
        options=[
            joinedload(AsyncEagerBookModel.author),
            selectinload(AsyncEagerBookModel.reviews)
        ]
    )

    assert len(books) == 3

    # 両方の関連モデルにアクセスできる
    for book in books:
        assert book.author is not None
        assert isinstance(book.author.name, str)
        assert isinstance(book.reviews, list)


@pytest.mark.asyncio
async def test_find_with_options_and_filters(async_db_test, setup_async_test_data):
    """
    options とフィルタを組み合わせて使用できることを確認
    """
    data = setup_async_test_data
    repo = AsyncBookRepository(session=async_db_test)

    author1_id = data['authors'][0].id

    # フィルタと options を組み合わせ
    books = await repo.find(
        filters=[AsyncEagerBookModel.author_id == author1_id],
        options=[joinedload(AsyncEagerBookModel.author)]
    )

    assert len(books) == 2
    for book in books:
        assert book.author_id == author1_id
        assert book.author.name == "Author One"


@pytest.mark.asyncio
async def test_find_with_options_and_pagination(async_db_test, setup_async_test_data):
    """
    options とページネーション（offset, limit）を組み合わせて使用できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # options + offset + limit
    books = await repo.find(
        options=[joinedload(AsyncEagerBookModel.author)],
        offset=0,
        limit=2,
        order_by='id:asc'
    )

    assert len(books) == 2
    for book in books:
        assert book.author is not None


@pytest.mark.asyncio
async def test_find_with_options_and_order_by(async_db_test, setup_async_test_data):
    """
    options とソート（order_by）を組み合わせて使用できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # options + order_by
    books = await repo.find(
        options=[joinedload(AsyncEagerBookModel.author)],
        order_by='title:desc'
    )

    assert len(books) == 3
    assert books[0].title == "Book 3"
    assert books[1].title == "Book 2"
    assert books[2].title == "Book 1"


@pytest.mark.asyncio
async def test_find_with_single_option_not_list(async_db_test, setup_async_test_data):
    """
    options を list ではなく単一の option として渡せることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # 単一の option（list にしない）
    books = await repo.find(
        options=joinedload(AsyncEagerBookModel.author)
    )

    assert len(books) == 3
    for book in books:
        assert book.author is not None


@pytest.mark.asyncio
async def test_find_with_nested_joinedload(async_db_test, setup_async_test_data):
    """
    ネストした joinedload を使用できることを確認
    """
    repo = AsyncReviewRepository(session=async_db_test)

    # review → book → author とネストして eager load
    reviews = await repo.find(
        options=[
            joinedload(AsyncEagerReviewModel.book).joinedload(AsyncEagerBookModel.author)
        ]
    )

    assert len(reviews) == 3
    for review in reviews:
        assert review.book is not None
        assert review.book.author is not None


@pytest.mark.asyncio
async def test_get_by_with_options(async_db_test, setup_async_test_data):
    """
    get_by メソッドの制限事項を確認

    Note: get_by は内部で find を呼ぶが、**kwargs を渡していないため、
    現状では options を使用できない。
    options を使用する場合は find() メソッドを直接使用する必要がある。
    """
    repo = AsyncBookRepository(session=async_db_test)

    # get_by は options をサポートしていない（設計上の制限）
    # 代わりに find() を使用する
    books = await repo.find(
        filters=[AsyncEagerBookModel.title == "Book 1"],
        options=[joinedload(AsyncEagerBookModel.author)]
    )

    assert isinstance(books, list)
    assert len(books) == 1
    assert books[0].title == "Book 1"
    assert books[0].author is not None


@pytest.mark.asyncio
async def test_options_none_behavior(async_db_test, setup_async_test_data):
    """
    options=None を明示的に渡した場合、通常の動作をすることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # options=None を明示的に指定
    books = await repo.find(options=None)

    assert isinstance(books, list)
    assert len(books) == 3


@pytest.mark.asyncio
async def test_get_by_id_with_options(async_db_test, setup_async_test_data):
    """
    get_by_id() で options を使って eager loading できることを確認
    """
    data = setup_async_test_data
    repo = AsyncBookRepository(session=async_db_test)

    book_id = data['books'][0].id

    # options なし（既存の動作）
    book = await repo.get_by_id(book_id)
    assert book is not None
    assert book.title == "Book 1"

    # options あり（eager loading）
    book = await repo.get_by_id(
        book_id,
        options=[
            joinedload(AsyncEagerBookModel.author),
            selectinload(AsyncEagerBookModel.reviews)
        ]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで関連モデルにアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


@pytest.mark.asyncio
async def test_get_by_with_options_single(async_db_test, setup_async_test_data):
    """
    get_by() で single=True と options を使って eager loading できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # get_by with options
    book = await repo.get_by(
        'title',
        'Book 1',
        single=True,
        options=[joinedload(AsyncEagerBookModel.author)]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで author にアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"


@pytest.mark.asyncio
async def test_get_by_with_options_multiple(async_db_test, setup_async_test_data):
    """
    get_by() で複数レコードを取得する際に options を使えることを確認
    """
    data = setup_async_test_data
    author_id = data['authors'][0].id
    repo = AsyncBookRepository(session=async_db_test)

    # get_by (single=False) with options
    books = await repo.get_by(
        'author_id',
        author_id,
        options=[selectinload(AsyncEagerBookModel.reviews)]
    )

    assert isinstance(books, list)
    assert len(books) == 2
    # N+1 なしで reviews にアクセスできる
    for book in books:
        assert isinstance(book.reviews, list)


@pytest.mark.asyncio
async def test_find_one_with_options(async_db_test, setup_async_test_data):
    """
    find_one() で options を使って eager loading できることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # find_one with options
    book = await repo.find_one(
        filters=[AsyncEagerBookModel.title == "Book 1"],
        options=[
            joinedload(AsyncEagerBookModel.author),
            selectinload(AsyncEagerBookModel.reviews)
        ]
    )

    assert book is not None
    assert book.title == "Book 1"
    # N+1 なしで関連モデルにアクセスできる
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


# =============================================================================
# default_options のテスト（非同期版）
# =============================================================================

@pytest.mark.asyncio
async def test_default_options_in_constructor(async_db_test, setup_async_test_data):
    """
    コンストラクタで default_options を設定し、
    find() で自動的に適用されることを確認
    """
    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            # デフォルトで author を eager load
            self.default_options = [
                joinedload(AsyncEagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # options を指定せずに find を呼ぶ
    books = await repo.find()

    assert len(books) == 3
    # default_options により author がロード済み
    for book in books:
        assert book.author is not None
        assert isinstance(book.author, AsyncEagerAuthorModel)


@pytest.mark.asyncio
async def test_class_level_default_options_are_applied(async_db_test, setup_async_test_data):
    """
    default_options をクラス属性で指定しても適用されることを確認
    """

    class AsyncBookRepositoryWithClassDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        default_options = [
            joinedload(AsyncEagerBookModel.author)
        ]

        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)

    repo = AsyncBookRepositoryWithClassDefaults(session=async_db_test)

    books = await repo.find()

    assert len(books) == 3
    for book in books:
        assert book.author is not None
        assert isinstance(book.author, AsyncEagerAuthorModel)


@pytest.mark.asyncio
async def test_default_options_with_find_one(async_db_test, setup_async_test_data):
    """
    default_options が find_one でも適用されることを確認
    """
    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            self.default_options = [
                joinedload(AsyncEagerBookModel.author),
                selectinload(AsyncEagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # find_one でも default_options が適用される
    book = await repo.find_one(filters=[AsyncEagerBookModel.title == "Book 1"])

    assert book is not None
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


@pytest.mark.asyncio
async def test_default_options_with_get_by_id(async_db_test, setup_async_test_data):
    """
    default_options が get_by_id でも適用されることを確認
    """
    data = setup_async_test_data
    book_id = data['books'][0].id

    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            self.default_options = [
                joinedload(AsyncEagerBookModel.author),
                selectinload(AsyncEagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # get_by_id でも default_options が適用される
    book = await repo.get_by_id(book_id)

    assert book is not None
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2


@pytest.mark.asyncio
async def test_default_options_with_get_by(async_db_test, setup_async_test_data):
    """
    default_options が get_by でも適用されることを確認
    """
    data = setup_async_test_data

    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            self.default_options = [
                joinedload(AsyncEagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # get_by（複数件）
    books = await repo.get_by('author_id', data['authors'][0].id)
    assert len(books) == 2
    for book in books:
        assert book.author is not None

    # get_by（単一件）
    book = await repo.get_by('title', 'Book 1', single=True)
    assert book is not None
    assert book.author is not None


@pytest.mark.asyncio
async def test_explicit_options_override_default_options(async_db_test, setup_async_test_data):
    """
    明示的に options を指定すると default_options が無視されることを確認
    """
    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            # デフォルトでは author のみ
            self.default_options = [
                joinedload(AsyncEagerBookModel.author)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # 明示的に reviews のみ指定（author は無視される）
    books = await repo.find(options=[selectinload(AsyncEagerBookModel.reviews)])

    assert len(books) == 3
    # reviews はロード済み
    for book in books:
        if book.reviews:
            assert isinstance(book.reviews[0], AsyncEagerReviewModel)


@pytest.mark.asyncio
async def test_empty_options_disables_default_options(async_db_test, setup_async_test_data):
    """
    options=[] を明示的に渡すと default_options がスキップされることを確認
    """
    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            self.default_options = [
                joinedload(AsyncEagerBookModel.author),
                selectinload(AsyncEagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    # 空リストを渡すと eager loading なし
    books = await repo.find(options=[])

    assert len(books) == 3
    # 関連モデルはロードされていない（後方互換性確認）
    assert isinstance(books[0], AsyncEagerBookModel)


@pytest.mark.asyncio
async def test_default_options_with_multiple_relationships(async_db_test, setup_async_test_data):
    """
    複数の relationship を default_options で設定できることを確認
    """
    class BookRepositoryWithDefaults(AsyncBaseRepository[AsyncEagerBookModel]):
        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)
            self.default_options = [
                joinedload(AsyncEagerBookModel.author),
                selectinload(AsyncEagerBookModel.reviews)
            ]

    repo = BookRepositoryWithDefaults(session=async_db_test)

    books = await repo.find(filters=[AsyncEagerBookModel.title == "Book 1"])

    assert len(books) == 1
    book = books[0]
    # 両方の関連モデルがロード済み
    assert book.author is not None
    assert book.author.name == "Author One"
    assert len(book.reviews) == 2
    assert all(isinstance(r, AsyncEagerReviewModel) for r in book.reviews)


@pytest.mark.asyncio
async def test_default_options_empty_by_default(async_db_test, setup_async_test_data):
    """
    default_options を設定しない場合は空リストがデフォルトであることを確認
    """
    repo = AsyncBookRepository(session=async_db_test)

    # default_options が存在し、空リストであることを確認
    assert hasattr(repo, 'default_options')
    assert repo.default_options == []

    # 既存の動作は変わらない
    books = await repo.find()
    assert len(books) == 3


# =============================================================================
# default_order_by のテスト
# =============================================================================


@pytest.mark.asyncio
async def test_default_order_by_applied_when_order_by_not_specified(async_db_test, setup_async_test_data):
    """
    default_order_by をクラス属性で指定した場合に order_by 未指定でも適用されることを確認
    """

    class OrderedAsyncBookRepository(AsyncBaseRepository[AsyncEagerBookModel]):
        default_order_by = 'title:desc'

        def __init__(self, session):
            super().__init__(AsyncEagerBookModel, session)

    repo = OrderedAsyncBookRepository(session=async_db_test)

    titles = [book.title for book in await repo.find()]

    assert titles == ["Book 3", "Book 2", "Book 1"]
