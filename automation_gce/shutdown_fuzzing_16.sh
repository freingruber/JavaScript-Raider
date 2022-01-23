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



# The content of this script must be saved in the "shutdown-script" meta information
# of a GCE machine (alternatively the >start_gce_instances.sh< script will pass it.
# => Then this script automatically executes when the instance is stopped (e.g. Google shuts down a preemptive machine)

# The purpose of the script is to gracefully shut down fuzzing. Typically, it should be no problem to just
# pull the plug because results (e.g. crashes or new behavior files) are always immediately uploaded to a bucket.
# However, I also want to sync the current stats / tagging results
# => This helps to get a better understanding of how many real fuzzing executions were performed
#
# Please note: It's not guaranteed that GCE really executes this script and it often was not executed.

# TODO:
# The script should maybe also be added to /etc/acpi/powerbtn.sh
# to ensure that it's really everytime called, see: https://haggainuchi.com/shutdown.html

# Step1: Kill all watchdogs (otherwise they would respawn the fuzzers)
pkill -f watchdog.sh

# Step2: Kill all fuzzer instances
let all_pids=$(pgrep -i -f JS_FUZZER.py);
for pid in $all_pids; do
    kill -2 $pid
done

# Step3: Wait until they are all stopped
for pid in $all_pids; do
	while kill -0 $pid; do
	   sleep 1
	done
done

echo "Finished!"
sleep 15
