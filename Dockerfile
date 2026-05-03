# Quad Fighter – dedicated game server
# ─────────────────────────────────────
# Build:
#   docker build -t quad-fighter-server .
#
# Run:
#   docker run -p 9046:9046 quad-fighter-server
#
# Or with docker-compose:
#   docker-compose up

FROM python:3.11-slim

LABEL maintainer="Quad Fighter"
LABEL description="Headless authoritative game server for Quad Fighter"

WORKDIR /app

# Only the server and version file are needed – no pygame, no display
COPY server.py version.py ./

# No external dependencies required for the server (uses stdlib only)

ENV QUAD_SERVER_HOST=0.0.0.0
ENV QUAD_SERVER_PORT=9046
ENV QUAD_MAX_PLAYERS=4
ENV QUAD_TICK_RATE=30

EXPOSE 9046

CMD ["python", "-u", "server.py"]
