"""ORM model metadata tests."""

from app.db.base import Base
from app.models import Client, Document, DocumentChunk


def test_models_import_successfully() -> None:
    assert Client.__name__ == "Client"
    assert Document.__name__ == "Document"
    assert DocumentChunk.__name__ == "DocumentChunk"


def test_metadata_contains_expected_tables() -> None:
    assert {"clients", "documents", "document_chunks"}.issubset(Base.metadata.tables)


def test_model_table_names() -> None:
    assert Client.__tablename__ == "clients"
    assert Document.__tablename__ == "documents"
    assert DocumentChunk.__tablename__ == "document_chunks"
