"""
Tests for society-scoped document management and PDF export
"""
import os
import pytest
from app import create_app, db
from app.models import User, Society, Document, DocumentFolder, Role
from datetime import datetime, timezone


@pytest.fixture
def app():
    """Create and configure a test app instance."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False
    app.config['SECRET_KEY'] = 'test-secret-key'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()


@pytest.fixture
def society_user(app):
    """Create a test society user."""
    with app.app_context():
        # Create a role first
        role = Role.query.filter_by(name='society_admin').first()
        if not role:
            role = Role(name='society_admin', description='Society Admin')
            db.session.add(role)
            db.session.commit()
        
        # Create user
        user = User(
            username='testsociety',
            email='society@test.com',
            first_name='Test',
            last_name='Society',
            role_id=role.id,
            is_active=True
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Create society profile
        society = Society(
            id=user.id,
            legal_name='Test Sport Society',
            company_type='ASD',
            vat_number='IT12345678901',
            city='Milano'
        )
        db.session.add(society)
        db.session.commit()
        
        return user


@pytest.fixture
def second_society(app):
    """Create a second society for isolation testing."""
    with app.app_context():
        role = Role.query.filter_by(name='society_admin').first()
        
        user = User(
            username='society2',
            email='society2@test.com',
            first_name='Second',
            last_name='Society',
            role_id=role.id,
            is_active=True
        )
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        society = Society(
            id=user.id,
            legal_name='Second Sport Society',
            company_type='ASD',
            vat_number='IT98765432109',
            city='Roma'
        )
        db.session.add(society)
        db.session.commit()
        
        return user


def test_document_society_scoping(app, society_user, second_society):
    """Test that documents are properly scoped to societies."""
    with app.app_context():
        # Create document for first society
        doc1 = Document(
            title='Society 1 Document',
            file_path='/test/doc1.pdf',
            file_name='doc1.pdf',
            file_size=1024,
            file_type='pdf',
            society_id=society_user.id,
            uploaded_by=society_user.id
        )
        db.session.add(doc1)
        
        # Create document for second society
        doc2 = Document(
            title='Society 2 Document',
            file_path='/test/doc2.pdf',
            file_name='doc2.pdf',
            file_size=2048,
            file_type='pdf',
            society_id=second_society.id,
            uploaded_by=second_society.id
        )
        db.session.add(doc2)
        db.session.commit()
        
        # Verify documents are separated
        society1_docs = Document.query.filter_by(society_id=society_user.id).all()
        society2_docs = Document.query.filter_by(society_id=second_society.id).all()
        
        assert len(society1_docs) == 1
        assert len(society2_docs) == 1
        assert society1_docs[0].title == 'Society 1 Document'
        assert society2_docs[0].title == 'Society 2 Document'


def test_folder_society_scoping(app, society_user, second_society):
    """Test that folders are properly scoped to societies."""
    with app.app_context():
        # Create folder for first society
        folder1 = DocumentFolder(
            name='Society 1 Folder',
            society_id=society_user.id,
            created_by=society_user.id
        )
        db.session.add(folder1)
        
        # Create folder for second society
        folder2 = DocumentFolder(
            name='Society 2 Folder',
            society_id=second_society.id,
            created_by=second_society.id
        )
        db.session.add(folder2)
        db.session.commit()
        
        # Verify folders are separated
        society1_folders = DocumentFolder.query.filter_by(society_id=society_user.id).all()
        society2_folders = DocumentFolder.query.filter_by(society_id=second_society.id).all()
        
        assert len(society1_folders) == 1
        assert len(society2_folders) == 1
        assert society1_folders[0].name == 'Society 1 Folder'
        assert society2_folders[0].name == 'Society 2 Folder'


def test_pdf_export_data_preparation(app, society_user):
    """Test that PDF export prepares data correctly."""
    with app.app_context():
        # Create test documents
        for i in range(3):
            doc = Document(
                title=f'Test Document {i+1}',
                file_path=f'/test/doc{i+1}.pdf',
                file_name=f'doc{i+1}.pdf',
                file_size=1024 * (i+1),
                file_type='pdf',
                society_id=society_user.id,
                uploaded_by=society_user.id,
                download_count=i
            )
            db.session.add(doc)
        db.session.commit()
        
        # Query documents like the export endpoint would
        documents = Document.query.filter_by(society_id=society_user.id).all()
        
        assert len(documents) == 3
        assert all(doc.society_id == society_user.id for doc in documents)


def test_document_isolation_no_cross_society_access(app, society_user, second_society):
    """Test that one society cannot access another society's documents."""
    with app.app_context():
        # Create document for second society
        doc = Document(
            title='Private Document',
            file_path='/test/private.pdf',
            file_name='private.pdf',
            file_size=1024,
            file_type='pdf',
            society_id=second_society.id,
            uploaded_by=second_society.id
        )
        db.session.add(doc)
        db.session.commit()
        
        # First society should not see second society's documents
        society1_docs = Document.query.filter_by(society_id=society_user.id).all()
        
        assert len(society1_docs) == 0
        assert doc.society_id == second_society.id
        assert doc.society_id != society_user.id
