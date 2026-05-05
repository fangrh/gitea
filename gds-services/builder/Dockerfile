FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y git libexpat1 libssl3 libcurl4 && rm -rf /var/lib/apt/lists/*
COPY gds-services/builder/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY gdsfactory /gdsfactory
RUN pip install --no-cache-dir -e /gdsfactory
COPY gds-services/builder/main.py .
EXPOSE 8001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
