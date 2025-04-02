# docker/dashboard.Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY dashboard/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY dashboard/app.py .

EXPOSE 8501

CMD ["streamlit", "run", "app.py"]