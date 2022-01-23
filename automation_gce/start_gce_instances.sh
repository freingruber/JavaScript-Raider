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


# Note: you can just create 6 machines every 60 minutes (from a snapshot) according to:
# https://cloud.google.com/compute/docs/disks/snapshot-best-practices
# Otherwise you get the error:
# Operation rate exceeded for resource [...]. Too frequent operations from the source resource.

# But you can create multiple snapshots from your base-fuzzer image and then start from
# multiple snapshots.
# Also note that you need to increase your quota if you want to start multiple fuzzer instances!
# This especially applies to the CPU quota and number of IP-Addresses quota.


PROJECT_NAME="your-project-name-goes-here"

BASE_NAME="fuzzer-europe-west1-"
ZONE=europe-west1-b

# The name of the snapshot you created from your base fuzzer image
# This base image should have the fuzzer stored on the file system and all required dependencies installed
# It's recommended to first test that the fuzzer can run successfully on this system for several hours
# Be aware that you must create OUTPUT folders for each fuzzing instance in the base image
# for details read the comments in >start_fuzzing_16.sh<
SNAPSHOT_BASEIMAGE_NAME="fuzzer-baseimage-3-08-2021_one"

SERVICE_ACCOUNT=123456789-compute@developer.gserviceaccount.com

# Be aware that the disk size also influences the number of free inodes
# The fuzzer stores a lot of small files, it's therefore typically enough to use
# 15 GB of disk space to store the OS, the fuzzer and all corpus files.
# You could then have something like ~5GB of free space, but no inodes and results can't be saved.
# It's therefore important to use a big enough disk space to have enough free inodes!
FUZZER_DISK_SIZE="45"

MACHINE_TYPE=e2-standard-16

# Startup and shutdown script paths are local paths from the systems on which you
# execute this script (and not paths from GCE instances)
# The startup script will start a watchdog and several fuzzer instances on the machine
# E.g. on a 16-core system (Machine type e2-standard-16) you should start 16 fuzzing jobs
# The startup script will do this
# The stop script tries to save results to GCE buckets in case the machine gets preempted.
# However, this often doesn't work because it's not guaranteed that the stop script gets executed
STARTUP_SCRIPT_LOCAL_PATH="/home/user/Desktop/fuzzer/automation_gce/start_fuzzing_16.sh"
SHUTDOWN_SCRIPT_LOCAL_PATH="/home/user/Desktop/fuzzer/automation_gce/shutdown_fuzzing_16.sh"

START_ID=1
NUMBER_INSTANCES_TO_START=50
CURRENT_COUNTER=0

read -p "Going to start $NUMBER_INSTANCES_TO_START instance(s). Are you sure (y/n)?" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
	END_ID=$(( $START_ID + $NUMBER_INSTANCES_TO_START ))

	for (( current_id=$START_ID; current_id<$END_ID; current_id++ ))
	do
		CURRENT_COUNTER=$(( $CURRENT_COUNTER + 1 ))
		if (( $CURRENT_COUNTER > 5 )); then
			CURRENT_COUNTER=$((0))
			echo "Going to sleep for 65 minutes..."
			sleep 3900	# sleep 65 minutes
			echo "After sleep!"
		fi
	
		CURRENT_NAME=$BASE_NAME$current_id
		echo "Going to start $CURRENT_NAME..."
		
		gcloud compute --project $PROJECT_NAME disks create $CURRENT_NAME --size $FUZZER_DISK_SIZE --zone $ZONE --source-snapshot $SNAPSHOT_BASEIMAGE_NAME --type "pd-balanced"
		
		gcloud beta compute --project=$PROJECT_NAME instances create $CURRENT_NAME --zone=$ZONE --machine-type=$MACHINE_TYPE --subnet=default --network-tier=PREMIUM --no-restart-on-failure --maintenance-policy=TERMINATE --preemptible --service-account=$SERVICE_ACCOUNT --scopes=https://www.googleapis.com/auth/devstorage.read_only,https://www.googleapis.com/auth/logging.write,https://www.googleapis.com/auth/monitoring.write,https://www.googleapis.com/auth/servicecontrol,https://www.googleapis.com/auth/service.management.readonly,https://www.googleapis.com/auth/trace.append --disk=name=$CURRENT_NAME,device-name=$CURRENT_NAME,mode=rw,boot=yes,auto-delete=yes --reservation-affinity=any --metadata-from-file=startup-script=$STARTUP_SCRIPT_LOCAL_PATH,shutdown-script=$SHUTDOWN_SCRIPT_LOCAL_PATH
	done
fi