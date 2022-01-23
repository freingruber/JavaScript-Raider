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


# I think there is a python integration for gcloud, but for the moment I'm just wrapping OS commands...

# The script will remove all old fuzzer instances in a loop all 30 minutes.
# This will DELETE ALL FILES on the instance - so make sure you already synchronized them (e.g.: to a GCE Bucket)!
# Hint: Check afterwards if really all associated disks were removed!
# TODO: Maybe I need the "--delete-disks all" flag?
# But I think I correctly set the "auto delete disk" flag when creating the instances?
# It seems like GCE is just ignoring them sometimes (?)

import subprocess
import time


while True:
    print("Going to query status of all instances...")
    result = subprocess.run(['gcloud', 'compute', 'instances', 'list'], stdout=subprocess.PIPE)
    tmp = result.stdout.decode('utf-8')
    for line in tmp.split("\n"):
        if "TERMINATED" in line:
            parts = line.split()
            instance_name = parts[0]
            instance_zone = parts[1]
            if instance_name == "developer-system":
                continue    # skip my developer machine
            print("Going to delete %s (zone: %s)" % (instance_name, instance_zone))

            remove_result = subprocess.run(['gcloud', 'compute', 'instances', 'delete', instance_name, '--zone', instance_zone, '--quiet'], stdout=subprocess.PIPE)
            print("Result:")
            print(remove_result.stdout.decode('utf-8'))

    print("Going to sleep 0.5 hour...")
    time.sleep(1800)        # Check all 30 minutes; 3600....delay 1 hour

