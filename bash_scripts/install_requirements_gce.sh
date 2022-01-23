#!/bin/bash

# Copyright 2022 @ReneFreingruber
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

apt install python3
apt install python3-pip
apt install expect
apt install python-dev libxml2-dev libxslt-dev    # Maybe instead requires libxslt1-dev
pip3 install progressbar
pip3 install hexdump
pip3 install unidecode
pip3 install bitstring
pip3 install --upgrade google-api-python-client   # used for synchronization via GCE buckets
pip3 install --upgrade google-cloud-storage       # used for synchronization via GCE buckets
pip3 install line_profiler      # only used for debugging / finding performance bottlenecks
pip3 install psutil
pip3 install paramiko           # used by the "create initial corpus" scripts
pip3 install scrapy             # used by the "create initial corpus" scripts
pip3 install gitpython          # used by the "create initial corpus" scripts
