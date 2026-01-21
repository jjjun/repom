"""
update_from_dict() が余計なキー（モデルに存在しないキー）と読み取り専用プロパティを正しく処理することを確認
"""
import pytest
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from repom.models.base_model import BaseModel


class SimpleTestModel(BaseModel):
    """テスト用の単純なモデル"""
    __tablename__ = 'simple_test_model_extra_keys'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(nullable=True)


class ModelWithProperties(BaseModel):
    """読み取り専用プロパティを持つモデル"""
    __tablename__ = 'model_with_properties'

    first_name: Mapped[str] = mapped_column(String(50), nullable=False)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False)
    age: Mapped[int] = mapped_column(nullable=False, default=0)

    @property
    def full_name(self):
        """読み取り専用プロパティ（setter なし）"""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_adult(self):
        """読み取り専用プロパティ（setter なし）"""
        return self.age >= 18


class ParentModel(BaseModel):
    """リレーション用の親モデル"""
    __tablename__ = 'parent_model_for_relation_test'

    title: Mapped[str] = mapped_column(String(100), nullable=False)


class ChildModel(BaseModel):
    """リレーションとプロパティを持つ子モデル"""
    __tablename__ = 'child_model_for_relation_test'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, ForeignKey("parent_model_for_relation_test.id"), nullable=False)
    parent: Mapped["ParentModel"] = relationship("ParentModel")

    @property
    def parent_title(self):
        """親モデルのプロパティを返す読み取り専用プロパティ"""
        return self.parent.title if self.parent else None


class ModelWithTimestamps(BaseModel):
    """システムカラムを持つテスト用モデル"""
    __tablename__ = 'model_with_timestamps_extra_keys'
    use_created_at = True
    use_updated_at = True

    name: Mapped[str] = mapped_column(String(100), nullable=False)


def test_update_from_dict_ignores_extra_keys(db_test):
    """モデルに存在しないキーが辞書にあっても無視されることを確認"""
    # テストデータを作成
    model = SimpleTestModel(name='Alice', age=30)
    db_test.add(model)
    db_test.commit()

    # モデルに存在しないキーを含む辞書で更新
    update_data = {
        'name': 'Bob',           # 存在するフィールド
        'age': 35,              # 存在するフィールド
        'email': 'bob@example.com',  # 存在しないフィールド
        'address': '123 Street',     # 存在しないフィールド
        'phone': '555-1234'          # 存在しないフィールド
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # 存在するフィールドは更新されている
    assert model.name == 'Bob'
    assert model.age == 35

    # 存在しないフィールドは追加されていない（エラーも発生しない）
    assert not hasattr(model, 'email')
    assert not hasattr(model, 'address')
    assert not hasattr(model, 'phone')

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_only_extra_keys(db_test):
    """辞書に存在するフィールドのキーが一つもない場合"""
    model = SimpleTestModel(name='Charlie', age=40)
    db_test.add(model)
    db_test.commit()

    # モデルに存在しないキーのみの辞書
    update_data = {
        'email': 'charlie@example.com',
        'city': 'Tokyo',
        'country': 'Japan'
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # 何も変更されていない
    assert model.name == 'Charlie'
    assert model.age == 40

    # 存在しないフィールドは追加されていない
    assert not hasattr(model, 'email')
    assert not hasattr(model, 'city')
    assert not hasattr(model, 'country')

    # 変更がないことが返り値で示される
    assert result is False


def test_update_from_dict_mixed_valid_and_invalid_keys(db_test):
    """有効なキーと無効なキーが混在している場合"""
    model = SimpleTestModel(name='David', age=25)
    db_test.add(model)
    db_test.commit()

    original_name = model.name
    original_age = model.age

    # 一部のキーのみ有効
    update_data = {
        'name': 'David Updated',  # 有効（更新される）
        'invalid_field_1': 'value1',  # 無効（無視される）
        'invalid_field_2': 123,       # 無効（無視される）
        # age は更新しない
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # name は更新されている
    assert model.name == 'David Updated'
    # age は変更されていない
    assert model.age == original_age

    # 無効なフィールドは追加されていない
    assert not hasattr(model, 'invalid_field_1')
    assert not hasattr(model, 'invalid_field_2')

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_with_system_and_extra_keys(db_test):
    """システムカラム（id, created_at, updated_at）と余計なキーが混在している場合"""
    model = ModelWithTimestamps(name='Eve')
    db_test.add(model)
    db_test.commit()

    original_id = model.id
    original_created_at = model.created_at

    # システムカラム、有効なキー、無効なキーが混在
    update_data = {
        'id': 999,                   # システムカラム（無視される）
        'created_at': '2020-01-01',  # システムカラム（無視される）
        'name': 'Eve Updated',       # 有効（更新される）
        'extra_field': 'extra_value'  # 無効（無視される）
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # システムカラムは保護されている
    assert model.id == original_id
    assert model.created_at == original_created_at

    # name は更新されている
    assert model.name == 'Eve Updated'

    # 余計なフィールドは追加されていない
    assert not hasattr(model, 'extra_field')

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_empty_dict(db_test):
    """空の辞書を渡した場合"""
    model = SimpleTestModel(name='Frank', age=50)
    db_test.add(model)
    db_test.commit()

    result = model.update_from_dict({})

    # 何も変更されていない
    assert model.name == 'Frank'
    assert model.age == 50

    # 変更がないことが返り値で示される
    assert result is False


def test_update_from_dict_exclude_fields_with_extra_keys(db_test):
    """exclude_fields と余計なキーが混在している場合"""
    model = SimpleTestModel(name='Grace', age=28)
    db_test.add(model)
    db_test.commit()

    # exclude_fields で name を除外
    update_data = {
        'name': 'Grace Updated',     # exclude_fields で除外（更新されない）
        'age': 29,                  # 更新される
        'invalid_key': 'value'      # 無効（無視される）
    }

    result = model.update_from_dict(update_data, exclude_fields=['name'])
    db_test.commit()

    # name は除外されているので更新されない
    assert model.name == 'Grace'
    # age は更新される
    assert model.age == 29

    # 無効なフィールドは追加されていない
    assert not hasattr(model, 'invalid_key')

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_ignores_readonly_properties(db_test):
    """読み取り専用プロパティ（@property）は無視されることを確認"""
    model = ModelWithProperties(first_name='John', last_name='Doe', age=25)
    db_test.add(model)
    db_test.commit()

    # 読み取り専用プロパティを含む辞書で更新を試みる
    update_data = {
        'first_name': 'Jane',           # DBカラム（更新される）
        'age': 30,                      # DBカラム（更新される）
        'full_name': 'Should Be Ignored',  # @property（無視される）
        'is_adult': False,              # @property（無視される）
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # DBカラムは更新されている
    assert model.first_name == 'Jane'
    assert model.age == 30
    assert model.last_name == 'Doe'  # 更新されていない

    # 読み取り専用プロパティは計算結果を返す（setter がないので変更されない）
    assert model.full_name == 'Jane Doe'
    assert model.is_adult is True  # age=30 なので True

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_with_relation_property(db_test):
    """リレーション経由の読み取り専用プロパティが無視されることを確認"""
    parent = ParentModel(title='Parent Title')
    db_test.add(parent)
    db_test.commit()

    child = ChildModel(name='Child Name', parent_id=parent.id, parent=parent)
    db_test.add(child)
    db_test.commit()

    # リレーション経由のプロパティを含む辞書で更新
    update_data = {
        'name': 'Updated Child',         # DBカラム（更新される）
        'parent_title': 'Should Ignore',  # @property（無視される）
        'extra_field': 'value'           # 存在しないキー（無視される）
    }

    result = child.update_from_dict(update_data)
    db_test.commit()

    # name は更新されている
    assert child.name == 'Updated Child'

    # parent_title は読み取り専用プロパティ（親から取得される）
    assert child.parent_title == 'Parent Title'

    # parent_id は変更されていない
    assert child.parent_id == parent.id

    # 変更があったことが返り値で示される
    assert result is True


def test_update_from_dict_mixed_columns_and_properties(db_test):
    """DBカラム、読み取り専用プロパティ、存在しないキーが混在している場合"""
    model = ModelWithProperties(first_name='Alice', last_name='Smith', age=20)
    db_test.add(model)
    db_test.commit()

    # 様々なキーが混在
    update_data = {
        'first_name': 'Alicia',          # DBカラム（更新される）
        'last_name': 'Johnson',          # DBカラム（更新される）
        'age': 22,                       # DBカラム（更新される）
        'full_name': 'Ignored',          # @property（無視される）
        'is_adult': 'Ignored',           # @property（無視される）
        'nonexistent_field': 'value',    # 存在しないキー（無視される）
    }

    result = model.update_from_dict(update_data)
    db_test.commit()

    # DBカラムは全て更新されている
    assert model.first_name == 'Alicia'
    assert model.last_name == 'Johnson'
    assert model.age == 22

    # 読み取り専用プロパティは計算結果を返す
    assert model.full_name == 'Alicia Johnson'
    assert model.is_adult is True

    # 存在しないフィールドは追加されていない
    assert not hasattr(model, 'nonexistent_field')

    # 変更があったことが返り値で示される
    assert result is True
