FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && \
    apt-get install -y \
    libpq-dev \
    build-essential \
    curl \
    git && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

CMD ["fastapi", "dev", "--host", "0.0.0.0", "--port", "8000"]
