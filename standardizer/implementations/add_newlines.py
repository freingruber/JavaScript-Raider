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



import standardizer.standardizer_helpers as standardizer_helpers


# Call this function just as soon as comments are removed
# TODO: The code is very similar to:
# import native_code.speed_optimized_functions as speed_optimized_functions
# speed_optimized_functions.get_index_of_next_symbol_not_within_string()
def add_newlines(code_to_minimize, required_coverage):
    tmp = ""
    in_str_double_quote = False
    in_str_single_quote = False
    in_template_str = False
    in_forward_slash = False
    previous_backward_slash = False
    for line in code_to_minimize.split("\n"):
        for current_char in line:
            if current_char == '"':
                if previous_backward_slash:
                    tmp += current_char
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_str_double_quote = not in_str_double_quote
                previous_backward_slash = False
            elif current_char == "'":
                if previous_backward_slash:
                    tmp += current_char
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_str_single_quote = not in_str_single_quote
                previous_backward_slash = False
            elif current_char == "`":
                if previous_backward_slash:
                    # `\`` === '`' // --> true
                    tmp += current_char
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_template_str = not in_template_str
                previous_backward_slash = False
            elif current_char == "\\":
                previous_backward_slash = not previous_backward_slash
                tmp += current_char
            elif current_char == "/":
                if in_str_double_quote or in_str_single_quote or in_template_str or previous_backward_slash:
                    pass
                else:
                    in_forward_slash = not in_forward_slash
                tmp += current_char
                previous_backward_slash = False
            elif current_char == "{":
                if in_str_double_quote or in_str_single_quote or in_template_str or in_forward_slash:
                    tmp += current_char
                else:
                    # not in a string, so we can add a newline
                    tmp += current_char + "\n"
                    # Important, if the character is a {, I can't add a newline in front of the {
                    # The reason is code like this:
                    # return {0.1: a};
                    # If a newline would be added, the return would just be executed (this is the only exception of this behavior in JavaScript..)
                previous_backward_slash = False
            elif current_char == "}":
                if in_str_double_quote or in_str_single_quote or in_template_str or in_forward_slash:
                    tmp += current_char
                else:
                    # not in a string, so we can add a newline
                    tmp += "\n" + current_char + "\n"
                previous_backward_slash = False
            else:
                tmp += current_char
                previous_backward_slash = False
        tmp += "\n"

    # Now remove completely empty lines
    minimized_code = ""
    for line in tmp.split("\n"):
        if line.strip() == "":
            continue
        minimized_code += line + "\n"


    if minimized_code == code_to_minimize.rstrip():
        # Nothing was modified, so it must not be executed again
        return minimized_code

    if standardizer_helpers.does_code_still_trigger_coverage(minimized_code, required_coverage):
        # Minimization worked and we still trigger the new coverage
        return minimized_code
    else:
        # Something went wrong and minimization didn't work
        return code_to_minimize
