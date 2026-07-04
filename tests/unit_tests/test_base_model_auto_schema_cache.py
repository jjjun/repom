"""Regression tests for BaseModelAuto generated schema caches."""

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from repom.models.base_model_auto import BaseModelAuto


class SchemaCacheModel(BaseModelAuto):
    __tablename__ = 'schema_cache_model'

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


def test_create_schema_cache_respects_exclude_fields_in_both_orders():
    PlainFirst = SchemaCacheModel.get_create_schema(
        schema_name='CreateCachePlainFirst'
    )
    ExcludedSecond = SchemaCacheModel.get_create_schema(
        schema_name='CreateCachePlainFirst',
        exclude_fields=['name']
    )

    assert 'name' in PlainFirst.model_fields
    assert 'name' not in ExcludedSecond.model_fields
    assert 'age' in ExcludedSecond.model_fields
    assert PlainFirst is not ExcludedSecond

    ExcludedFirst = SchemaCacheModel.get_create_schema(
        schema_name='CreateCacheExcludedFirst',
        exclude_fields=['name']
    )
    PlainSecond = SchemaCacheModel.get_create_schema(
        schema_name='CreateCacheExcludedFirst'
    )

    assert 'name' not in ExcludedFirst.model_fields
    assert 'age' in ExcludedFirst.model_fields
    assert 'name' in PlainSecond.model_fields
    assert ExcludedFirst is not PlainSecond


def test_update_schema_cache_respects_exclude_fields_in_both_orders():
    PlainFirst = SchemaCacheModel.get_update_schema(
        schema_name='UpdateCachePlainFirst'
    )
    ExcludedSecond = SchemaCacheModel.get_update_schema(
        schema_name='UpdateCachePlainFirst',
        exclude_fields=['name']
    )

    assert 'name' in PlainFirst.model_fields
    assert 'name' not in ExcludedSecond.model_fields
    assert 'age' in ExcludedSecond.model_fields
    assert PlainFirst is not ExcludedSecond

    ExcludedFirst = SchemaCacheModel.get_update_schema(
        schema_name='UpdateCacheExcludedFirst',
        exclude_fields=['name']
    )
    PlainSecond = SchemaCacheModel.get_update_schema(
        schema_name='UpdateCacheExcludedFirst'
    )

    assert 'name' not in ExcludedFirst.model_fields
    assert 'age' in ExcludedFirst.model_fields
    assert 'name' in PlainSecond.model_fields
    assert ExcludedFirst is not PlainSecond


def _make_duplicate_named_model(module_name: str, table_name: str, field_name: str):
    return type(
        'DuplicateModel',
        (BaseModelAuto,),
        {
            '__module__': module_name,
            '__tablename__': table_name,
            '__annotations__': {field_name: Mapped[str]},
            field_name: mapped_column(String(100), nullable=False),
        }
    )


def test_schema_caches_are_keyed_by_model_class_identity():
    ModelA = _make_duplicate_named_model(
        'tests.unit_tests.schema_cache_namespace_a',
        'schema_cache_duplicate_a',
        'alpha'
    )
    ModelB = _make_duplicate_named_model(
        'tests.unit_tests.schema_cache_namespace_b',
        'schema_cache_duplicate_b',
        'beta'
    )

    assert ModelA.__name__ == ModelB.__name__
    assert ModelA.__module__ != ModelB.__module__

    CreateA = ModelA.get_create_schema()
    CreateB = ModelB.get_create_schema()
    assert 'alpha' in CreateA.model_fields
    assert 'beta' not in CreateA.model_fields
    assert 'beta' in CreateB.model_fields
    assert 'alpha' not in CreateB.model_fields

    UpdateA = ModelA.get_update_schema()
    UpdateB = ModelB.get_update_schema()
    assert 'alpha' in UpdateA.model_fields
    assert 'beta' not in UpdateA.model_fields
    assert 'beta' in UpdateB.model_fields
    assert 'alpha' not in UpdateB.model_fields

    ResponseA = ModelA.get_response_schema()
    ResponseB = ModelB.get_response_schema()
    assert 'alpha' in ResponseA.model_fields
    assert 'beta' not in ResponseA.model_fields
    assert 'beta' in ResponseB.model_fields
    assert 'alpha' not in ResponseB.model_fields
