FROM golang:1.25-alpine AS builder
WORKDIR /src
COPY go.mod ./
COPY cmd ./cmd
ARG VERSION=dev
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w -X main.version=${VERSION}" -o /out/keepalived-monitor ./cmd/keepalived-monitor

FROM alpine:3.22
RUN apk add --no-cache ca-certificates tzdata && addgroup -S monitor && adduser -S -G monitor monitor
WORKDIR /app
COPY --from=builder /out/keepalived-monitor /usr/local/bin/keepalived-monitor
USER monitor
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 CMD wget -q -O- http://127.0.0.1:8080/healthz >/dev/null || exit 1
ENTRYPOINT ["/usr/local/bin/keepalived-monitor"]
