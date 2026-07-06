FROM python:3.8-slim

RUN apt-get update -y && apt-get install -y libpq-dev gcc

WORKDIR /app

RUN mkdir -p data/to_ingest/silver

COPY ./main.py ./main.py
COPY ./main.1.py ./main.1.py

COPY ./requirements.txt ./requirements.txt

RUN pip install -r requirements.txt
