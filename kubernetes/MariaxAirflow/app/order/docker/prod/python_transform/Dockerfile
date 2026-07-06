FROM python:3.8-slim

WORKDIR /app

COPY ./main.py ./main.py

COPY ./requirements.txt ./requirements.txt

RUN mkdir -p data/to_ingest

RUN pip install -r requirements.txt
