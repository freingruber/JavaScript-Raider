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



# This script implements testcase minimization.
# It tries to remove specific parts of the testcase and then executes to code to check if the minimized version
# still triggers the same coverage. If not, the remove operation will be reverted.
# This script supports two main functions:
#
# *) minimize_testcase_fast():
#       This will perform fast minimization. It can be called before a testcase was standardized (e.g. before variable
#       or function tokens were renamed). Standardization can take a long runtime, it therefore makes sense to perform
#       a quick minimization before calling standardization.
#
# *) minimize_testcase():
#       After a testcase was standardized, the full minimization function should be called.
#       This function will try to perform all kinds of minimization.


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import utils
import minimizer.minimizer_helpers as minimizer_helpers

from minimizer.implementations.replace_throw_instructions import replace_throw_instructions
from minimizer.implementations.replace_strings import replace_strings
from minimizer.implementations.remove_line_by_line_multiline import remove_line_by_line_multiline
from minimizer.implementations.remove_try_catch_blocks import remove_try_catch_blocks
from minimizer.implementations.remove_unused_variables_from_function_headers import remove_unused_variables_from_function_headers
from minimizer.implementations.remove_not_required_function_contexts import remove_not_required_function_contexts
from minimizer.implementations.remove_body import remove_body
from minimizer.implementations.remove_line_by_line import remove_line_by_line
from minimizer.implementations.remove_not_referenced_functions import remove_not_referenced_functions
from minimizer.implementations.ensure_tokens_are_contiguous import ensure_tokens_are_contiguous


# The fast method ( minimize_testcase_fast() ) will try to make a testcase small; It can be called without renaming tokens first
# => first make fast minimization, then rename all tokens (which means this can be called in a minimized testcase)
# at the end fall the normal minimization function ( minimize_testcase() ) which also depends on renamed tokens
def minimize_testcase_fast(content, required_coverage, current_coverage_filepath):
    original_length = len(content)
    utils.msg("[i] Start fast minimization of file; original length: %d" % original_length)

    minimizer_helpers.initialize(current_coverage_filepath)

    content = remove_body(content, required_coverage).rstrip()
    content = remove_line_by_line(content, required_coverage).rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "{", "}").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "(", ")").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "[", "]").rstrip()
    content = remove_line_by_line(content, required_coverage).rstrip()
    content = remove_try_catch_blocks(content, required_coverage).rstrip()

    utils.msg("[i] Finished fast minimization of file; original length: %d ; new length %d" % (original_length, len(content)))
    return content


# This function will perform all minimization steps on a testcase.
# The input testcase should already have renamed tokens (e.g.: variable should be named var_1_ and so on).
# If you want to fast minimize a testcase before renaming tokens you should call
# minimize_testcase_fast() instead.
def minimize_testcase(content, required_coverage, current_coverage_filepath):
    original_length = len(content)
    utils.msg("[i] Start minimization of file; original length: %d" % original_length)

    minimizer_helpers.initialize(current_coverage_filepath)

    # Note:
    # I'm now ensuring inside handle_new_file.py that >required_coverage< only contains deterministic behavior.
    # So I must not check here again if I can really trigger this behavior every time

    content = remove_not_referenced_functions(content, required_coverage).rstrip()
    content = remove_body(content, required_coverage).rstrip()
    content = remove_line_by_line(content, required_coverage).rstrip()

    # remove_not_referenced_functions() is called twice, as first and last function
    # This is important to remove cyclic functions, e.g. func1 just calls func2 and func2 calls func1
    # But func1 and func2 are not called elsewhere in the code
    # After removing code line by line both function bodies will be empty
    # Afterwards these functions will be removed
    # The first call to this function is important to ensure that testcases are very quickly small
    # so that the runtime is fast because less executions are required
        
    content = remove_line_by_line_multiline(content, required_coverage, "{", "}").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "(", ")").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "[", "]").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "{", "}").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "(", ")").rstrip()
    content = remove_line_by_line_multiline(content, required_coverage, "[", "]").rstrip()
    content = remove_line_by_line(content, required_coverage).rstrip()

    content = remove_not_referenced_functions(content, required_coverage).rstrip()
    content = replace_strings(content, required_coverage).rstrip()
    
    content = remove_try_catch_blocks(content, required_coverage).rstrip()

    content = remove_unused_variables_from_function_headers(content, required_coverage).rstrip()
    content = remove_not_required_function_contexts(content, required_coverage).rstrip()
    content = replace_throw_instructions(content, required_coverage).rstrip()

    content = ensure_tokens_are_contiguous(content, required_coverage)

    utils.msg("[i] Finished minimization of file; original length: %d ; new length %d" % (original_length, len(content)))
    return content
