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



import utils
import sys
from testsuite.implementations.test_exec_engine import test_exec_engine
from testsuite.implementations.test_coverage_feedback import test_coverage_feedback
from testsuite.implementations.test_speed_optimized_functions import test_speed_optimized_functions
from testsuite.implementations.test_corpus_quality import test_corpus_quality
from testsuite.implementations.test_javascript_operations_database import test_javascript_operations_database_quality


def execute_testsuite(which_tests_to_perform):
    which_tests_to_perform = which_tests_to_perform.lower()

    utils.msg("\n")
    utils.msg("[i] " + "=" * 100)
    utils.msg("[i] Going to start testsuite with argument: %s" % which_tests_to_perform)
    utils.msg("[i] " + "=" * 100)


    if which_tests_to_perform == "speed_optimized_functions" or which_tests_to_perform == "all":
        test_speed_optimized_functions()

    if which_tests_to_perform == "exec_engine" or which_tests_to_perform == "all":
        test_exec_engine()

    if which_tests_to_perform == "coverage_feedback" or which_tests_to_perform == "all":
        test_coverage_feedback()

    if which_tests_to_perform == "corpus" or which_tests_to_perform == "all":
        test_corpus_quality()

    if which_tests_to_perform == "operations_database" or which_tests_to_perform == "all":
        test_javascript_operations_database_quality()

    # if which_tests_to_perform == "state_operations" or which_tests_to_perform == "all":
    # TODO: test_state_operations()
    # => E.g.: if a state modification is correctly implemented (e.g.: adding a line or removing lines)
    # or adding a variable

    # if which_tests_to_perform == "mutations" or which_tests_to_perform == "all":
    # TODO: test_mutations()
    # => Implement testcases for all mutations

    # TODO: Test Minimizer? Test Standardizer?
    # TODO: Check if globals.pickle is correct?

    # Test Sync is currently not implemented, it's a standalone script

    utils.msg("[i] " + "=" * 100 + "\n\n")
