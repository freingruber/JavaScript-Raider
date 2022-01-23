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



# I use this script sometimes when I statically modify JavaScript corpus files
# (e.g.: removing not executed code to manually minimize the file)
# This helps to verify that the modification was correct (e.g.: it doesn't lead to an exception in the code...)
#
# It's also useful when updating the JavaScript engine to ensure that all files from the corpus don't trigger
# an exception in the new JavaScript version.
#
# Example invocation:
# python3 check_if_all_files_dont_trigger_an_exception.py | tee output.log
# cat output.log | grep -v "SUCCESS:"


import os
import sys
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
from native_code.executor import Executor, Execution_Status


base_path = '/home/user/Desktop/input/OUTPUT/current_corpus/'   # input path

# Coverage is not required to check if an exception/crash occurs
exec_engine = Executor(timeout_per_execution_in_ms=5000, enable_coverage=False)
count = 0
for filename in os.listdir(base_path):
    if filename.endswith(".js"):
        fullpath = os.path.join(base_path, filename)
        with open(fullpath, "r") as fobj:
            content = fobj.read().strip()

        exec_engine.restart_engine()    # restart engine before every testcase so that testcases 100% don't affect each other
        result = exec_engine.execute_safe(content)
        if result.status != Execution_Status.SUCCESS:
            print("Failed with file: %s" % filename)
            print("Status: %s" % result.get_status_str())
        else:
            print("SUCCESS: %s" % filename)
            # pass
        count += 1
        if (count % 1000) == 0:
            print("Processed: %d files" % count)
        sys.stdout.flush()

print("Finished!")
