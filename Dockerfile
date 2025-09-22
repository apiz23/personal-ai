# Gunakan Python slim
FROM python:3.11-slim

# Working directory
WORKDIR /app

# Copy requirements & install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY . .

# Set PORT env (Fly.io will map)
ENV PORT=8080

# Start FastAPI
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
