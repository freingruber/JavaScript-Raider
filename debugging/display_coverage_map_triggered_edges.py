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



# This script displays how many edges are triggered in the current coverage map
# Runtime: 1-2 minutes because of the bit-wise file-reading
# if ctrl+c is hit during processing, incomplete/partial results will be printed!
#
# The script is used to see how good a corpus is and to compare corpus testcases
# from different sources. (e.g: the self created corpus just achieves ~10% coverage)
# whereas the downloaded corpus has over 24% coverage.
#
# Example invocation:
# python3 display_coverage_map_triggered_edges.py


import os
import sys
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

from native_code.executor import Executor


final_coverage_map_input_path = "/home/user/Desktop/input/OUTPUT_new/previous_coverage_map.map"


# Dynamically extract the total number of possible edges
# exec_engine = Executor(timeout_per_execution_in_ms=800, enable_coverage=True)
# exec_engine.adjust_coverage_with_dummy_executions()
# TOTAL_POSSIBLE_EDGES = exec_engine.total_number_possible_edges

# Instead of execution of the v8 engine I can also just hardcode the number of possible edges
# This can be useful if the coverage map was created for an older v8 binary
TOTAL_POSSIBLE_EDGES = 596937

with open(final_coverage_map_input_path, "rb") as fobj:
    content = fobj.read()

# Hacky version, but this is a lot faster than the version which uses a python bit stream...
how_many_nulls = 0  
for x in content:
    if x == 0xff:
        continue
    b1 = x & 0b00000001
    b2 = x & 0b00000010
    b3 = x & 0b00000100
    b4 = x & 0b00001000
    b5 = x & 0b00010000
    b6 = x & 0b00100000
    b7 = x & 0b01000000
    b8 = x & 0b10000000

    if b1 == 0:
        how_many_nulls += 1
    if b2 == 0:
        how_many_nulls += 1
    if b3 == 0:
        how_many_nulls += 1
    if b4 == 0:
        how_many_nulls += 1
    if b5 == 0:
        how_many_nulls += 1
    if b6 == 0:
        how_many_nulls += 1
    if b7 == 0:
        how_many_nulls += 1
    if b8 == 0:
        how_many_nulls += 1

print("Triggered %d of %d possible edges" % (how_many_nulls, TOTAL_POSSIBLE_EDGES))
coverage_percent = float(how_many_nulls) / float(TOTAL_POSSIBLE_EDGES)
coverage_percent *= 100     # convert it to percent
print("Coverage: %.4f" % coverage_percent)
