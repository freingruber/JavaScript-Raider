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


# Yes, this code really works...
# (at least I hope so)
# TODO: The code is very similar to:
# import native_code.speed_optimized_functions as speed_optimized_functions
# speed_optimized_functions.get_index_of_next_symbol_not_within_string()
# => Combine them!
def remove_comments(code_to_minimize, required_coverage):
    tmp = ""
    in_str_double_quote = False
    in_str_single_quote = False
    in_template_str = False
    previous_forward_slash = False
    previous_backward_slash = False
    in_multiline_comment = False
    previous_was_star = False
    for line in code_to_minimize.split("\n"):
        for current_char in line:
            if in_multiline_comment and not (current_char == "*" or current_char == "/"):
                previous_was_star = False
                continue    # ignore stuff inside multi-line comments
            if current_char == '"':
                if previous_backward_slash:
                    tmp += current_char
                    previous_forward_slash = False
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_str_double_quote = not in_str_double_quote
                previous_forward_slash = False
                previous_backward_slash = False
            elif current_char == "'":
                if previous_backward_slash:
                    tmp += current_char
                    previous_forward_slash = False
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_str_single_quote = not in_str_single_quote
                previous_forward_slash = False
                previous_backward_slash = False
            elif current_char == "`":
                if previous_backward_slash:
                    # `\`` === '`' // --> true
                    tmp += current_char
                    previous_forward_slash = False
                    previous_backward_slash = False
                    continue
                tmp += current_char
                in_template_str = not in_template_str
                previous_forward_slash = False
                previous_backward_slash = False
            elif current_char == "/":
                if previous_was_star:
                    # This means we were in a multi-line comment and it now terminated
                    previous_was_star = False
                    in_multiline_comment = False
                    previous_forward_slash = False
                    previous_backward_slash = False
                    continue    # ignore the current character and continue with next character normally
                previous_backward_slash = False
                if in_str_double_quote or in_str_single_quote or in_template_str:
                    # inside a string, so just add the character
                    tmp += current_char
                else:
                    if previous_forward_slash:
                        tmp = tmp[:-1]  # Remove the previous slash (which was the comment symbol)
                        break
                    else:
                        tmp += current_char
                        previous_forward_slash = True
            elif current_char == "\\":
                previous_backward_slash = not previous_backward_slash
                tmp += current_char
                previous_forward_slash = False
            elif current_char == "*":
                if in_multiline_comment:
                    previous_was_star = True
                    continue
                if previous_forward_slash:
                    # Start of a multi line comment
                    in_multiline_comment = True
                    tmp = tmp[:-1]
                else:
                    tmp += current_char
            else:
                tmp += current_char
                previous_forward_slash = False
                previous_backward_slash = False
        tmp = tmp.rstrip()
        tmp += "\n"

    minimized_code = tmp.rstrip()

    if standardizer_helpers.does_code_still_trigger_coverage(minimized_code, required_coverage):
        return minimized_code
    else:
        return code_to_minimize     # didn't work
