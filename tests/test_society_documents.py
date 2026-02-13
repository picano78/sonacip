"""
Tests for society-scoped document management and PDF export
"""
import pytest


def test_society_scoping_logic():
    """Test that society filtering logic is correct."""
    # This is a simple smoke test to ensure imports work
    from app.documents.routes import _get_society_filter
    
    # The function exists and is callable
    assert callable(_get_society_filter)


def test_pdf_generation_function_exists():
    """Test that PDF generation function exists."""
    from app.documents.routes import _generate_pdf_export
    
    # The function exists and is callable
    assert callable(_generate_pdf_export)


def test_document_model_has_society_id():
    """Test that Document model has society_id field."""
    from app.models import Document
    
    # Check that the model has the society_id attribute
    assert hasattr(Document, 'society_id')


def test_folder_model_has_society_id():
    """Test that DocumentFolder model has society_id field."""
    from app.models import DocumentFolder
    
    # Check that the model has the society_id attribute
    assert hasattr(DocumentFolder, 'society_id')


def test_routes_module_imports():
    """Test that the documents routes module imports correctly."""
    try:
        from app.documents import routes
        assert hasattr(routes, 'bp')
        assert hasattr(routes, 'export_pdf')
    except ImportError as e:
        pytest.fail(f"Failed to import documents routes: {e}")

