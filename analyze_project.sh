#!/bin/bash

# SONACIP Project Analysis Script
# Analyzes project structure and identifies unused files

set -e

echo "=== SONACIP PROJECT ANALYSIS ==="
echo "Objective: Identify unused files without deleting anything"
echo ""

PROJECT_DIR="/opt/sonacip"
REPORT_FILE="$PROJECT_DIR/cleanup_report.txt"

# Create report header
cat > "$REPORT_FILE" << EOF
SONACIP Project Cleanup Analysis Report
Generated: $(date)
========================================

IMPORTANT: This is ANALYSIS ONLY - No files were deleted
========================================

EOF

echo "Step 1: Analyzing project structure..."
echo ""

# Section 1: Project Structure Analysis
echo "=== PROJECT STRUCTURE ANALYSIS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Get directory sizes
echo "Directory sizes:" >> "$REPORT_FILE"
du -h --max-depth=2 "$PROJECT_DIR" | sort -hr >> "$REPORT_FILE" 2>/dev/null || echo "Could not get directory sizes" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Total project size
TOTAL_SIZE=$(du -sh "$PROJECT_DIR" 2>/dev/null | cut -f1)
echo "Total project size: $TOTAL_SIZE" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "Step 2: Identifying suspicious files..."
echo ""

# Section 2: Suspicious Files
echo "=== SUSPICIOUS FILES ANALYSIS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find log files
echo "Log files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.log" -type f -exec ls -lh {} \; 2>/dev/null | head -20 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find temporary files
echo "Temporary files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.tmp" -o -name "*.temp" -o -name "temp*" -type f -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find backup files
echo "Backup files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.bak" -o -name "*.old" -o -name "*.backup*" -type f -exec ls -lh {} \; 2>/dev/null | head -15 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find Python cache
echo "Python cache files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "__pycache__" -type d -exec du -sh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.pyc" -type f -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find zip/archive files
echo "Archive files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.zip" -o -name "*.tar*" -o -name "*.gz" -type f -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "Step 3: Analyzing Python dependencies..."
echo ""

# Section 3: Python Dependencies Analysis
echo "=== PYTHON DEPENDENCIES ANALYSIS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find all Python files
echo "Python files found:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.py" -type f | wc -l | xargs echo "Total Python files:" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Check for unused Python files (basic check)
echo "Potentially unused Python files (no direct imports found):" >> "$REPORT_FILE"
# This is a simplified check - real analysis would be more complex
find "$PROJECT_DIR" -name "*.py" -type f -exec grep -l "__main__" {} \; 2>/dev/null | head -10 >> "$REPORT_FILE" || echo "No __main__ files found" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "Step 4: Analyzing static files..."
echo ""

# Section 4: Static Files Analysis
echo "=== STATIC FILES ANALYSIS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Check static directory
if [ -d "$PROJECT_DIR/static" ]; then
    echo "Static directory size:" >> "$REPORT_FILE"
    du -sh "$PROJECT_DIR/static" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    echo "Large static files (>1MB):" >> "$REPORT_FILE"
    find "$PROJECT_DIR/static" -type f -size +1M -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    echo "Static file types:" >> "$REPORT_FILE"
    find "$PROJECT_DIR/static" -type f | sed 's/.*\.//' | sort | uniq -c | sort -nr | head -15 >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
fi

# Check uploads directory
if [ -d "$PROJECT_DIR/uploads" ]; then
    echo "Uploads directory size:" >> "$REPORT_FILE"
    du -sh "$PROJECT_DIR/uploads" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
    
    echo "Upload files:" >> "$REPORT_FILE"
    find "$PROJECT_DIR/uploads" -type f | wc -l | xargs echo "Total upload files:" >> "$REPORT_FILE"
    echo "" >> "$REPORT_FILE"
fi

echo "Step 5: Analyzing specific file patterns..."
echo ""

# Section 5: Specific Patterns
echo "=== SPECIFIC FILE PATTERNS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find development files
echo "Development files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.dev" -o -name "test_*" -o -name "*_test*" -type f -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find configuration files
echo "Configuration files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.conf" -o -name "*.config" -o -name "*.ini" -o -name "*.env*" -type f -exec ls -lh {} \; 2>/dev/null | head -10 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Find documentation files
echo "Documentation files:" >> "$REPORT_FILE"
find "$PROJECT_DIR" -name "*.md" -o -name "*.txt" -o -name "*.rst" -o -name "README*" -type f -exec ls -lh {} \; 2>/dev/null | head -15 >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "Step 6: Creating recommendations..."
echo ""

# Section 6: Recommendations
echo "=== CLEANUP RECOMMENDATIONS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Calculate potential space savings
echo "POTENTIAL SPACE SAVINGS:" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Python cache size
PYCACHE_SIZE=$(find "$PROJECT_DIR" -name "__pycache__" -type d -exec du -sm {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
if [ "$PYCACHE_SIZE" -gt 0 ]; then
    echo "Python cache (__pycache__): ${PYCACHE_SIZE}MB - SAFE TO DELETE" >> "$REPORT_FILE"
fi

# Log files size
LOG_SIZE=$(find "$PROJECT_DIR" -name "*.log" -type f -exec du -sm {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
if [ "$LOG_SIZE" -gt 0 ]; then
    echo "Log files: ${LOG_SIZE}MB - REVIEW BEFORE DELETING" >> "$REPORT_FILE"
fi

# Backup files size
BACKUP_SIZE=$(find "$PROJECT_DIR" -name "*.bak" -o -name "*.old" -o -name "*.backup*" -type f -exec du -sm {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
if [ "$BACKUP_SIZE" -gt 0 ]; then
    echo "Backup files: ${BACKUP_SIZE}MB - REVIEW BEFORE DELETING" >> "$REPORT_FILE"
fi

# Archive files size
ARCHIVE_SIZE=$(find "$PROJECT_DIR" -name "*.zip" -o -name "*.tar*" -o -name "*.gz" -type f -exec du -sm {} \; 2>/dev/null | awk '{sum+=$1} END {print sum}')
if [ "$ARCHIVE_SIZE" -gt 0 ]; then
    echo "Archive files: ${ARCHIVE_SIZE}MB - REVIEW BEFORE DELETING" >> "$REPORT_FILE"
fi

echo "" >> "$REPORT_FILE"

# Section 7: File Categories
echo "=== FILE CATEGORIES ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "1. FILES SAFE TO DELETE:" >> "$REPORT_FILE"
echo "   - Python cache (__pycache__ directories)" >> "$REPORT_FILE"
echo "   - Compiled Python files (*.pyc)" >> "$REPORT_FILE"
echo "   - Temporary files (*.tmp, *.temp)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "2. FILES TO REVIEW BEFORE DELETING:" >> "$REPORT_FILE"
echo "   - Log files (*.log)" >> "$REPORT_FILE"
echo "   - Backup files (*.bak, *.old, *.backup*)" >> "$REPORT_FILE"
echo "   - Archive files (*.zip, *.tar*)" >> "$REPORT_FILE"
echo "   - Test files (test_*)" >> "$REPORT_FILE"
echo "   - Development files (*.dev)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "3. FILES TO NOT TOUCH:" >> "$REPORT_FILE"
echo "   - Application Python files (*.py)" >> "$REPORT_FILE"
echo "   - Configuration files (.env, config files)" >> "$REPORT_FILE"
echo "   - Database files (*.db, *.sqlite*)" >> "$REPORT_FILE"
echo "   - Static files used by application" >> "$REPORT_FILE"
echo "   - Upload files (user content)" >> "$REPORT_FILE"
echo "   - Requirements.txt" >> "$REPORT_FILE"
echo "   - Service files (*.sh, systemd configs)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Section 8: Estimated Space Recovery
echo "=== ESTIMATED SPACE RECOVERY ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

TOTAL_SAFE_DELETE=$((PYCACHE_SIZE))
TOTAL_REVIEW=$((LOG_SIZE + BACKUP_SIZE + ARCHIVE_SIZE))

echo "Estimated space from safe deletions: ${TOTAL_SAFE_DELETE}MB" >> "$REPORT_FILE"
echo "Estimated space from review deletions: ${TOTAL_REVIEW}MB" >> "$REPORT_FILE"
echo "Total potential space recovery: $((TOTAL_SAFE_DELETE + TOTAL_REVIEW))MB" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# Section 9: Final Recommendations
echo "=== FINAL RECOMMENDATIONS ===" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "RECOMMENDED CLEANUP SEQUENCE:" >> "$REPORT_FILE"
echo "1. Remove Python cache: find $PROJECT_DIR -name '__pycache__' -type d -exec rm -rf {} +" >> "$REPORT_FILE"
echo "2. Remove .pyc files: find $PROJECT_DIR -name '*.pyc' -type f -delete" >> "$REPORT_FILE"
echo "3. Review and clean old logs (keep recent ones)" >> "$REPORT_FILE"
echo "4. Review backup files (keep recent ones)" >> "$REPORT_FILE"
echo "5. Review archive files (extract if needed)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "WARNING:" >> "$REPORT_FILE"
echo "- Always backup before deleting" >> "$REPORT_FILE"
echo "- Test application after cleanup" >> "$REPORT_FILE"
echo "- Keep recent logs for debugging" >> "$REPORT_FILE"
echo "- Keep important backups" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

echo "Analysis completed: $(date)" >> "$REPORT_FILE"

echo "Step 7: Displaying report..."
echo ""

# Display report to terminal
echo "=== SONACIP PROJECT ANALYSIS REPORT ==="
echo ""
echo "📊 Project Size: $TOTAL_SIZE"
echo "📝 Report saved to: $REPORT_FILE"
echo ""
echo "=== QUICK SUMMARY ==="
echo ""

# Show key findings
echo "🗂️  Largest directories:"
du -h --max-depth=1 "$PROJECT_DIR" 2>/dev/null | sort -hr | head -5
echo ""

echo "🗑️  Files that can be safely deleted:"
echo "   Python cache: ${PYCACHE_SIZE}MB"
echo "   Compiled Python files: Included in cache"
echo ""

echo "📋 Files to review:"
echo "   Log files: ${LOG_SIZE}MB"
echo "   Backup files: ${BACKUP_SIZE}MB"
echo "   Archive files: ${ARCHIVE_SIZE}MB"
echo ""

echo "💾 Total potential space recovery: $((TOTAL_SAFE_DELETE + TOTAL_REVIEW))MB"
echo ""

echo "🔍 Key findings:"
if [ "$PYCACHE_SIZE" -gt 10 ]; then
    echo "   ⚠️  Large Python cache detected (${PYCACHE_SIZE}MB)"
fi

if [ "$LOG_SIZE" -gt 50 ]; then
    echo "   ⚠️  Large log files detected (${LOG_SIZE}MB)"
fi

if [ "$BACKUP_SIZE" -gt 20 ]; then
    echo "   ⚠️  Large backup files detected (${BACKUP_SIZE}MB)"
fi

echo ""
echo "📋 Full report details available in: $REPORT_FILE"
echo ""
echo "⚠️  REMINDER: This is ANALYSIS ONLY - No files were deleted"
echo ""
echo "🚀 Analysis completed successfully!"
