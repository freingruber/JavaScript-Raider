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
import native_code.coverage_helpers as coverage_helpers
import testcase_helpers

tmp_coverage_filepath = None


def initialize(current_coverage_filepath):
    global tmp_coverage_filepath
    tmp_coverage_filepath = current_coverage_filepath


def does_code_still_trigger_coverage(new_code, required_coverage):
    global tmp_coverage_filepath
    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(new_code, tmp_coverage_filepath)
    for coverage_entry in required_coverage:
        if coverage_entry not in triggered_coverage:
            return False
    return True





def remove_function(code, function_name):
    # print("REMOVING FUNCTION: %s" % function_name)
    if function_name not in code:
        return code
    index_function_name = code.index(function_name)
    right_side = code[index_function_name + len(function_name):]
    left_side = code[:index_function_name]

    # Let's first fix the right side and remove the function body
    index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(right_side, "{")
    if index == -1:
        return code     # some error case

    rest = right_side[index+1:]
    end_index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "}")
    if end_index == -1:
        return code     # some error case

    stuff_after_function = right_side[index+1+1+end_index:]  # both +1 are for { and }

    # Now let's handle the left side which should still contain something like "\nfunction "
    try:
        newline_index = len(left_side) - left_side[::-1].index("\n") - 1        # search from the end for the last occurrence of newline (which must occur before a function declaration)
        stuff_before_newline = left_side[:newline_index]
        stuff_after_newline = left_side[newline_index+1:]
        if "function" not in stuff_after_newline:
            return code     # something is wrong, so just return the not modified code

        return stuff_before_newline.rstrip("\n") + "\n" + stuff_after_function.lstrip("\n")       # This is the good case, return everything except the function
    except:
        return code     # exception means something was wrong, so just return the not modified code



def remove_variable_from_function_header(content, variable_name):
    codeline = testcase_helpers.get_first_codeline_which_contains_token(content, variable_name)
    token_to_remove = variable_name
    idx = codeline.find(variable_name)
    rest = codeline[idx+len(variable_name):]
    rest_len = len(rest)
    idx = 0
    if rest[idx:].startswith(" "):
        while idx < rest_len:
            current_char = rest[idx]
            if current_char == " ":
                token_to_remove += current_char
                idx += 1
                continue
            else:
                break
    if rest[idx:].startswith(","):
        while idx < rest_len:
            current_char = rest[idx]
            if current_char == ",":
                token_to_remove += current_char
                idx += 1
                continue
            else:
                break
    if rest[idx:].startswith(" "):
        while idx < rest_len:
            current_char = rest[idx]
            if current_char == " ":
                token_to_remove += current_char
                idx += 1
                continue
            else:
                break
    new_content = content.replace(token_to_remove, "")
    return new_content
