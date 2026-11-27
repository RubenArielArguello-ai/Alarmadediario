FROM python:3.11.15-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app/hibrido

COPY hibrido/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY hibrido/*.py ./
COPY hibrido/static/ ./static/

EXPOSE 8000

CMD ["python", "server.py", "--host", "0.0.0.0"]
