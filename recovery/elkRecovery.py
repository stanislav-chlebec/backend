# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2019 Cisco and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
This script will save or load all the records saved in
Elasticsearch database
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import argparse
import datetime
import sys
from operator import itemgetter

from elasticsearch import Elasticsearch

if sys.version_info >= (3, 4):
    import configparser as ConfigParser
else:
    import ConfigParser


def create_register_elk_repo(name, is_compress, elk):
    body = {}
    body['type'] = 'fs'
    body['settings'] = {}
    body['settings']['location'] = name
    body['settings']['compress'] = is_compress
    elk.snapshot.create_repository(name, body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This serves to save or load all information in yangcatalog.org in elk.'
                    'in case the server will go down and we would lose all the information we'
                    ' have got. We have two options in here.')
    parser.add_argument('--name_save', default=str(datetime.datetime.utcnow()).split('.')[0].replace(' ', '_').replace(':', '-') + '-utc',
                        type=str, help='Set name of the file to save. Default name is date and time in UTC')
    parser.add_argument('--name_load', type=str,
                        help='Set name of the file to load. Default will take a last saved file')
    parser.add_argument('--save', action='store_true', default=True,
                        help='Set weather you want to create snapshot. Default is True')
    parser.add_argument('--load', action='store_true', default=False,
                        help='Set weather you want to load from snapshot. Default is False')
    parser.add_argument('--latest', action='store_true', default=True,
                        help='Set weather to load the latest snapshot')
    parser.add_argument('--compress', action='store_true', default=True,
                        help='Set weather to compress snapshot files. Default is True')
    parser.add_argument('--config-path', type=str, default='/etc/yangcatalog/yangcatalog.conf',
                        help='Set path to config file')

    args = parser.parse_args()
    config_path = args.config_path
    config = ConfigParser.ConfigParser()
    config._interpolation = ConfigParser.ExtendedInterpolation()
    config.read(config_path)
    cache_directory = config.get('Directory-Section', 'cache')
    credentials = config.get('General-Section', 'credentials').split(' ')
    repo_name = config.get('General-Section', 'elk-repo-name')

    es_host = config.get('DB-Section', 'es-host')
    es_port = config.get('DB-Section', 'es-port')
    es = Elasticsearch([{'host': '{}'.format(es_host), 'port': es_port}])
    save = args.save
    if args.load:
        save = False

    if save:
        create_register_elk_repo(repo_name, args.compress, es)
        index_body = {
            'indices': '_all'
        }
        es.snapshot.create(repository=repo_name, snapshot=args.name_save, body=index_body)
    else:
        create_register_elk_repo(repo_name, args.compress, es)
        index_body = {
            'indices': '_all'
        }
        if args.latest:
            snapshots = es.snapshot.get(repository=repo_name, snapshot='_all')['snapshots']
            sorted_snapshots = sorted(snapshots, key=itemgetter('start_time_in_millis'))
            es.snapshot.restore(repository=repo_name, snapshot=sorted_snapshots[-1]['snapshot'], body=index_body)
        else:
            es.snapshot.restore(repository=repo_name, snapshot=args.name_load, body=index_body)

