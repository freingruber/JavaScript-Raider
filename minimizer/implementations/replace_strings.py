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


def replace_strings(code, required_coverage):
    for string_character in ['"', "'", "`"]:     # currently I don't try regex strings
        fixed_code = ""
        code_to_fix = code
        while True:
            index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code_to_fix, string_character)
            if index == -1:
                break
            rest = code_to_fix[index + 1:]
            end_index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, string_character)
            if end_index == -1:
                break
            code_with_removed_string = fixed_code + code_to_fix[:index] + string_character + string_character + code_to_fix[index + 1 + 1 + end_index:]  # both +1 are for both string characters

            if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_string, required_coverage):
                # Minimization worked and we still trigger the new coverage
                fixed_code = fixed_code + code_to_fix[:index] + string_character + string_character
                code_to_fix = code_to_fix[index + 1 + 1 + end_index:]
            else:
                # Minimization did not work
                fixed_code = fixed_code + code_to_fix[:index + end_index + 1 + 1]
                code_to_fix = code_to_fix[index + 1 + 1 + end_index:]

        # Loop finished, so update the code for the next iteration
        code = fixed_code + code_to_fix
    return code
