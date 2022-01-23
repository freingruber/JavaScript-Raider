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



import minimizer.minimizer_helpers as minimizer_helpers


def remove_not_referenced_functions(code, required_coverage):
    function_idx = 1
    code_without_not_referenced_functions = code
    while True:
        function_name = "func_%d_" % function_idx
        function_idx += 1
        if function_name not in code:
            break
        num_occurrences = code.count(function_name)
        if num_occurrences == 0:
            break   # should not occur
        elif num_occurrences == 1:
            # In this case the only occurrence is the declaration of the function
            # The function can therefore be removed
            code_without_not_referenced_functions = minimizer_helpers.remove_function(code_without_not_referenced_functions, function_name)

    if minimizer_helpers.does_code_still_trigger_coverage(code_without_not_referenced_functions, required_coverage):
        return code_without_not_referenced_functions
    else:
        # Return the not modified code
        return code
