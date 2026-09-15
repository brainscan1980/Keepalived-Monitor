FROM python:3.13-alpine
WORKDIR /app
RUN apk add --no-cache openssh-client && pip install --no-cache-dir flask pyyaml gunicorn
COPY app /app
RUN mkdir -p /app/data
EXPOSE 8080
CMD ["gunicorn","--bind","0.0.0.0:8080","--workers","1","--threads","4","app:app"]
