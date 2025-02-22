FROM python:3
ARG YANG_ID_GID

ENV YANG_ID_GID "$YANG_ID_GID"
ENV LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONUNBUFFERED=1

ENV VIRTUAL_ENV=/backend

#Install Cron
RUN apt-get update
RUN apt-get -y install cron \
  && apt-get autoremove -y

RUN groupadd -g ${YANG_ID_GID} -r yang \
  && useradd --no-log-init -r -g yang -u ${YANG_ID_GID} -d $VIRTUAL_ENV yang \
  && pip install virtualenv \
  && virtualenv --system-site-packages $VIRTUAL_ENV \
  && mkdir -p \
   #    /var/yang/tmp /var/yang/logs \
   #    /var/yang/cache /var/yang/backup \
   #    /var/yang/all_modules \
   #    /var/yang/requests \
   #    /var/yang/commit_dir \
   #    /var/yang/ytrees \
   #    /var/yang/nonietf/yangmodels/yang \
        /etc/yangcatalog
 # && chown -R yang:yang /var/yang
COPY . $VIRTUAL_ENV

ENV PYTHONPATH=$VIRTUAL_ENV/bin/python
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV GIT_PYTHON_GIT_EXECUTABLE=/usr/bin/git

WORKDIR $VIRTUAL_ENV

RUN pip install -r requirements.txt \
  && ./setup.py install

ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV UWSGI_PROCS=1
ENV UWSGI_THREADS=20

# Add crontab file in the cron directory
COPY crontab /etc/cron.d/yang-cron

RUN chown yang:yang /etc/cron.d/yang-cron
RUN chown -R yang:yang $VIRTUAL_ENV
USER ${YANG_ID_GID}:${YANG_ID_GID}

# Apply cron job
RUN crontab /etc/cron.d/yang-cron
WORKDIR $VIRTUAL_ENV/api

CMD exec uwsgi -s :3031 --plugins python3 --protocol uwsgi \
  -H $VIRTUAL_ENV \
  --cache2 name=main_cache1,items=3000 \
  --cache2 name=main_cache2,items=3000 \
  --cache2 name=cache_modules1,items=10000,blocksize=20100 \
  --cache2 name=cache_modules2,items=10000,blocksize=20100 \
  --cache2 name=cache_chunks1,items=10000,blocksize=100 \
  --cache2 name=cache_chunks2,items=10000,blocksize=100 \
  --processes $UWSGI_PROCS --threads $UWSGI_THREADS \
  --wsgi api.wsgi --need-app

EXPOSE 3031
