FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN apk add --no-cache openssh-client \
    && pip install --no-cache-dir -r /app/requirements.txt \
    && mkdir -p /etc/ssh/ssh_config.d \
    && printf '%s\n' \
       'Host *' \
       '    ControlMaster auto' \
       '    ControlPersist 60' \
       '    ControlPath /tmp/keepalived-monitor-ssh-%C' \
       '    ServerAliveInterval 30' \
       '    ServerAliveCountMax 2' \
       > /etc/ssh/ssh_config.d/keepalived-monitor.conf

COPY app /app
COPY VERSION /app/static/VERSION

RUN mkdir -p /app/data

EXPOSE 5001

CMD ["gunicorn","--bind","0.0.0.0:5001","--workers","1","--threads","4","wsgi:app"]
