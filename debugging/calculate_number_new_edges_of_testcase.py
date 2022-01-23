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



import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

from native_code.executor import Executor, Execution_Status
import config as cfg



import os



testcase_dir = "/home/user/Desktop/input/OUTPUT/current_corpus"
testcase_filename = "tc1234.js"

fullpath = os.path.join(testcase_dir, testcase_filename)
with open(fullpath, "r") as fobj:
    content = fobj.read()


exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_max, enable_coverage=True)
exec_engine.adjust_coverage_with_dummy_executions()

result = exec_engine.execute_safe(content)

if result.status == Execution_Status.SUCCESS:
    print("Success, edge edges: %d" % result.num_new_edges)
elif result.status == Execution_Status.CRASH:
    print("Crash")
elif result.status == Execution_Status.EXCEPTION_THROWN:
    print("Exception")
elif result.status == Execution_Status.TIMEOUT:
    print("Timeout")
else:
    print("Unkown")
