FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN apt-get update && apt-get install -y cmake libgl1 && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 5000
ENV FLASK_APP=appy.py
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "appy:app"]
