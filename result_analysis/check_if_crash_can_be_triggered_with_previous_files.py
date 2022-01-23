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



# I store per crash also previously executed in-memory files
# It can happen that a testcase crashes but the crash can't be reproduced because
# one of the previously executed testcases changed a global state, which then lead to the crash
# In most cases (like ~99% of crashes), the crash can be reproduced without the "previous_files".
# For the others, I use this script to analyze the crash
# The script basically just executes all previous files and then the crashing
# to detect if the crash can be reproduced using this way.
# In my analysis all such crashes were crap. So I think it's not really required to do this analysis.


import os
import sys
sys.path.append("..")
from native_code.executor import Executor, Execution_Status
import hashlib
import re
import subprocess


d8_path = "/home/user/Desktop/fuzzer/Target_v8/v8_aug_2021_without_coverage/d8"
input_path_previous_files = "/home/user/Desktop/fuzzer_data/ssh_downloaded_files/fuzzer-us-west1-64/OUTPUT10/crashes/53f4c2ac250ce6b10860a5524d54d300_previous/"

exec_engine = Executor(timeout_per_execution_in_ms=4000, enable_coverage=False, custom_path_d8=d8_path)
exec_engine.restart_engine()


# Test without "previous_files":
# result = exec_engine.execute_once(testcase1)
# print(result)

for i in range(1, 100):
    fullpath = os.path.join(input_path_previous_files, "%d.js" % i)
    # print(fullpath)
    if os.path.exists(fullpath) is False:
        continue
    with open(fullpath, "r") as fobj:
        content = fobj.read()

    result = exec_engine.execute_once(content)
    print(result)
    # if result.status == Execution_Status.CRASH:
    # stderr = result.engine_stderr
