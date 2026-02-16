"""
Test dashboard customization and mobile responsiveness.
"""
import pytest
from jinja2 import Environment, FileSystemLoader


def test_dashboard_customize_template_syntax():
    """Test that the dashboard customization template is valid."""
    env = Environment(loader=FileSystemLoader('app/templates'))
    template = env.get_template('main/dashboard_customize.html')
    assert template is not None


def test_dashboard_template_syntax():
    """Test that the dashboard template is valid."""
    env = Environment(loader=FileSystemLoader('app/templates'))
    template = env.get_template('main/dashboard.html')
    assert template is not None


def test_dashboard_customize_has_no_drag_drop():
    """Verify that drag & drop functionality has been removed."""
    with open('app/templates/main/dashboard_customize.html', 'r') as f:
        content = f.read()
    
    # Check that old drag & drop code is removed
    assert 'draggable="true"' not in content
    assert 'dragstart' not in content
    assert 'dragover' not in content
    assert 'drop-zone' not in content
    
    # Check that new selection-based code is present
    assert 'widget-checkbox' in content
    assert 'toggleWidget' in content
    assert 'type="checkbox"' in content


def test_dashboard_customize_has_selection_system():
    """Verify that the new selection-based system is implemented."""
    with open('app/templates/main/dashboard_customize.html', 'r') as f:
        content = f.read()
    
    # Check for selection system elements
    assert 'checkbox' in content
    assert 'toggleWidget' in content
    assert 'moveUp' in content
    assert 'moveDown' in content
    assert 'setSize' in content
    assert 'selectedCount' in content


def test_mobile_styles_in_css():
    """Verify that mobile responsive styles are present in CSS."""
    with open('app/static/css/style.css', 'r') as f:
        content = f.read()
    
    # Check for mobile media queries
    assert '@media (max-width: 767px)' in content
    assert '@media (max-width: 374px)' in content
    assert '@media (min-width: 375px) and (max-width: 767px)' in content
    
    # Check for touch-friendly sizes
    assert 'min-height: 48px' in content or 'min-height: 44px' in content
    
    # Check for safe area insets
    assert 'env(safe-area-inset-' in content


def test_dashboard_template_has_mobile_styles():
    """Verify that dashboard template has mobile responsive styles."""
    with open('app/templates/main/dashboard.html', 'r') as f:
        content = f.read()
    
    # Check for mobile media queries
    assert '@media (max-width: 767px)' in content
    assert '@media (max-width: 480px)' in content


def test_customize_template_has_mobile_styles():
    """Verify that customize template has mobile responsive styles."""
    with open('app/templates/main/dashboard_customize.html', 'r') as f:
        content = f.read()
    
    # Check for mobile media queries
    assert '@media (max-width: 768px)' in content
    
    # Check for touch-friendly button sizes
    assert 'min-width: 44px' in content or 'min-width: 48px' in content
    assert 'min-height: 44px' in content or 'min-height: 48px' in content


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
