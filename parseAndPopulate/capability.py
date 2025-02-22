# Copyright The IETF Trust 2019, All Rights Reserved
# Copyright 2018 Cisco and its affiliates
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
Capability class will parse all the capability.xml files
and pulls all the information from platfom-metadata.json file
if it exist or it will parse ietf-yang-library.xml file if such
file exists, or it will start to parse all the files that are
in the directory if there is none xml or json files mentioned above
and it will store them as sdos since we don t have any vendor
information about them
"""

__author__ = "Miroslav Kovac"
__copyright__ = "Copyright 2018 Cisco and its affiliates, Copyright The IETF Trust 2019, All Rights Reserved"
__license__ = "Apache License, Version 2.0"
__email__ = "miroslav.kovac@pantheon.tech"

import fileinput
import fnmatch
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET

import utility.log as log
from utility import repoutil
from parseAndPopulate.loadJsonFiles import LoadFiles
from parseAndPopulate.modules import Modules
from parseAndPopulate.parseException import ParseException

github_raw = 'https://raw.githubusercontent.com/'
github_url = 'https://github.com/'


# searching for file based on pattern or pattern_with_revision
def find_first_file(directory, pattern, pattern_with_revision):
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern_with_revision):
                filename = os.path.join(root, basename)
                return filename
    for root, dirs, files in os.walk(directory):
        for basename in files:
            if fnmatch.fnmatch(basename, pattern):
                filename = os.path.join(root, basename)
                return filename


class Capability:
    def __init__(self, log_directory, hello_message_file, index, prepare, integrity_checker,
                 api, sdo, json_dir, html_result_dir, save_file_to_dir, private_dir,
                 yang_models_dir, run_integrity=False):
        global LOGGER
        LOGGER = log.get_logger('capability', log_directory + '/parseAndPopulate.log')
        LOGGER.debug('Running constructor')
        self.logger = log.get_logger('repoutil', log_directory + '/parseAndPopulate.log')
        self.log_directory = log_directory
        self.run_integrity = run_integrity
        self.to = save_file_to_dir
        self.html_result_dir = html_result_dir
        self.json_dir = json_dir
        self.index = index
        self.prepare = prepare
        self.integrity_checker = integrity_checker
        self.parsed_yang = None
        self.api = api
        self.sdo = sdo
        self.yang_models_dir = yang_models_dir
        # Get hello message root
        if 'xml' in hello_message_file:
            try:
                LOGGER.debug('Checking for xml hello message file')
                self.root = ET.parse(hello_message_file).getroot()
            except:
                #try to change & to &amp
                hello_file = fileinput.FileInput(hello_message_file, inplace=True)
                for line in hello_file:
                    print(line.replace('&', '&amp;'), end='')
                hello_file.close()
                LOGGER.warning('Hello message file has & instead of &amp, automatically changing to &amp')
                self.root = ET.parse(hello_message_file).getroot()
        # Split it so we can get vendor, os-type, os-version
        self.split = hello_message_file.split('/')
        self.hello_message_file = hello_message_file

        if self.api and not self.sdo:
            self.platform_data = []
            json_file = open(hello_message_file.split('.xml')[0] + '.json')
            impl = json.load(json_file)
            self.initialize(impl)
            json_file.close()

        if not self.api and not self.sdo:
            if os.path.isfile('/'.join(self.split[:-1]) + '/platform-metadata.json'):
                self.platform_data = []
                json_file = open('/'.join(self.split[:-1]) + '/platform-metadata.json')
                platforms = json.load(json_file)['platforms']['platform']
                for impl in platforms:
                    self.initialize(impl)
                json_file.close()
            else:
                self.platform_data = []
                LOGGER.debug('Setting metadata concerning whole directory')
                self.owner = 'YangModels'
                self.repo = 'yang'
                repo = repoutil.RepoUtil('{}{}/{}'.format(github_url, self.owner, self.repo), self.logger)
                repo.clone()
                self.path = None
                self.branch = 'master'
                self.branch = repo.get_commit_hash(self.branch)
                repo.remove()
                self.feature_set = 'ALL'
                self.software_version = self.split[5]
                self.vendor = self.split[3]
                # Solve for os-type
                if 'nx' in self.split[4]:
                    self.os = 'NX-OS'
                    self.platform = self.split[6].split('-')[0]
                elif 'xe' in self.split[4]:
                    self.os = 'IOS-XE'
                    self.platform = self.split[6].split('-')[0]
                elif 'xr' in self.split[4]:
                    self.os = 'IOS-XR'
                    self.platform = self.split[6].split('-')[1]
                else:
                    self.os = 'Unknown'
                    self.platform = 'Unknown'
                self.os_version = self.split[5]
                self.software_flavor = 'ALL'
                self.platform_data.append(
                    {'software-flavor': self.software_flavor,
                     'platform': self.platform})
            integrity_checker.add_platform('/'.join(self.split[:-2]), self.platform)

        self.parsed_jsons = None
        if not run_integrity:
            self.parsed_jsons = LoadFiles(private_dir, log_directory)

    def initialize(self, impl):
        if impl['module-list-file']['path'] in self.hello_message_file:
            LOGGER.info('Parsing a received json file')
            self.feature_set = 'ALL'
            self.os_version = impl['software-version']
            self.software_flavor = impl['software-flavor']
            self.vendor = impl['vendor']
            self.platform = impl['name']
            self.os = impl['os-type']
            self.software_version = impl['software-version']
            self.owner = impl['module-list-file']['owner']
            self.repo = impl['module-list-file']['repository'].split('.')[0]
            self.path = impl['module-list-file']['path']
            self.branch = impl['module-list-file'].get('branch')
            repo = repoutil.RepoUtil('{}{}/{}'.format(github_url, self.owner, self.repo), self.logger)
            repo.clone()
            if not self.branch:
                self.branch = 'master'
            self.branch = repo.get_commit_hash(self.branch)
            repo.remove()
            self.platform_data.append({'software-flavor': self.software_flavor,
                                       'platform': self.platform})

    def parse_and_dump_sdo(self):
        repo = None
        if self.api:
            LOGGER.debug('Parsing sdo files sent via API')
            with open(self.json_dir + '/prepare-sdo.json', 'r') as f:
                sdos_json = json.load(f)
            sdos_list = sdos_json['modules']['module']
            for sdo in sdos_list:
                file_name = unicodedata.normalize('NFKD', sdo['source-file']['path'].split('/')[-1]) \
                    .encode('ascii', 'ignore')
                LOGGER.info('Parsing sdo file sent via API{}'.format(file_name))
                self.owner = sdo['source-file']['owner']
                repo_file_path = sdo['source-file']['path']
                self.repo = sdo['source-file']['repository'].split('.')[0]
                if repo is None:
                    repo = repoutil.RepoUtil('{}{}/{}'.format(github_url, self.owner, self.repo), self.logger)
                    repo.clone()
                self.branch = sdo['source-file'].get('branch')
                if not self.branch:
                    self.branch = 'master'
                self.branch = repo.get_commit_hash('/'.join(repo_file_path.split('/')[:-1]), self.branch)
                root = self.owner + '/' + sdo['source-file']['repository'].split('.')[0] + '/' + self.branch + '/' \
                       + '/'.join(repo_file_path.split('/')[:-1])
                root = self.json_dir + '/temp/' + root
                if sys.version_info < (3, 4):
                    root = self.json_dir + '/temp/' \
                           + unicodedata.normalize('NFKD', root).encode('ascii', 'ignore')
                if sys.version_info >= (3, 4):
                    file_name = file_name.decode('utf-8', 'strict')
                if not os.path.isfile(root + '/' + file_name):
                    LOGGER.error('File {} sent via API was not downloaded'.format(file_name))
                    continue
                if '[1]' not in file_name:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory, root + '/' + file_name,
                                       self.html_result_dir, self.parsed_jsons, self.json_dir)
                    except ParseException as e:
                        LOGGER.error(e.msg)
                        continue
                    name = file_name.split('.')[0].split('@')[0]
                    schema = github_raw + self.owner + '/' + self.repo + '/' + self.branch + '/' + repo_file_path
                    yang.parse_all(self.branch, name,
                                   self.prepare.name_revision_organization,
                                   schema, self.to, sdo)
                    self.prepare.add_key_sdo_module(yang)

        else:
            LOGGER.debug('Parsing sdo files from directory')
            for root, subdirs, sdos in os.walk('/'.join(self.split)):
                for file_name in sdos:
                    if '.yang' in file_name and ('vendor' not in root or 'odp' not in root):
                        LOGGER.info('Parsing sdo file from directory {}'.format(file_name))

                        if '[1]' in file_name:
                            LOGGER.warning('File {} contains [1] it its file name'.format(file_name))
                        else:
                            try:
                                yang = Modules(self.yang_models_dir, self.log_directory, root + '/' + file_name,
                                               self.html_result_dir, self.parsed_jsons, self.json_dir)
                            except ParseException as e:
                                LOGGER.error(e.msg)
                                continue
                            name = file_name.split('.')[0].split('@')[0]
                            self.owner = 'YangModels'
                            self.repo = 'yang'
                            if repo is None:
                                repo = repoutil.RepoUtil('{}{}/{}'.format(github_url, self.owner, self.repo), self.logger)
                                repo.clone()
                            self.branch = 'master'
                            path = root + '/' + file_name
                            abs_path = os.path.abspath(path)
                            if '/yangmodels/yang/' in abs_path:
                                path = abs_path.split('/yangmodels/yang/')[1]
                            else:
                                path = re.split('tmp\/\w*\/', abs_path)[1]
                            self.branch = repo.get_commit_hash(path, self.branch)
                            schema = (github_raw + self.owner + '/' + self.repo
                                      + '/' + self.branch + '/' + path)
                            yang.parse_all(self.branch, name,
                                           self.prepare.name_revision_organization,
                                           schema, self.to)
                            self.prepare.add_key_sdo_module(yang)
        repo.remove()

    # parse capability xml and save to file
    def parse_and_dump_yang_lib(self):
        LOGGER.debug('Starting to parse files from vendor')
        capabilities = []
        netconf_version = []
        LOGGER.debug('Getting capabilities out of api message')
        if self.api:
            with open(self.hello_message_file.split('.xml')[0] + '.json') as f:
                impl = json.load(f)
            caps = impl['platforms'].get('netconf-capabilities')
            if caps:
                for cap in caps:
                    capability = cap
                    # Parse netconf version
                    if ':netconf:base:' in capability:
                        netconf_version.append(capability)
                        LOGGER.debug('Getting netconf version')
                    # Parse capability together with version
                    elif ':capability:' in capability:
                        cap_with_version = capability
                        capabilities.append(cap_with_version.split('?')[0])
        else:
            if os.path.isfile('/'.join(self.split[:-1]) + '/platform-metadata.json'):
                json_file = open('/'.join(self.split[:-1]) + '/platform-metadata.json')
                platforms = json.load(json_file)['platforms']['platform']
                for impl in platforms:
                    if impl['module-list-file']['path'] in self.hello_message_file:
                        caps = impl.get('netconf-capabilities')
                        if caps:
                            for cap in caps:
                                capability = cap
                                # Parse netconf version
                                if ':netconf:base:' in capability:
                                    netconf_version.append(capability)
                                    LOGGER.debug('Getting netconf version')
                                # Parse capability together with version
                                elif ':capability:' in capability:
                                    cap_with_version = capability
                                    capabilities.append(
                                        cap_with_version.split('?')[0])
                json_file.close()

        # netconf capability parsing
        modules = self.root[0]
        set_of_names = set()
        keys = set()
        schema_part = github_raw + self.owner + '/' + self.repo + '/' + self.branch + '/'
        for module in modules:
            if 'module-set-id' in module.tag:
                continue
            LOGGER.debug('Getting capabilities out of yang-library xml message')
            module_name = None

            for mod in module:
                if 'name' in mod.tag:
                    module_name = mod.text
                    break

            yang_lib_info = {}
            yang_lib_info['path'] = '/'.join(self.split[0:-1])
            yang_lib_info['name'] = module_name
            yang_lib_info['features'] = []
            yang_lib_info['deviations'] = {}
            names = []
            revs = []
            conformance_type = None
            for mod in module:
                if 'revision' in mod.tag:
                    yang_lib_info['revision'] = mod.text
                elif 'conformance-type' in mod.tag:
                    conformance_type = mod.text
                elif 'feature' in mod.tag:
                    yang_lib_info['features'].append(mod.text)
                elif 'deviation' in mod.tag:
                    names.append(mod[0].text)
                    revs.append(mod[1].text)
            yang_lib_info['deviations']['name'] = names
            yang_lib_info['deviations']['revision'] = revs

            try:
                try:
                    yang = Modules(self.yang_models_dir, self.log_directory,
                               '/'.join(self.split), self.html_result_dir,
                               self.parsed_jsons, self.json_dir, True, True,
                               yang_lib_info, run_integrity=self.run_integrity)
                except ParseException as e:
                    LOGGER.error(e.msg)
                    continue

                yang.parse_all(self.branch, module_name,
                               self.prepare.name_revision_organization,
                               schema_part, self.to)
                yang.add_vendor_information(self.vendor, self.platform_data,
                                            self.software_version,
                                            self.os_version, self.feature_set,
                                            self.os, conformance_type,
                                            capabilities, netconf_version,
                                            self.integrity_checker,
                                            self.split)
                if self.run_integrity:
                    yang.resolve_integrity(self.integrity_checker, self.split,
                                           self.os_version)
                self.prepare.add_key_sdo_module(yang)
                keys.add('{}@{}/{}'.format(yang.name, yang.revision,
                                           yang.organization))
                set_of_names.add(yang.name)
            except FileNotFoundError:

                self.integrity_checker.add_module('/'.join(self.split),
                                                  [module_name])
                LOGGER.warning('File {} not found in the repository'
                               .format(module_name))

            LOGGER.info('Starting to parse {}'.format(module_name))

        for key in keys:
            self.parse_imp_inc(self.prepare.yang_modules[key].submodule,
                               set_of_names, True, schema_part, capabilities,
                               netconf_version)
            self.parse_imp_inc(self.prepare.yang_modules[key].imports,
                               set_of_names, False, schema_part, capabilities,
                               netconf_version)

    # parse capability xml and save to file
    def parse_and_dump(self):
        LOGGER.debug('Starting to parse files from vendor')
        capabilities = []
        tag = self.root.tag
        netconf_version = []

        # netconf capability parsing
        modules = self.root.iter(tag.split('hello')[0] + 'capability')
        set_of_names = set()
        keys = set()
        capabilities_exist = False
        LOGGER.debug('Getting capabilities out of hello message')
        if os.path.isfile(
                        '/'.join(self.split[:-1]) + '/platform-metadata.json'):
            json_file = open(
                '/'.join(self.split[:-1]) + '/platform-metadata.json')
            platforms = json.load(json_file)['platforms']['platform']
            for impl in platforms:
                if impl['module-list-file']['path'] in self.hello_message_file:
                    caps = impl.get('netconf-capabilities')
                    if caps:
                        capabilities_exist = True
                        for cap in caps:
                            capability = cap
                            # Parse netconf version
                            if ':netconf:base:' in capability:
                                netconf_version.append(capability)
                                LOGGER.debug('Getting netconf version')
                            # Parse capability together with version
                            elif ':capability:' in capability:
                                cap_with_version = capability
                                capabilities.append(
                                    cap_with_version.split('?')[0])
            json_file.close()
        LOGGER.debug('Getting capabilities out of hello message')
        if not capabilities_exist:
            for module in modules:
                # Parse netconf version
                if ':netconf:base:' in module.text:
                    netconf_version.append(module.text)
                    LOGGER.debug('Getting netconf version')
                # Parse capability together with version
                if ':capability:' in module.text:
                    cap_with_version = module.text.split(':capability:')[1]
                    capabilities.append(cap_with_version.split('?')[0])
            modules = self.root.iter(tag.split('hello')[0] + 'capability')

        schema_part = github_raw + self.owner + '/' + self.repo + '/' +\
                      self.branch + '/'
        # Parse modules
        for module in modules:
            if 'module=' in module.text:
                # Parse name of the module
                module_and_more = module.text.split('module=')[1]
                module_name = module_and_more.split('&')[0]
                LOGGER.info('Parsing module {}'.format(module_name))
                try:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory, '/'.join(self.split),
                                       self.html_result_dir, self.parsed_jsons,
                                       self.json_dir, True, data=module_and_more,
                                       run_integrity=self.run_integrity)
                    except ParseException as e:
                        LOGGER.error(e.msg)
                        continue
                    yang.parse_all(self.branch, module_name,
                                   self.prepare.name_revision_organization,
                                   schema_part, self.to)
                    yang.add_vendor_information(self.vendor, self.platform_data,
                                                self.software_version,
                                                self.os_version,
                                                self.feature_set,
                                                self.os, 'implement',
                                                capabilities,
                                                netconf_version,
                                                self.integrity_checker,
                                                self.split)
                    if self.run_integrity:
                        yang.resolve_integrity(self.integrity_checker,
                                               self.split, self.os_version)
                    self.prepare.add_key_sdo_module(yang)
                    key = '{}@{}/{}'.format(yang.name, yang.revision,
                                            yang.organization)
                    keys.add(key)
                    set_of_names.add(yang.name)
                except FileNotFoundError:
                    self.integrity_checker.add_module('/'.join(self.split),
                                                      [module_and_more.split(
                                                          '&')[0]])
                    LOGGER.warning('File {} not found in the repository'
                                   .format(module_name))

        for key in keys:
            self.parse_imp_inc(self.prepare.yang_modules[key].submodule,
                               set_of_names, True, schema_part, capabilities,
                               netconf_version)
            self.parse_imp_inc(self.prepare.yang_modules[key].imports,
                               set_of_names, False, schema_part, capabilities,
                               netconf_version)

    def parse_imp_inc(self, modules, set_of_names, is_include, schema_part,
                      capabilities, netconf_version):
        for mod in modules:
            if is_include:
                name = mod.name
                conformance_type = 'import'
            else:
                conformance_type = None
                name = mod.arg
            if name not in set_of_names:
                LOGGER.info('Parsing module {}'.format(name))
                set_of_names.add(name)
                yang_file = find_first_file('/'.join(self.split[0: -1]),
                                            name + '.yang', name + '@*.yang')
                if yang_file is None:
                    yang_file = find_first_file(self.yang_models_dir, name + '.yang',
                                                name + '@*.yang')
                if yang_file is None:
                    # TODO add integrity that this file is missing
                    return
                try:
                    try:
                        yang = Modules(self.yang_models_dir, self.log_directory,
                                       yang_file, self.html_result_dir,
                                       self.parsed_jsons, self.json_dir,
                                       is_vendor_imp_inc=True,
                                       run_integrity=self.run_integrity)
                    except ParseException as e:
                        LOGGER.error(e.msg)
                        continue
                    yang.parse_all(self.branch, name,
                                   self.prepare.name_revision_organization,
                                   schema_part, self.to)
                    yang.add_vendor_information(self.vendor, self.platform_data,
                                                self.software_version,
                                                self.os_version,
                                                self.feature_set, self.os,
                                                conformance_type, capabilities,
                                                netconf_version,
                                                self.integrity_checker,
                                                self.split)
                    if self.run_integrity:
                        yang.resolve_integrity(self.integrity_checker,
                                               self.split, self.os_version)
                    self.prepare.add_key_sdo_module(yang)
                    self.parse_imp_inc(yang.submodule, set_of_names, True,
                                       schema_part, capabilities, netconf_version)
                    self.parse_imp_inc(yang.imports, set_of_names, False,
                                       schema_part, capabilities, netconf_version)
                except FileNotFoundError:
                    self.integrity_checker.add_module('/'.join(self.split),
                                                      [name])
                    LOGGER.warning('File {} not found in the repository'
                                   .format(name))
