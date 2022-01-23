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


# This script "standardizes" a testcase
# It will rename tokens like variable, function or class names and
# insert newlines at required locations.
#
# TODO: An important property is that the code should be idempotent. Is this currently the case?

# TODO: maybe also change code like "function\txyz" to "function xyz" and also remove multiple spaces
# so that later code doesn't has to handle such cases...
# My current code is pretty ugly because I often parse for "\t" and "\n" in all cases where a space can occur..


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import utils
import standardizer.standardizer_helpers as standardizer_helpers
from standardizer.implementations.add_newlines import add_newlines
from standardizer.implementations.add_possible_required_newlines import add_possible_required_newlines
from standardizer.implementations.remove_comments import remove_comments
from standardizer.implementations.remove_semicolon_lines import remove_semicolon_lines
from standardizer.implementations.remove_shebang import remove_shebang
from standardizer.implementations.rename_classes import rename_classes
from standardizer.implementations.rename_functions import rename_functions
from standardizer.implementations.rename_variables import rename_variables
import native_code.coverage_helpers as coverage_helpers
import config as cfg


def standardize_testcase(content, required_coverage, current_coverage_filepath):
    utils.msg("[i] Start to standardize testcase..")

    standardizer_helpers.initialize(current_coverage_filepath)

    content = remove_shebang(content, required_coverage)
    content = remove_comments(content, required_coverage)
    content = remove_semicolon_lines(content, required_coverage)
    
    content = add_possible_required_newlines(content, required_coverage)

    content = rename_variables(content, required_coverage)
    content = rename_functions(content, required_coverage)
    content = rename_classes(content, required_coverage)

    # Important; adding newlines must occur after renaming variables
    # Otherwise it leads to problems with lines like:
    # let {x} = ...
    # Because newline would be added after {
    content = add_newlines(content, required_coverage)

    return content


# The function standardize_testcase() is typically started via the JS_Fuzzer.py script
# To manually test this script with a specific testcase,
# you can add a call to this function at the end of the script and execute the script
def manually_start_this_script():
    from native_code.executor import Executor

    test_code = ""
    coverage_map_path = "test_coverage.map"
    exec_engine = Executor(timeout_per_execution_in_ms=6000, enable_coverage=True)
    exec_engine.adjust_coverage_with_dummy_executions()
    cfg.exec_engine = exec_engine       # Make exec engine available to all sub modules
    exec_engine.execute_safe("const bla = 1; print(1);")
    exec_engine.execute_safe("var foobar = 1+3;")
    exec_engine.save_global_coverage_map_in_file(coverage_map_path)

    previous_coverage = coverage_helpers.extract_coverage_from_coverage_map_file(coverage_map_path)

    exec_engine.restart_engine()    # Restart to ensure that the testcase is executed in a fresh process
    new_coverage = coverage_helpers.extract_coverage_of_testcase(test_code, coverage_map_path)
    new_coverage = coverage_helpers.remove_already_known_coverage(new_coverage, previous_coverage)

    if len(new_coverage) == 0:
        # Try it one more time to really be 100% sure that the testcase doesn't trigger new behavior (deterministically)
        exec_engine.restart_engine()
        new_coverage = coverage_helpers.extract_coverage_of_testcase(test_code, coverage_map_path)
        new_coverage = coverage_helpers.remove_already_known_coverage(new_coverage, previous_coverage)
        if len(new_coverage) == 0:
            utils.perror("[-] Could not trigger new behavior again. Maybe the behavior is not deterministic, skipping input...")    # most likely an implementation error on my side if this occurs

    for i in range(0, 5):
        triggered_coverage = coverage_helpers.extract_coverage_of_testcase(test_code, coverage_map_path)
        problem_entries = []
        for coverage_entry in new_coverage:
            if coverage_entry not in triggered_coverage:
                utils.msg("[-] Problem finding coverage %d again in file" % coverage_entry)
                problem_entries.append(coverage_entry)

        for coverage_entry in problem_entries:
            new_coverage.remove(coverage_entry)

    if len(new_coverage) == 0:
        utils.perror("[-] Problem")

    print("Required new coverage: %d" % len(new_coverage))
    ret = standardize_testcase(test_code, new_coverage, coverage_map_path)
    print("Result:")
    print(ret)

# manually_start_this_script()
