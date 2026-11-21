FROM docker.io/library/python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 預先下載 Chroma 預設的 embedding 模型（all-MiniLM-L6-v2），執行時就不用連網
RUN python -c "from chromadb.utils.embedding_functions import DefaultEmbeddingFunction as D; D()(['warmup'])"

COPY src/ ./src/
COPY skills/ ./skills/

ENV PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    OUTPUT_DIR=/app/output \
    REFERENCE_DIR=/app/reference \
    INDEX_DIR=/app/index \
    DATA_DIR=/app/data \
    HOST=0.0.0.0 \
    PORT=7860

EXPOSE 7860
VOLUME ["/app/output", "/app/reference", "/app/index", "/app/data"]

CMD ["python", "-m", "texture_agent"]
