FROM python:3.11.14

WORKDIR /usr/src/app

EXPOSE 3000

COPY . .

RUN pip install --no-cache-dir . && pip install beets==2.5.1

# Run as a non-root user so files the app creates in the mounted config dir
# (the beets config and library.db) are not owned by root on the host. UID/GID
# default to 1000 to match a typical host user; if yours differ, override with
# the compose `user:` directive or chown the mounted volume to match.
RUN groupadd --gid 1000 beetiful \
    && useradd --uid 1000 --gid 1000 --create-home beetiful
USER beetiful

CMD [ "waitress-serve", "--port=3000", "beetiful:app" ]
