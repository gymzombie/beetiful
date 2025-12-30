FROM python:3.11.14

WORKDIR /usr/src/app

EXPOSE 3000

COPY . .

RUN pip install --no-cache-dir . && pip install beets==2.5.1

CMD [ "waitress-serve", "--port=3000", "beetiful:app" ]

