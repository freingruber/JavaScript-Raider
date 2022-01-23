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


import subprocess

if True:
    print("Going to query status of all instances...")
    result = subprocess.run(['gcloud', 'compute', 'instances', 'list'], stdout=subprocess.PIPE)
    tmp = result.stdout.decode('utf-8')
    for line in tmp.split("\n"):
        if "RUNNING" in line:
            parts = line.split()
            instance_name = parts[0]
            instance_zone = parts[1]
            if instance_name == "developer-system":
                continue    # skip my developer machine
            print("Going to stop %s (zone: %s)" % (instance_name, instance_zone))

            stop_result = subprocess.run(['gcloud', 'compute', 'instances', 'stop', instance_name, '--zone', instance_zone, '--quiet'], stdout=subprocess.PIPE)
            print("Result:")
            print(stop_result.stdout.decode('utf-8'))
