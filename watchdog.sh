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



# This script is used to restart the fuzzer in case an exception occurs
# Typically the fuzzer should not throw exceptions, but if it really throws one,
# it just restarts fuzzing
# To enable or disable coverage, the command line must be updated

if [ "$#" -ne 1 ]
then
  echo "Output argument is missing!"
  exit 1
fi


cd /home/gce_user/fuzzer    # Replace this with the correct fuzzer path on the GCE instance

while true
do
	python3 JS_FUZZER.py --output_dir $1 --resume --disable_coverage
	sleep 1
done

