"""
Test: Repository __init__ without model argument (auto inference)

Issue: https://github.com/repom/repom/issues/XXX

When a repository class inherits from BaseRepository[Model] and omits __init__,
calling `repo_class(session)` passes `session` to the `model` parameter,
causing ArgumentError in SQLAlchemy queries.

Expected behavior:
- repo_class(session) should work without defining __init__
- BaseRepository should infer the model from type parameters
"""

import pytest
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from repom import BaseRepository
from repom.models import BaseModel


class AutoInferenceModel(BaseModel):
    """Test model for auto inference"""
    __tablename__ = 'test_auto_inference'

    name: Mapped[str] = mapped_column(String(100))


class RepositoryWithInit(BaseRepository[AutoInferenceModel]):
    """Repository with explicit __init__ - should work"""

    def __init__(self, session=None):
        super().__init__(AutoInferenceModel, session)


class RepositoryWithoutInit(BaseRepository[AutoInferenceModel]):
    """Repository without __init__ - now works with auto inference"""
    pass


def test_repository_with_explicit_init(db_test):
    """✅ リポジトリが明示的な __init__ を持つ場合（従来の方法）"""
    repo = RepositoryWithInit(session=db_test)

    # モデルが正しく設定されている
    assert repo.model == AutoInferenceModel

    # find() が動作する
    results = repo.find()
    assert isinstance(results, list)


def test_repository_without_init_with_keyword_arg(db_test):
    """✅ __init__ 省略 + session=... のキーワード引数で呼び出し"""
    repo = RepositoryWithoutInit(session=db_test)

    # モデルが型パラメータから自動推論される
    assert repo.model == AutoInferenceModel

    # find() が正常に動作する
    results = repo.find()
    assert isinstance(results, list)


def test_repository_without_init_with_positional_arg_error(db_test):
    """❌ __init__ 省略 + 位置引数で呼び出すとエラーメッセージが明確"""
    with pytest.raises(TypeError) as exc_info:
        # 位置引数で渡すと Session が model に入る
        RepositoryWithoutInit(db_test)

    # エラーメッセージが明確
    error_msg = str(exc_info.value)
    assert "Session object was passed as 'model' parameter" in error_msg
    assert "session" in error_msg.lower()


def test_repository_backward_compatibility_explicit_model(db_test):
    """🔄 既存の明示的な model 指定パターンも動作し続けること"""
    # 既存コード：model を明示的に指定
    repo = BaseRepository(AutoInferenceModel, session=db_test)

    assert repo.model == AutoInferenceModel
    results = repo.find()
    assert isinstance(results, list)


def test_repository_auto_inference_without_type_param_error():
    """❌ 型パラメータなしでモデル推論不可時のエラーメッセージ"""

    class NoTypeParamRepository(BaseRepository):
        """型パラメータを指定していないリポジトリ"""
        pass

    with pytest.raises(TypeError) as exc_info:
        NoTypeParamRepository()

    error_msg = str(exc_info.value)
    assert "Could not infer model type" in error_msg
    assert "NoTypeParamRepository" in error_msg
