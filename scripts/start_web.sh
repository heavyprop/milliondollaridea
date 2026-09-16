#!/bin/sh
set -eu

echo "Applying database migrations..."
python manage.py migrate --noinput
echo "Preparing the classification model (first run downloads it)..."
python -c 'from apps.recommendations.classification import get_classifier; get_classifier()'
echo "Website ready at http://localhost:${WEB_PORT:-8000}"
exec python manage.py runserver 0.0.0.0:8000
