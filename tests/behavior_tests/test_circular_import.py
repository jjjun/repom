"""Regression coverage for model discovery with circular relationships."""

from pathlib import Path
import subprocess
import sys


def test_load_models_configures_circular_relationship_models():
    script = """
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from repom.config import config
from repom.utility import load_models

config.model_locations = [
    "tests.fixtures.circular_import.package_a",
    "tests.fixtures.circular_import.package_b",
]
config.model_excluded_dirs = set()
config.allowed_package_prefixes = {"tests.fixtures.circular_import.", "repom."}

failures = load_models(strict=True)
assert failures == []

from repom.models.base_model import BaseModel
from tests.fixtures.circular_import.package_a.model_a import ModelA
from tests.fixtures.circular_import.package_b.model_b import ModelB

assert "test_model_a" in BaseModel.metadata.tables
assert "test_model_b" in BaseModel.metadata.tables

engine = create_engine("sqlite:///:memory:")
BaseModel.metadata.create_all(
    engine,
    tables=[
        BaseModel.metadata.tables["test_model_a"],
        BaseModel.metadata.tables["test_model_b"],
    ],
)

with Session(engine) as session:
    parent = ModelA(name="parent")
    parent.children.append(ModelB())
    session.add(parent)
    session.commit()
    parent_id = parent.id

with Session(engine) as session:
    parent = session.get(ModelA, parent_id)
    assert len(parent.children) == 1
    assert parent.children[0].parent is parent
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
