FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HOME=/cache/huggingface

WORKDIR /app
COPY requirements/ requirements/
# CPU wheels avoid downloading GPU runtimes for local development.
RUN pip install --no-cache-dir torch==2.14.0+cpu --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements/development.txt
COPY . .
RUN pip install --no-cache-dir --no-deps -e .

CMD ["sh", "scripts/start_web.sh"]
