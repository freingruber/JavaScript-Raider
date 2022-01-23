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

import config as cfg
import utils
import testsuite.testsuite_helpers as helper

from testsuite.testcases_for_corpus_quality import expected_operations_in_database


def test_corpus_quality():
    utils.msg("\n")
    utils.msg("[i] " + "-" * 100)
    utils.msg("[i] Going to check quality of the current corpus...")
    helper.reset_stats()

    testcases_from_corpus = []
    for entry in cfg.corpus_js_snippets.corpus_iterator():
        (code, _, _) = entry
        # The testcases contain code like "var_2_.pop()", but my test-dataset
        # contains entries like "var_TARGET_.pop()". => I therefore rename all variables
        # to "var_TARGET_" and then I can easily check if I have the "var_TARGET_.pop()"
        # operation in my corpus by just checking if the string occurs in one of the testcases
        code = replace_all_variables(code)
        testcases_from_corpus.append(code)

    # Now check if all these required code snippets can be found in the corpus:
    performed_tests = 0
    successful_tests = 0
    for entry in expected_operations_in_database:
        (expected_operation_code, _) = entry  # the data type is ignored in the "corpus" tests
        performed_tests += 1
        does_corpus_contain_operation = False
        for testcase_code in testcases_from_corpus:
            if expected_operation_code in testcase_code:
                does_corpus_contain_operation = True
                break
        if does_corpus_contain_operation:
            successful_tests += 1

    # Print results:
    if successful_tests == performed_tests:
        utils.msg("[+] Corpus quality result: All %d performed checks were passed! Your corpus looks good!" % performed_tests)
    else:
        success_rate = (float(successful_tests) / performed_tests) * 100.0
        utils.msg("[!] Corpus quality result: %d of %d (%.2f %%) tests were successful!" % (successful_tests, performed_tests, success_rate))

    utils.msg("[i] " + "-" * 100)


def replace_all_variables(code):
    for i in range(1, 1000):    # testcases have typically max. 50-100 variables, 1000 variables is already a huge over-estimation
        token = "var_%d_" % i
        code = code.replace(token, "var_TARGET_")
    return code
