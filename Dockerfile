FROM python:3.13-slim
WORKDIR /app
COPY app.py .
EXPOSE 8000
# Domyslnie tryb podatny. Tryb bezpieczny: -e SECURE=1
ENV SECURE=0
CMD ["python", "app.py"]
