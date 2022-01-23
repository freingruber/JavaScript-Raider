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



# During development it can be useful to find testcases which use specific data types like "Intl.Locale"
# For example, if mutations performed on a variable of data type "Intl.Local" often lead to exceptions,
# I can search for all such testcases, then hardcode these names into the developer-mode file
# and use the developer-mode to debug just Intl.Local mutations.
# This scripts searches for a specific data type in all testcases in the corpus.


import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import testcase_state


variable_type_to_search = "webassembly.table"

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
    
    for variable_name in state.variable_types:
        for entry in state.variable_types[variable_name]:
            (line_number, variable_type) = entry
            if variable_type == variable_type_to_search:
                print(filename)
                break
        else:
            continue
        break

# x = Testcase_State(1,1,1)
# x.calculate_curly_bracket_offsets(content)
# print(content)
# (self, content):
