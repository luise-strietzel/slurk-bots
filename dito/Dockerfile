FROM python:3.9

RUN mkdir -p /usr/src/dito
WORKDIR /usr/src/dito

COPY requirements.txt /usr/src/dito
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /usr/src/dito

ENTRYPOINT ["python", "main.py"]
