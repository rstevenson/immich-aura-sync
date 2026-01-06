FROM python:3.11-alpine

WORKDIR /app

# Copy and install sync service requirements FIRST
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy auraframes and install its requirements
COPY auraframes/ ./auraframes/
RUN pip install --no-cache-dir -r ./auraframes/requirements.txt

# Copy application code
COPY src/ ./src/
COPY config.example.yml .

CMD ["python", "src/main.py"]
