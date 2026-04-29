#!/bin/bash
# Rebuild Tailwind CSS — jalankan setiap kali ada perubahan di templates atau app.css
set -e
echo "Building Tailwind CSS..."
docker compose run --rm tailwind
echo "Done. CSS saved to app/src/static/css/app.css"
