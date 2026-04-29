FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV COORDINATOR_HOST=0.0.0.0
ENV COORDINATOR_PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY run_coordinator.py ./

EXPOSE 8000

CMD ["python", "run_coordinator.py"]
