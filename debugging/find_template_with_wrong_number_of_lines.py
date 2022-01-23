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



# I had a bug in the creation of template states.
# E.g.: an entry contained for example that var_1_ has data type Array in line 20,
# but the testcase just had 19 lines of code.
# This originated from some funny unicode symbols which Python doesn't like
# I used this script to detect these problematic testcases/templates


import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import testcase_state

template_dir = "/home/user/Desktop/input/templates/"

already_processed = 0
for sub_dir in os.listdir(template_dir):
    full_path = os.path.join(template_dir, sub_dir)
    if os.path.isdir(full_path):
        for filename in os.listdir(full_path):
            if filename.endswith(".js") is False:
                continue
            file_fullpath = os.path.join(full_path, filename)

            already_processed += 1
            state_filepath = file_fullpath + ".pickle"
            state = testcase_state.load_state(state_filepath)
            number_of_lines = state.testcase_number_of_lines
            
            for line_number in state.lines_where_code_can_be_inserted:
                if line_number > number_of_lines:
                    print("Bad entry: %s (%d already parsed)" % (state_filepath, already_processed))
                    break
