FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git libexpat1 libssl3 libcurl4 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY main.py viewer.html .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
