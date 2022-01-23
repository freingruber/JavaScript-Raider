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



# This is just a small helper utility which loads a state of a testcase and prints it.
# It can be used to check if state calculation is correct.
#
# Example invocation:
# python3 display_state_of_testcase.py
#


import os
import sys
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import testcase_state

# filepath_state = "/home/user/Desktop/input/OUTPUT/current_corpus/tc666.js.pickle"
filepath_state = "/home/user/Desktop/test_new_working_dir/current_corpus/tc187.js.pickle"

if os.path.isfile(filepath_state) is False:
    print("State file does not exist!")
    sys.exit(-1)

state = testcase_state.load_state(filepath_state)
print(state)

# The code below can be used to check if copying a state works:
# print("\n\n\nAfter:")
# state = state.deep_copy()
# print(state)
