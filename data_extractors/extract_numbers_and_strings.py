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


# This script will extract all numbers and strings which occur in
# a JavaScript corpus. The stored database is later loaded by the fuzzer
# and can be used for mutations (e.g.: when changing a number with a mutation).
#
# Note: The resulting database will later work better as soon as the minimizer is improved.
# Currently, the minimizer doesn't try to replace numbers. Example:
# Testcase 1 contains:
# for(let i = 0; i < 64; ++i) {
# And Testcase 2 contains:
# for(let i = 0; i < 68; ++i) {
# => In this case the output database would be: set(0, 64, 68)
# => However, it's very likely that the minimizer can change the numbers to the lowest possible numbers,
# so that e.g. both lines change to:
# for(let i = 0; i < 63; ++i) {
# and they still trigger the same coverage (it's assumed that 63 would be the boundary value to trigger compilation).
# => then the database would just contain set(0, 63) and would therefore be smaller. The likelihood to select "boundary values"
# (like for compilation) is therefore higher.
# A similar idea can be applied to the strings.


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import pickle
from native_code.executor import Execution_Status
import config as cfg
import utils


def create_database():
    all_numbers = set()
    all_strings = set()
    all_numbers_final = set()
    all_strings_final = set()

    # The corpus_iterator() ignores "permanently disabled" files and this is
    # the desired behavior. A lot of permanently disabled testcases
    for testcase_entry in cfg.corpus_js_snippets.corpus_iterator():
        (content, _, _) = testcase_entry

        # Extract the strings and numbers
        string_positions = testcase_mutators_helpers.get_positions_of_all_strings_in_testcase(content)
        number_positions = testcase_mutators_helpers.get_positions_of_all_numbers_in_testcase(content)
        for position_entry in number_positions:
            (start_idx, end_idx) = position_entry
            value = content[start_idx:end_idx+1]
            all_numbers.add(value)

        for position_entry in string_positions:
            (start_idx, end_idx) = position_entry
            value = content[start_idx:end_idx+1]
            all_strings.add(value)

    utils.msg("[i] Found %d unique numbers in the corpus. Going to check if they are valid..." % len(all_numbers))
    idx = 0
    total_executions = len(all_numbers)
    for value in all_numbers:
        idx += 1
        if idx % 100 == 0 or idx == total_executions:
            utils.msg("[i] Status update: Execution %d of %d to verify the extracted numbers." % (idx, total_executions))
        # Check if the execution works (it should not lead to exceptions during fuzzing!)
        # This should work 100% of the time with numbers, the check is more important for strings
        execution_result = cfg.exec_engine.execute_safe("let x = %s;" % value)
        if execution_result.status == Execution_Status.SUCCESS:
            all_numbers_final.add(value)
    utils.msg("[i] Found %d unique numbers which are valid and which will be saved to the database!" % len(all_numbers_final))

    utils.msg("[i] Found %d unique strings in the corpus. Going to check if they are valid..." % len(all_strings))
    idx = 0
    total_executions = len(all_strings)
    for value in all_strings:
        idx += 1
        if idx % 100 == 0 or idx == total_executions:
            utils.msg("[i] Status update: Execution %d of %d to verify the extracted strings." % (idx, total_executions))
        # Check if the execution works (it should not lead to exceptions during fuzzing!)
        # This should work 100% of the time with numbers, the check is more important for strings
        execution_result = cfg.exec_engine.execute_safe("let x = %s;" % value)
        if execution_result.status == Execution_Status.SUCCESS:
            all_strings_final.add(value)
    utils.msg("[i] Found %d unique strings which are valid and which will be saved to the database!" % len(all_strings_final))

    utils.msg("[i] Going to save numbers database at: %s" % cfg.pickle_database_path_numbers)
    with open(cfg.pickle_database_path_numbers, 'wb') as fout:
        pickle.dump(all_numbers, fout, pickle.HIGHEST_PROTOCOL)

    utils.msg("[i] Going to save strings database at: %s" % cfg.pickle_database_path_strings)
    with open(cfg.pickle_database_path_strings, 'wb') as fout:
        pickle.dump(all_strings, fout, pickle.HIGHEST_PROTOCOL)
