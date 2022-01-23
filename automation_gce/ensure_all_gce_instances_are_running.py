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


# This script will check all 30 minutes if instances were preempted / stopped
# and will try to restart them
# In general, I would not recommend doing this. It's more efficient to start all preemptive instances
# and wait 1 day until all systems are stopped again. And then restart all systems.
# However, I didn't had so much time left, so I had to force restarts all 30 minutes
# (to spend all my GCE credits before they expired)

import subprocess
import time

project_name = "your-gce-project-name"

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
            print("Going to start %s (zone: %s)" % (instance_name, instance_zone))
            start_result = subprocess.run(['gcloud', 'beta', 'compute', 'instances', 'start', '--zone', '%s' % instance_zone, '%s' % instance_name, '--project', project_name], stdout=subprocess.PIPE)
            print("Start result:")
            print(start_result.stdout.decode('utf-8'))
            
    print("Going to sleep 0.5 hour...")
    time.sleep(1800)   # Check all 30 minutes; 3600....delay 1 hour
