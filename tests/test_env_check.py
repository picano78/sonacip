"""
Test environment validation functionality
Tests for check_env.py script that validates environment variables
"""
import os
import sys
import pytest
import subprocess
from pathlib import Path
from unittest import mock


class TestEnvironmentCheck:
    """Test the check_env.py validation script"""
    
    @pytest.fixture
    def backup_env_files(self):
        """Backup and restore .env files during tests"""
        env_file = Path('.env')
        backup_file = Path('.env.backup')
        
        # Backup existing .env if it exists
        if env_file.exists():
            env_file.rename(backup_file)
        
        yield
        
        # Restore .env after test
        if backup_file.exists():
            if env_file.exists():
                env_file.unlink()
            backup_file.rename(env_file)
        elif env_file.exists():
            env_file.unlink()
    
    def run_check_env(self, env_vars=None):
        """Helper to run check_env.py with specific environment variables"""
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)
        
        result = subprocess.run(
            [sys.executable, 'check_env.py'],
            capture_output=True,
            text=True,
            env=env
        )
        return result
    
    def test_check_env_script_exists(self):
        """Test that check_env.py script exists"""
        assert Path('check_env.py').exists(), "check_env.py script not found"
    
    def test_creates_env_from_example(self, backup_env_files):
        """Test that script creates .env from .env.example if missing"""
        env_file = Path('.env')
        env_example = Path('.env.example')
        
        # Ensure .env doesn't exist
        if env_file.exists():
            env_file.unlink()
        
        # Ensure .env.example exists
        assert env_example.exists(), ".env.example must exist for this test"
        
        # Run the check
        result = self.run_check_env({'APP_ENV': 'development'})
        
        # Check that .env was created
        assert env_file.exists(), ".env file should be created"
        assert "Creating .env from .env.example" in result.stdout
        assert "✓ .env file created" in result.stdout
    
    def test_production_mode_requires_credentials(self, backup_env_files):
        """Test that production mode fails without proper credentials"""
        env_file = Path('.env')
        
        # Create .env with production mode but placeholder credentials
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=CHANGEME_GENERATE_WITH_PYTHON_SECRETS\n"
            "SUPERADMIN_EMAIL=Picano78@gmail.com\n"
            "SUPERADMIN_PASSWORD=Simone78\n"
        )
        
        result = self.run_check_env()
        
        # Should fail
        assert result.returncode != 0, "Should fail with placeholder credentials in production"
        assert "Environment Check Failed" in result.stdout
        assert "SECRET_KEY has placeholder value" in result.stdout
        assert "SUPERADMIN_EMAIL has placeholder value" in result.stdout
        assert "SUPERADMIN_PASSWORD has placeholder value" in result.stdout
    
    def test_production_mode_with_valid_credentials(self, backup_env_files):
        """Test that production mode passes with valid credentials"""
        env_file = Path('.env')
        
        # Create .env with production mode and valid credentials
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2\n"
            "SUPERADMIN_EMAIL=admin@mycompany.com\n"
            "SUPERADMIN_PASSWORD=SecurePassword123!\n"
        )
        
        result = self.run_check_env()
        
        # Should pass
        assert result.returncode == 0, f"Should pass with valid credentials. Output: {result.stdout}"
        assert "Environment Check Passed" in result.stdout
        assert "Production Mode Detected" in result.stdout
    
    def test_production_mode_missing_email(self, backup_env_files):
        """Test that production mode fails if SUPERADMIN_EMAIL is missing"""
        env_file = Path('.env')
        
        # Create .env with production mode but missing email
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2\n"
            "SUPERADMIN_PASSWORD=SecurePassword123!\n"
        )
        
        result = self.run_check_env()
        
        # Should fail
        assert result.returncode != 0, "Should fail with missing email in production"
        assert "SUPERADMIN_EMAIL" in result.stdout
        assert "NOT SET" in result.stdout
    
    def test_production_mode_missing_password(self, backup_env_files):
        """Test that production mode fails if SUPERADMIN_PASSWORD is missing"""
        env_file = Path('.env')
        
        # Create .env with production mode but missing password
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2\n"
            "SUPERADMIN_EMAIL=admin@mycompany.com\n"
        )
        
        result = self.run_check_env()
        
        # Should fail
        assert result.returncode != 0, "Should fail with missing password in production"
        assert "SUPERADMIN_PASSWORD" in result.stdout
        assert "NOT SET" in result.stdout
    
    def test_development_mode_allows_missing_credentials(self, backup_env_files):
        """Test that development mode allows missing credentials"""
        env_file = Path('.env')
        
        # Create .env with development mode and minimal config
        env_file.write_text(
            "APP_ENV=development\n"
            "SECRET_KEY=dev-secret-key\n"
        )
        
        result = self.run_check_env()
        
        # Should pass
        assert result.returncode == 0, f"Should pass in development mode. Output: {result.stdout}"
        assert "Environment Check Passed" in result.stdout
        assert "Development Mode" in result.stdout
        assert "Random credentials will be generated" in result.stdout
    
    def test_development_mode_with_credentials(self, backup_env_files):
        """Test that development mode works with credentials set"""
        env_file = Path('.env')
        
        # Create .env with development mode and credentials
        env_file.write_text(
            "APP_ENV=development\n"
            "SECRET_KEY=dev-secret-key\n"
            "SUPERADMIN_EMAIL=dev@localhost\n"
            "SUPERADMIN_PASSWORD=DevPassword123!\n"
        )
        
        result = self.run_check_env()
        
        # Should pass
        assert result.returncode == 0, f"Should pass in development mode. Output: {result.stdout}"
        assert "Environment Check Passed" in result.stdout
    
    def test_masks_sensitive_values(self, backup_env_files):
        """Test that sensitive values are masked in output"""
        env_file = Path('.env')
        
        # Create .env with valid credentials
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2\n"
            "SUPERADMIN_EMAIL=admin@mycompany.com\n"
            "SUPERADMIN_PASSWORD=SecurePassword123!\n"
        )
        
        result = self.run_check_env()
        
        # Check that sensitive values are masked
        assert "***" in result.stdout, "Sensitive values should be masked"
        # The full secret key should not be visible
        assert "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2" not in result.stdout
        # The full password should not be visible
        assert "SecurePassword123!" not in result.stdout or "***123!" in result.stdout
    
    def test_shows_helpful_error_messages(self, backup_env_files):
        """Test that error messages provide helpful guidance"""
        env_file = Path('.env')
        
        # Create .env with missing required variables
        env_file.write_text("APP_ENV=production\n")
        
        result = self.run_check_env()
        
        # Check for helpful error messages
        assert result.returncode != 0
        assert "How to fix:" in result.stdout
        assert "Edit the .env file" in result.stdout
        assert "SUPERADMIN_EMAIL=" in result.stdout
        assert "SUPERADMIN_PASSWORD=" in result.stdout
    
    def test_detects_flask_env_production(self, backup_env_files):
        """Test that FLASK_ENV=production is also detected"""
        env_file = Path('.env')
        
        # Create .env with FLASK_ENV instead of APP_ENV
        env_file.write_text(
            "FLASK_ENV=production\n"
            "SECRET_KEY=test-key\n"
        )
        
        result = self.run_check_env()
        
        # Should fail in production mode
        assert result.returncode != 0
        assert "SUPERADMIN_EMAIL" in result.stdout
    
    def test_recommended_variables_shown_as_warnings(self, backup_env_files):
        """Test that recommended but optional variables show as warnings"""
        env_file = Path('.env')
        
        # Create .env with minimal valid production config
        env_file.write_text(
            "APP_ENV=production\n"
            "SECRET_KEY=a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1b2\n"
            "SUPERADMIN_EMAIL=admin@mycompany.com\n"
            "SUPERADMIN_PASSWORD=SecurePassword123!\n"
        )
        
        result = self.run_check_env()
        
        # Should pass but with warnings
        assert result.returncode == 0, f"Should pass with minimal config. Output: {result.stdout}"
        assert "Warnings:" in result.stdout
        assert "optional" in result.stdout.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
