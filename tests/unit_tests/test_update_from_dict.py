"""
update_from_dict() が余計なキー（モデルに存在しないキー）と読み取り専用プロパティを正しく処理することを確認
"""
import pytest
from datetime import datetime
from time import sleep
from sqlalchemy import String, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from repom.models.base_model import BaseModel
from repom.mixins import SoftDeletableMixin


class SimpleTestModel(BaseModel):
    """テスト用の単純なモデル"""
    __tablename__ = 'simple_test_model_extra_keys'
    updatable_fields = {'name', 'age'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[int] = mapped_column(nullable=True)


class ModelWithProperties(BaseModel):
    """読み取り専用プロパティを持つモデル"""
    __tablename__ = 'model_with_properties'
    updatable_fields = {'first_name', 'last_name', 'age', 'full_name', 'is_adult'}

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
    updatable_fields = {'name', 'parent_title'}

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
    updatable_fields = {'id', 'created_at', 'name'}

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


class AllowlistedModel(BaseModel):
    __tablename__ = 'allowlisted_model_mass_assignment'
    updatable_fields = {'name'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)


class NoAllowlistModel(BaseModel):
    __tablename__ = 'no_allowlist_model_mass_assignment'

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class CustomPrimaryKeyModel(BaseModel, use_id=False):
    __tablename__ = 'custom_pk_model_mass_assignment'
    updatable_fields = {'uuid', 'name'}

    uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SoftDeletableAllowlistModel(BaseModel, SoftDeletableMixin):
    __tablename__ = 'soft_deletable_allowlist_model_mass_assignment'
    updatable_fields = {'name', 'deleted_at'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class SystemProtectionModel(BaseModel):
    __tablename__ = 'system_protection_model'
    use_created_at = True
    use_updated_at = True
    updatable_fields = {'id', 'created_at', 'updated_at', 'name'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


class UuidUpdateModel(BaseModel, use_uuid=True):
    __tablename__ = 'uuid_update_model'
    updatable_fields = {'id', 'name'}

    name: Mapped[str] = mapped_column(String(100), nullable=False)


def test_update_from_dict_rejects_unlisted_field(db_test):
    model = AllowlistedModel(name='original', is_admin=False)
    db_test.add(model)
    db_test.commit()

    result = model.update_from_dict({'is_admin': True})
    db_test.commit()

    assert model.is_admin is False
    assert result is False


def test_update_from_dict_uses_class_updatable_fields():
    model = AllowlistedModel(name='original', is_admin=False)
    model.updatable_fields = {'name', 'is_admin'}

    result = model.update_from_dict({'is_admin': True})

    assert model.is_admin is False
    assert result is False


def test_model_constructor_rejects_updatable_fields():
    with pytest.raises(TypeError, match='class-level model controls'):
        AllowlistedModel(name='original', updatable_fields={'name', 'is_admin'})


def test_model_constructor_rejects_unmapped_callable_attributes():
    with pytest.raises(TypeError, match='only accepts mapped model attributes'):
        AllowlistedModel(name='original', to_dict=lambda: {})


def test_update_from_dict_requires_explicit_allowlist(db_test):
    model = NoAllowlistModel(name='original')
    db_test.add(model)
    db_test.commit()

    with pytest.raises(ValueError):
        model.update_from_dict({'name': 'updated'})


def test_update_from_dict_excludes_all_primary_keys(db_test):
    model = CustomPrimaryKeyModel(
        uuid='11111111-1111-1111-1111-111111111111',
        name='original',
    )
    db_test.add(model)
    db_test.commit()

    model.update_from_dict({
        'uuid': '22222222-2222-2222-2222-222222222222',
        'name': 'updated',
    })
    db_test.commit()

    assert model.uuid == '11111111-1111-1111-1111-111111111111'
    assert model.name == 'updated'


def test_update_from_dict_excludes_deleted_at(db_test):
    model = SoftDeletableAllowlistModel(name='original')
    db_test.add(model)
    db_test.commit()

    model.update_from_dict({
        'deleted_at': '2020-01-01T00:00:00+00:00',
        'name': 'updated',
    })
    db_test.commit()

    assert model.deleted_at is None
    assert model.name == 'updated'


def test_update_from_dict_excludes_id(db_test):
    model = SystemProtectionModel(name='original')
    db_test.add(model)
    db_test.commit()
    original_id = model.id

    model.update_from_dict({'id': 999, 'name': 'updated'})
    db_test.commit()

    assert model.id == original_id
    assert model.name == 'updated'


def test_update_from_dict_excludes_created_at(db_test):
    model = SystemProtectionModel(name='original')
    db_test.add(model)
    db_test.commit()
    original_created_at = model.created_at

    model.update_from_dict({
        'created_at': datetime(2020, 1, 1),
        'name': 'updated',
    })
    db_test.commit()

    assert model.created_at == original_created_at
    assert model.name == 'updated'


def test_update_from_dict_excludes_updated_at(db_test):
    model = SystemProtectionModel(name='original')
    db_test.add(model)
    db_test.commit()

    model.update_from_dict({
        'updated_at': datetime(2020, 1, 1),
        'name': 'updated',
    })
    db_test.commit()

    assert model.updated_at != datetime(2020, 1, 1)
    assert model.name == 'updated'


def test_update_from_dict_protects_uuid_id(db_test):
    model = UuidUpdateModel(name='Original')
    db_test.add(model)
    db_test.commit()
    original_id = model.id

    model.update_from_dict({'id': '00000000-0000-0000-0000-000000000000', 'name': 'Updated'})
    db_test.commit()

    assert model.id == original_id
    assert model.name == 'Updated'


def test_update_from_dict_protects_system_columns_together(db_test):
    model = SystemProtectionModel(name='original')
    db_test.add(model)
    db_test.commit()
    original_id = model.id
    original_created_at = model.created_at
    original_updated_at = model.updated_at
    sleep(0.01)

    model.update_from_dict({
        'id': 999,
        'created_at': datetime(2020, 1, 1),
        'updated_at': datetime(2020, 1, 1),
        'name': 'updated',
    })
    db_test.commit()

    assert model.id == original_id
    assert model.created_at == original_created_at
    assert model.updated_at > original_updated_at
    assert model.name == 'updated'
