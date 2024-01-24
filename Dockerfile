FROM python

RUN mkdir /app

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt

ENTRYPOINT python main.py