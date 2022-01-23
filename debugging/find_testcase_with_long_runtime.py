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



# This script searches for testcases with a long runtime.
# I use this to detect slow testcases to try to further optimize the minimizer to
# also reduce the runtime of testcases


import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import testcase_state


max_runtime = 500

testcase_dir = "/home/user/Desktop/input/OUTPUT/current_corpus/"

for filename in os.listdir(testcase_dir):
    if filename.endswith("pickle"):
        continue
    if filename.endswith(".js") is False:
        continue

    filepath = os.path.join(testcase_dir, filename)
    with open(filepath, 'r') as fobj:
        content = fobj.read().rstrip()

    state_filepath = filepath + ".pickle"
    state = testcase_state.load_state(state_filepath)
    
    if state.runtime_length_in_ms > max_runtime:
        print("%s has a runtime of %d ms" % (filename, state.runtime_length_in_ms))
