FROM python:3.14.6-alpine3.24

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt

RUN apk upgrade --no-cache \
    && apk add --no-cache openssh-client \
    && python -m pip install --no-cache-dir -r /app/requirements.txt \
    && python -m pip uninstall -y pip setuptools wheel 2>/dev/null || true

RUN mkdir -p /etc/ssh/ssh_config.d \
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
