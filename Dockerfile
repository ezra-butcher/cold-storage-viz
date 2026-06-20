FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY fetch_data.py fit_forecasts.py app.py ./

# data/ is mounted at runtime so the cache persists across container restarts
VOLUME ["/app/data"]

EXPOSE 8050

CMD ["python", "app.py"]
