FROM python:3.13-slim

WORKDIR /app
RUN pip install --no-cache-dir "fastapi>=0.115" "uvicorn>=0.34"
COPY main.py .

EXPOSE 9000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
