FROM python:3.13-alpine
WORKDIR /app
RUN apk add --no-cache openssh-client && pip install --no-cache-dir flask pyyaml gunicorn cryptography
COPY app /app
COPY VERSION /app/static/VERSION
RUN mkdir -p /app/data
EXPOSE 5001
CMD ["gunicorn","--bind","0.0.0.0:5001","--workers","1","--threads","4","wsgi:app"]
