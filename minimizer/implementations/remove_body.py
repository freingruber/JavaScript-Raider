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


import native_code.speed_optimized_functions as speed_optimized_functions
import minimizer.minimizer_helpers as minimizer_helpers


def remove_body(code, required_coverage):
    fixed_code = ""
    code_to_fix = code
    while True:
        index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code_to_fix, "{")
        if index == -1:
            break
        rest = code_to_fix[index+1:]
        end_index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "}")
        if end_index == -1:
            break
        code_with_removed_body = fixed_code + code_to_fix[:index] + "{ }" + code_to_fix[index+1+1+end_index:]  # both +1 are for { and }

        if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_body, required_coverage):
            # Minimization worked and we still trigger the new coverage
            # Now check if I can also add a newline
            # The newline is important so that my fuzzer can later add code in this function by adding code between two lines
            code_with_removed_body = fixed_code + code_to_fix[:index] + "{\n}" + code_to_fix[index+1+1+end_index:]  # both +1 are for { and }
            if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_body, required_coverage):
                fixed_code = fixed_code + code_to_fix[:index] + "{\n}"
                code_to_fix = code_to_fix[index+1+1+end_index:]
            else:
                fixed_code = fixed_code + code_to_fix[:index] + "{ }"
                code_to_fix = code_to_fix[index+1+1+end_index:]
        else:
            # modification didn't work
            # Minimization did not work
            fixed_code = fixed_code + code_to_fix[:index+end_index+1+1]
            code_to_fix = code_to_fix[index+1+1+end_index:]

    return fixed_code + code_to_fix
