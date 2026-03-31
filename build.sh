#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput

# verification logs for Render deploy visibility
python manage.py showmigrations vendor_portal
python manage.py dbshell <<'SQL'
SELECT name FROM sqlite_master WHERE type='table' AND name='vendor_portal_user';
SQL

python manage.py ensure_initial_admin
