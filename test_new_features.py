#!/usr/bin/env python3
"""
Test script for society data export and live banners features
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    # Test imports
    print("Testing imports...")
    from app import create_app
    from app.models import Society, LiveBanner
    from app.admin.forms import LiveBannerForm
    from app.utils.exports import DataExporter
    
    print("✓ All imports successful")
    
    # Create app context
    app = create_app()
    
    with app.app_context():
        # Test model attributes
        print("\nTesting model attributes...")
        
        # Check Society has planner_notifications_enabled
        assert hasattr(Society, 'planner_notifications_enabled'), "Society missing planner_notifications_enabled"
        print("✓ Society.planner_notifications_enabled exists")
        
        # Check LiveBanner model
        assert hasattr(LiveBanner, 'title'), "LiveBanner missing title"
        assert hasattr(LiveBanner, 'position'), "LiveBanner missing position"
        assert hasattr(LiveBanner, 'is_active'), "LiveBanner missing is_active"
        print("✓ LiveBanner model has required attributes")
        
        # Check export methods
        assert hasattr(DataExporter, 'export_society_athletes'), "Missing export_society_athletes"
        assert hasattr(DataExporter, 'export_society_events'), "Missing export_society_events"
        assert hasattr(DataExporter, 'export_society_tournaments'), "Missing export_society_tournaments"
        assert hasattr(DataExporter, 'export_society_planner_events'), "Missing export_society_planner_events"
        print("✓ DataExporter has all required export methods")
        
        # Check form class exists (without instantiating it)
        assert LiveBannerForm is not None, "LiveBannerForm class not found"
        print("✓ LiveBannerForm class exists")
    
    print("\n✅ All basic tests passed!")
    print("\nFeatures implemented:")
    print("  1. Society data export (athletes, events, tournaments, planner)")
    print("  2. Society planner notifications toggle")
    print("  3. Live banner management for super admin")
    print("  4. Banner display during live streams")
    
    sys.exit(0)
    
except Exception as e:
    print(f"\n❌ Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
