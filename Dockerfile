FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8002

CMD ["sh", "-c", "python manage.py migrate && python manage.py collectstatic --noinput && gunicorn project.wsgi:application --bind 0.0.0.0:8002 --workers 3 --timeout 120"]
