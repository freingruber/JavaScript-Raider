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



# This script contains functions to rename tokens (variable names, function, classes, ..)

import re
import javascript.js_helpers as js_helpers


def rename_variable_name_safe(content, old_variable_name, new_variable_id):
    new_variable_name = "var_%d_" % new_variable_id
    return replace_token_safe(content, old_variable_name, new_variable_name)


def rename_function_name_safe(content, old_function_name, new_function_id):
    new_function_name = "func_%d_" % new_function_id
    return replace_token_safe(content, old_function_name, new_function_name)


def rename_class_name_safe(content, old_class_name, new_class_id):
    new_class_name = "cl_%d_" % new_class_id
    return replace_token_safe(content, old_class_name, new_class_name)


def rename_variable_name_old(code, variable_name, variable_id):
    return replace_token_old(code, variable_name, variable_id, "var")


def rename_function_name_old(code, variable_name, function_id):
    return replace_token_old(code, variable_name, function_id, "func")


def rename_class_name_old(code, variable_name, class_id):
    return replace_token_old(code, variable_name, class_id, "cl")



def replace_token_safe(content, old_token_name, new_token_name):
    content_without_special_chars = js_helpers.get_content_without_special_chars(content)
    content_without_special_chars += " "    # add a space at the end to ensure that tokens at the very end of the file are detected!

    old_token_name_with_space = old_token_name + " "
    old_token_name_length = len(old_token_name)

    variable_length_diff = len(new_token_name) - len(old_token_name)
    diff_offset = 0

    all_positions_to_replace = [m.start() for m in re.finditer(re.escape(old_token_name_with_space), content_without_special_chars)]
    for start_offset in all_positions_to_replace:
        fixed_offset = start_offset + diff_offset
        part1 = content[:fixed_offset]

        part1_with_specials = content_without_special_chars[:fixed_offset]
        if len(part1_with_specials) != 0:
            last_char = part1_with_specials[-1]
            if last_char != " ":
                # skip because it's not a correct token
                # for example, it can happen that a function named "_" gets renamed
                # If the testcase would contain variables like "var_1_" it would start to replace the 2nd "_"
                # (the first is already prevented because the char afterwards is checked; However I forgot to also check the previous char)
                # => this check here checks the previous chars and prevents that I rename "var_1_" to "var_1func_1_"
                continue
            # print("LAST_CHAR: >%s<" % last_char)
        part2 = content[fixed_offset+old_token_name_length:]
        part2_with_specials = content_without_special_chars[fixed_offset+old_token_name_length:]
        content = part1 + new_token_name + part2

        content_without_special_chars = part1_with_specials + new_token_name + part2_with_specials  # must also be updated so that >part1_with_specials< above is calculated correctly in the next iteration
        diff_offset += variable_length_diff
    return content


# The old implementation
# You should now use replace_token_safe() instead
def replace_token_old(code, variable_name, variable_id, token):
    all_occurrences = []
    i = code.find(variable_name)
    while i != -1:
        all_occurrences.append(i)
        i = code.find(variable_name, i + 1)

    good_occurrences = []
    for occurrence in all_occurrences:
        try:
            char_before = code[occurrence - 1]
        except:
            char_before = " "  # if it's the first char in the file it throws an exception, then I fake a valid char

        try:
            char_before_before = code[occurrence - 1]
        except:
            char_before_before = " "  # if it's the first char in the file it throws an exception, then I fake a valid char

        try:
            char_after = code[occurrence + len(variable_name)]
        except:
            char_after = " "  # if it's the last char in the file it throws an exception, then I fake a valid char

        # The "." check below is to handle cases like:
        # var fround = stdlib.Math.fround;
        # In this case the "stdlib.Math.fround" should not be renamed.
        if char_before.isalnum() is False and char_after.isalnum() is False and char_before != "." and char_before != "_" and char_after != "_":
            good_occurrences.append(occurrence)
        else:
            if char_before == "." and char_before_before == ".":
                # Code like: for (var [...y] in Object) {
                # where y must be renamed
                good_occurrences.append(occurrence)

    tmp = ""
    last_idx = 0
    for occurrence in good_occurrences:
        # print("VARIABLE NAME: >%s<" % variable_name)
        # print("Stuff before:")
        # print(code[last_idx:occurrence])
        tmp = tmp + code[last_idx:occurrence] + ("%s_%d_" % (token, variable_id))
        last_idx = occurrence + len(variable_name)
        # print("Updated last idx to: %d" % last_idx)
    # print("Adding the end:")
    # print(code[last_idx:])
    tmp += code[last_idx:]

    return tmp
