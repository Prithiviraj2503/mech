#!/usr/bin/env bash
set -o errexit

echo "Starting build process..."
pip install -r requirements.txt
echo "Requirements installed."

python manage.py collectstatic --noinput
echo "Static files collected."

python manage.py migrate --noinput
echo "Migrations applied."

# verification logs for Render deploy visibility
echo "Checking migrations for vendor_portal:"
python manage.py showmigrations vendor_portal

echo "Checking if vendor_portal_user table exists:"
python manage.py dbshell <<'SQL'
SELECT name FROM sqlite_master WHERE type='table' AND name='vendor_portal_user';
SQL

echo "Ensuring initial admin..."
python manage.py ensure_initial_admin

echo "Build process completed."
