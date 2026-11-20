FROM docker.io/library/python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY skills/ ./skills/

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/app/output \
    HOST=0.0.0.0 \
    PORT=7860

EXPOSE 7860
VOLUME ["/app/output"]

CMD ["python", "-m", "texture_agent"]
