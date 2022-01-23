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


def get_first_codeline_which_contains_token(content, token):
    for codeline in content.split("\n"):
        if token in codeline:
            return codeline.strip()
    return None  # token not found


# Line numbers start at 0 (and not at 1)!
# So line_number 1 means line 2
def content_offset_to_line_number(lines, offset):
    line_number = 0
    current_offset = 0
    for line in lines:
        offset_at_end_of_line = current_offset + len(line)
        # print("Offset at end of line %d is 0x%x" % (line_number, offset_at_end_of_line))
        if offset <= offset_at_end_of_line:
            return line_number

        current_offset = offset_at_end_of_line + 1  # +1 for the newline
        line_number += 1
    return None  # bug, should not occur


# If a testcase has "var_1_" and "var_3_" but no "var_2_"
# This function will rename all "var_3_" occurrences to "var_2_"
def ensure_all_variable_names_are_contiguous(code):
    return _ensure_all_token_names_are_contiguous("var_%d_", code)


def ensure_all_function_names_are_contiguous(code):
    return _ensure_all_token_names_are_contiguous("func_%d_", code)


def ensure_all_class_names_are_contiguous(code):
    return _ensure_all_token_names_are_contiguous("cl_%d_", code)


def _ensure_all_token_names_are_contiguous(token, code):
    max_number_of_variables = 1000  # assuming that all testcases have less than 1000 variable names
    variable_in_use = [False] * max_number_of_variables
    next_token_id = 1

    # Check which tokens are in-use
    for idx in range(max_number_of_variables):
        variable_id = idx + 1
        token_name = token % idx
        if token_name in code:
            new_token_name = token % next_token_id
            next_token_id += 1
            if new_token_name == token_name:
                pass  # nothing to do
            else:
                # they are different, e.g. token_name has a higher token ID, so change it
                code = code.replace(token_name, new_token_name)
    return code



def get_highest_variable_token_id(code):
    max_number_of_variables = 1000  # assuming that all testcases have less than 1000 variable names

    highest = 1
    for idx in range(max_number_of_variables):
        variable_id = idx + 1
        token_name = "var_%d_" % idx
        if token_name in code:
            highest = variable_id
    return highest


def remove_numbers_from_testcase(code):
    for number in range(0, 9 + 1):
        code = code.replace(str(number), "")  # remove all numbers
    return code


def remove_strings_from_testcase(code):
    original_code = code
    fixed_code = ""
    while True:
        # Try to remove "-strings
        idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, '"')
        if idx != -1:
            # testcase contains a "-string
            part1 = code[:idx + 1]  # everything including the " symbol
            rest = code[idx + 1:]
            idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, '"')
            if idx2 == -1:
                # should not occur, it means number of " symbols is not even
                # just return original code because there was maybe a flaw in testcase rewriting
                return original_code
            part2 = rest[idx2 + 1:]
            fixed_code += part1 + '"'
            code = part2
            continue
        # Try to remove '-strings
        idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "'")
        if idx != -1:
            # testcase contains a '-string
            part1 = code[:idx + 1]  # everything including the ' symbol
            rest = code[idx + 1:]
            idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "'")
            if idx2 == -1:
                # should not occur, it means number of ' symbols is not even
                # just return original code because there was maybe a flaw in testcase rewriting
                return original_code
            part2 = rest[idx2 + 1:]
            fixed_code += part1 + "'"
            code = part2
            continue

        # Try to remove `-strings
        idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "`")
        if idx != -1:
            # testcase contains a '-string
            part1 = code[:idx + 1]  # everything including the ` symbol
            rest = code[idx + 1:]
            idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "`")
            if idx2 == -1:
                # should not occur, it means number of ` symbols is not even
                # just return original code because there was maybe a flaw in testcase rewriting
                return original_code
            part2 = rest[idx2 + 1:]
            fixed_code += part1 + '`'
            code = part2
            continue

        break  # if this point is reached no strings are found

    return fixed_code + code
