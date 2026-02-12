#!/bin/bash
echo "🔒 Running Security Test Suite..."
python -m pytest tests/test_security_advanced.py -v
python security_scan.py
echo "✅ Security tests completed!"
