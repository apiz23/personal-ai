FROM python:3.12-slim

# Install OS dependencies needed for PyPDF2, jamaibase, etc.
RUN apt-get update && \
    apt-get install -y build-essential libssl-dev libffi-dev python3-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
