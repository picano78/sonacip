#!/usr/bin/env python3
"""
Security Scan Script
Esegue controlli automatici di sicurezza sul codice
"""

import os
import re
import sys
from pathlib import Path

class SecurityScanner:
    """Scanner per vulnerabilità comuni"""
    
    def __init__(self):
        self.issues = []
        self.warnings = []
    
    def scan_hardcoded_secrets(self, directory='.'):
        """Cerca credenziali hardcoded"""
        print("🔍 Scanning for hardcoded secrets...")
        
        patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', 'Possible hardcoded password'),
            (r'api[_-]?key\s*=\s*["\'][^"\']+["\']', 'Possible hardcoded API key'),
            (r'secret[_-]?key\s*=\s*["\'][^"\']{20,}["\']', 'Possible hardcoded secret'),
        ]
        
        for root, dirs, files in os.walk(directory):
            # Skip venv, node_modules, etc.
            dirs[:] = [d for d in dirs if d not in ['venv', 'node_modules', '.git', '__pycache__']]
            
            for file in files:
                if file.endswith(('.py', '.js', '.env')):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                            content = f.read()
                            for pattern, message in patterns:
                                if re.search(pattern, content, re.IGNORECASE):
                                    self.warnings.append(f"{filepath}: {message}")
                    except Exception:
                        pass
    
    def scan_sql_injection_risks(self, directory='.'):
        """Cerca potenziali SQL injection"""
        print("🔍 Scanning for SQL injection risks...")
        
        risky_patterns = [
            r'execute\([^)]*\%',
            r'cursor\.execute\([^)]*f["\']',
        ]
        
        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in ['venv', 'node_modules', '.git']]
            
            for file in files:
                if file.endswith('.py'):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            for pattern in risky_patterns:
                                if re.search(pattern, content):
                                    self.issues.append(f"{filepath}: Possible SQL injection risk")
                    except Exception:
                        pass
    
    def check_security_headers(self):
        """Verifica configurazione security headers"""
        print("🔍 Checking security headers configuration...")
        
        config_file = 'app/core/config.py'
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                content = f.read()
                
                required = [
                    ('SECURITY_HEADERS_ENABLED', 'Security headers not enabled'),
                    ('HSTS_ENABLED', 'HSTS not enabled'),
                    ('CSP_ENABLED', 'CSP not enabled'),
                ]
                
                for setting, message in required:
                    if setting not in content:
                        self.warnings.append(f"{config_file}: {message}")
    
    def report(self):
        """Stampa report"""
        print("\n" + "="*60)
        print("SECURITY SCAN REPORT")
        print("="*60)
        
        if self.issues:
            print(f"\n🚨 CRITICAL ISSUES FOUND: {len(self.issues)}")
            for issue in self.issues:
                print(f"  - {issue}")
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)}")
            for warning in self.warnings:
                print(f"  - {warning}")
        
        if not self.issues and not self.warnings:
            print("\n✅ No security issues found!")
        
        print("="*60)
        
        return len(self.issues)

if __name__ == '__main__':
    scanner = SecurityScanner()
    scanner.scan_hardcoded_secrets()
    scanner.scan_sql_injection_risks()
    scanner.check_security_headers()
    
    exit_code = scanner.report()
    sys.exit(exit_code)
