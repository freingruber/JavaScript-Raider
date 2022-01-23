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



# This function ensures that all tokens are contiguous. It should be
# called as last minimization function (and only if the testcase was already standardized).
# Other minimization functions maybe remove lines and therefore remove all occurrences of specific
# variables. For example, let's assume a testcase contains var_1_, var_2_ and var_3_.
# var_2_ just occurs in line 4 and the minimizer removes line 4. In this case var_3_ should be
# renamed to var_2_ because the testcase doesn't contain the original var_2_ anymore.
# The same applies for functions and classes.
# This is implemented in this script.

import minimizer.minimizer_helpers as minimizer_helpers
import testcase_helpers


def ensure_tokens_are_contiguous(code, required_coverage):

    # Handle variables:
    new_code = testcase_helpers.ensure_all_variable_names_are_contiguous(code)
    if new_code != code:
        if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
            code = new_code   # Renaming was successful
        else:
            # renaming failed - however renaming is important, so let's try to fix it
            # Try it a second time:
            if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
                code = new_code   # Renaming was successful
            else:
                # 2nd time was also not successful
                pass

    # Handle functions:
    new_code = testcase_helpers.ensure_all_function_names_are_contiguous(code)
    if new_code != code:
        if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
            code = new_code   # Renaming was successful
        else:
            # renaming failed - however renaming is important, so let's try to fix it
            # Try it a second time:
            if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
                code = new_code   # Renaming was successful
            else:
                # 2nd time was also not successful
                pass

    # Handle classes
    new_code = testcase_helpers.ensure_all_class_names_are_contiguous(code)
    if new_code != code:
        if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
            code = new_code   # Renaming was successful
        else:
            # renaming failed - however renaming is important, so let's try to fix it
            # Try it a second time:
            if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
                code = new_code   # Renaming was successful
            else:
                # 2nd time was also not successful
                pass

    return code
