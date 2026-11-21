#!/bin/bash
# Dolibarr Backup Service - Setup Script

set -e
umask 077

echo "=========================================="
echo " Dolibarr Backup Service - Setup"
echo "=========================================="
echo ""

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.8 or higher."
    exit 1
fi

echo "✓ Python 3 found: $(python3 --version)"

# Check if pip is installed
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 is not installed. Please install pip3."
    exit 1
fi

echo "✓ pip3 found"

# Check if mysql/mariadb client is installed
if ! command -v mysql &> /dev/null && ! command -v mariadb &> /dev/null; then
    echo "⚠️  Warning: MySQL/MariaDB client not found. Install it with:"
    echo "   - Ubuntu/Debian: sudo apt-get install mariadb-client"
    echo "   - macOS: brew install mariadb"
    echo "   - CentOS/RHEL: sudo yum install mariadb"
fi

# Create virtual environment
echo ""
echo "Creating Python virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip > /dev/null 2>&1
pip install -r requirements.txt

echo "✓ Dependencies installed"

# Create necessary directories
echo ""
echo "Creating directories..."
mkdir -p backups
mkdir -p logs
mkdir -p backup-config

echo "✓ Directories created"

# Check for .env file
echo ""
if [ ! -f ".env" ]; then
    echo "⚠️  No .env file found. Creating from .env.example..."
    cp .env.example .env
    echo "✓ .env file created"
    echo ""
    echo "⚠️  IMPORTANT: Edit the .env file with your configuration:"
    echo "   - Database credentials"
    echo "   - Google Drive folder ID"
    echo "   - Documents path"
    echo ""
else
    echo "✓ .env file exists"
fi

# Check for service account file
echo ""
if [ ! -f "backup-config/service-account.json" ]; then
    echo "⚠️  Google service account file not found!"
    echo "   Place your service-account.json in: backup-config/"
    echo ""
else
    echo "✓ Service account file found"
fi

echo ""
echo "=========================================="
echo " Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit .env file with your configuration"
echo "  2. Place service-account.json in backup-config/"
echo "  3. Run a test backup:"
echo "     source venv/bin/activate && python3 backup.py"
echo ""
echo "To schedule automated backups, add to crontab:"
echo "  crontab -e"
echo ""
echo "Add this line (runs daily at 3 AM):"
echo "  0 3 * * * cd $(pwd) && venv/bin/python3 backup.py >> logs/cron.log 2>&1"
echo ""
