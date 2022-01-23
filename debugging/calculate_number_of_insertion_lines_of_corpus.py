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



# I use this script to calculate how many deterministic operations I will implement.
# Edit: Previously I used deterministic operations, but the current fuzzer doesn't use them anymore.
# E.g. in a corpus with 9500 files there are ~157 000 lines where i can insert code.
# Lets assume that I try to insert 23 additional code lines in every line during deterministic fuzzing.
# That would result in 157 000 * 23 = 3 611 000 required executions
# Lets assume that I can perform in my slow VM 30 exec/sec
# => it would require 120366 seconds which is something like 33 hours
# The formula to calculate the required processing time in days is:
# (((157000*23)/30.0) / 60) / 60.0 / 24.0
# Whereas:
#  *) 157000 is the number code code lines
#  *) 23 is the number of deterministic operations
#  *) 30 is the execution time (e.g. on AWS it's 110 exec/sec)
#
# => I use this script to determine how many deterministic operations I want to perform to estimate the runtime
# This helps me to decide which operations I want to perform "deterministically" (= always) and which I want to
# just perform during fuzzing (randomly)
#
# Example invocation:
# python3 calculate_number_of_insertion_lines_of_corpus.py
#


import os
import sys
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)


import testcase_state
import utils

base_path = '/home/user/Desktop/input/OUTPUT/current_corpus/'  # Corpus input path

NUMBER_OF_DETERMINISTIC_OPERATIONS = 40
EXEC_TIME = 110

total_possible_insertions = 0
last_testcase_id = utils.get_last_testcase_number(base_path)
print("Last testcase ID: %d" % last_testcase_id)
for current_id in range(1, last_testcase_id+1):
    filename = "tc%d.js.pickle" % current_id
    filepath = os.path.join(base_path, filename)
    filepath_state = os.path.join(base_path, filename)
    if os.path.isfile(filepath_state) is False:
        continue
    state = testcase_state.load_state(filepath_state)
    total_possible_insertions += len(state.lines_where_code_can_be_inserted)
    total_possible_insertions += len(state.lines_where_code_with_coma_can_be_inserted)

print("In total %d possible code lines for insertion" % total_possible_insertions)

runtime_in_days = (((total_possible_insertions * NUMBER_OF_DETERMINISTIC_OPERATIONS)/30.0) / 60) / 60.0 / float(EXEC_TIME)
print("Estimated total runtime: %.2f days" % runtime_in_days)
