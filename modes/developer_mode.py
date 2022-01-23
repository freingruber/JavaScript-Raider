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


# This mode can be started by passing the "--developer_mode" flag to the fuzzer.
#
# I'm using this mode during development. I add code to the mode which executes
# e.g.: a mutation strategy which I currently implement. Then the developer mode
# just executes this mutation strategy on a specific testcase and I implement it
# (and for corner cases for different testcases)
# Note: It's recommended to also specify a --seed argument to get reliable results
# during development

"""
# Example invocation:

python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--seed 25 \
--resume \
--developer
"""


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import utils
import config as cfg
import testcase_state
from native_code.executor import Executor, Execution_Status
import mutators.database_operations as database_operations
from mutators.implementations.mutation_if_wrap_operations import mutation_if_wrap_operations
from mutators.implementations.mutation_modify_number import mutation_modify_number


def load_testcase():
    testcase_path = "/home/user/Desktop/input/OUTPUT/current_corpus/tc3770.js"
    state_path = testcase_path + ".pickle"
    with open(testcase_path, 'r') as fobj:
        testcase_content = fobj.read().rstrip()
    state = testcase_state.load_state(state_path)
    return testcase_content, state


def start_developer_mode():
    (testcase_content, state) = load_testcase()

    utils.print_diff_with_line_numbers("Input testcase:", testcase_content, testcase_content)
    # print("Input testcase:")
    # print("#"*30)
    # print(testcase_content)
    print("#"*30)
    print("\n")
    
    # print("State:")
    # print(state.get_summary())

    number_iterations = 1
    for i in range(number_iterations):
        state_copy = state.deep_copy()

        # random_code = debugging_call_get_random_js_thing(testcase_content, state_copy, 2)
        # print("Returned random code:")
        # print(random_code)
        
        # parts = testcase_content.split("\n")
        # instr = js_parsing.parse_next_instruction('\n'.join(parts[5:]))
        # print("Result:")
        # print(instr)

        (result_content, result_state) = mutation_modify_number(testcase_content, state_copy)

        # print("Result:")
        # print("#"*30)
        # print(result_content)

        # utils.print_diff_with_line_numbers("Result", testcase_content, result_content)

        # Printing a diff in colors is sometimes buggy (e.g. counting of line numbers)
        # In such cases I don't print the diff by passing twice the same argument
        utils.print_diff_with_line_numbers("Result", result_content, result_content)

        # input("<press enter to show state>")
        # print("#"*30)
        # print("State:")
        # print(result_state.get_summary())

        result = cfg.exec_engine.execute_safe(result_content)
        print("Execution result:")
        print(result)

        if number_iterations != 1:
            input("<press enter to continue>")
