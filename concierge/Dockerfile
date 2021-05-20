FROM python:3.9

RUN mkdir -p /usr/src/concierge
WORKDIR /usr/src/concierge

COPY requirements.txt /usr/src/concierge
RUN pip install --no-cache-dir -r requirements.txt

COPY ./ /usr/src/concierge

ENTRYPOINT ["python", "concierge.py"]
