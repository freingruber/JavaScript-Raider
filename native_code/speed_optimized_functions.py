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



# Some function implementations are very slow in Python code
# Since some of these functions are frequently called, I re-implemented them
# in C Code.
# This file contains the Python-wrappers which call the C-implementations
#
# For some examples + expected results you can check the file:
# example_usage_speed_optimized_functions.py

import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if current_dir not in sys.path: sys.path.append(current_dir)
if base_dir not in sys.path: sys.path.append(base_dir)

import libJSEngine  # C implementation for the executor; execute ./compile.sh to create it


# The function currently supports at least the following "symbol" values:
# ( ) { } [ ] / " ' ` ,
# Note: The name of the function is maybe a little bit misleading.
# Check the testsuite code to see some function invocation examples and expected results
def get_index_of_next_symbol_not_within_string(content, symbol, default_value=None):
    symbol_int = ord(symbol)
    idx = libJSEngine.get_index_of_next_symbol_not_within_string(content, symbol_int)
    if default_value is not None:
        idx = default_value if idx == -1 else idx
    return idx


# The function does not return an error code if the offset is wrong (e.g. outside of content)
# The caller must ensure that the offset argument is correct
def get_line_number_of_offset(content, offset):
    return libJSEngine.get_line_number_of_offset(content, offset)


# --------------------- Below here are the slow (old) Python implements ---------------------
"""
def get_line_number_of_offset_python_version_slow(content, offset):
    # Old slow implementation (consumes 3% of overall time (!))

    line_number = 0
    return_line = -1
    for idx in range(len(content)):
        if idx == offset:
            return_line = line_number
            break
        if content[idx] == "\n":
            line_number += 1
    return return_line

def get_line_number_of_offset_python_version_fast(content, offset):
    # New fast implementation (consumes 0.1% of overall time)
    # => Attention when modifying this function, it can has a huge impact on the overall speed
    current_line_offset = 0
    line_number = 0
    return_line = -1
    for line in content.split("\n"):
        if offset >= current_line_offset and offset <= (current_line_offset + len(line)):
            return_line = line_number
            break
        current_line_offset += len(line) + 1    # +1 for newline
        line_number += 1
    return return_line
"""

# This is the old (slow) python implementation
"""
def get_index_of_next_symbol_not_within_string_python_version(content, symbol):
    if symbol == "\\" or symbol == "*":
        print("TODO, this symbol is currently not supported: %s" % symbol)
        sys.exit(-1)
    in_str_double_quote = False
    in_str_single_quote = False
    in_template_str = False
    in_regex_str = False
    previous_forward_slash = False
    previous_backward_slash = False
    in_multiline_comment = False
    previous_was_star = False
    bracket_depth = 0
    curly_bracket_depth = 0
    square_bracket_depth = 0
    for idx in range(0, len(content)):
        current_char = content[idx]
        # print("Current char: %s" % current_char)
        if in_multiline_comment and not (current_char == "*" or current_char == "/"):
            previous_was_star = False
            previous_backward_slash = False
            previous_forward_slash = False
            continue  # ignore stuff inside multi-line comments
        if current_char == '"':
            if in_str_single_quote or in_template_str or in_regex_str:
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if previous_backward_slash:
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if current_char == symbol:
                return idx
            in_str_double_quote = not in_str_double_quote
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == "'":
            if in_str_double_quote or in_template_str or in_regex_str:
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if previous_backward_slash:
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if current_char == symbol:
                return idx
            in_str_single_quote = not in_str_single_quote
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == "`":
            if in_str_double_quote or in_str_single_quote or in_regex_str:
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if previous_backward_slash:
                # `\`` === '`' // --> true
                previous_forward_slash = False
                previous_backward_slash = False
                continue
            if current_char == symbol:
                return idx
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
                continue  # ignore the current character and continue with next character normally

            if in_str_double_quote or in_str_single_quote or in_template_str:
                # inside a string
                previous_backward_slash = False
                continue
            else:
                if previous_forward_slash:
                    # That means we are inside an comment
                    # TODO implement
                    in_regex_str = False
                else:
                    # That means it's the first /
                    if not previous_backward_slash:
                        # in_regex_str = not in_regex_str # that means it could be an regex str
                        pass

                        if current_char == symbol:
                            return idx

                        # for the moment I ignore the regex strings which look e.g.: like:
                        # /abc+/i
                        # Reason: it can also be math code like a division like:
                        # 0/0
                        # I don't know how I can differentiate here...
                previous_forward_slash = True
            previous_backward_slash = False
        elif current_char == "\\":
            previous_backward_slash = not previous_backward_slash
            previous_forward_slash = False
        elif current_char == "*":
            if in_multiline_comment:
                previous_was_star = True
                continue
            if previous_forward_slash:
                # Start of a multi line comment
                in_multiline_comment = True
        elif current_char == "{":
            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if not previous_backward_slash:
                    if current_char == symbol:
                        return idx
                    curly_bracket_depth += 1
            previous_forward_slash = False
            previous_backward_slash = False

        elif current_char == "[":
            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if previous_backward_slash is False:
                    if current_char == symbol:
                        return idx
                    square_bracket_depth += 1
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == "]":
            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if current_char == symbol:
                    if square_bracket_depth == 0:
                        return idx
                square_bracket_depth -= 1
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == "(":
            # print("Start (")
            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if previous_backward_slash is False:
                    if current_char == symbol:
                        return idx
                    bracket_depth += 1
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == ")":
            # print("End )")
            # print(in_str_double_quote)
            # print(in_str_single_quote)
            # print(in_regex_str)
            # print(in_template_str)
            # print(bracket_depth)

            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if current_char == symbol:
                    if bracket_depth == 0:
                        return idx
                bracket_depth -= 1
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == "}":

            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                # TODO: I don't check here for simple comments like // bla
                if current_char == symbol:
                    if curly_bracket_depth == 0:
                        return idx
                curly_bracket_depth -= 1
            previous_forward_slash = False
            previous_backward_slash = False
        elif current_char == ",":
            if in_str_double_quote is False and in_str_single_quote is False and in_template_str is False and in_multiline_comment is False and in_regex_str is False:
                # We are not inside a string or comment
                if current_char == symbol:
                    if bracket_depth == 0 and curly_bracket_depth == 0 and square_bracket_depth == 0:
                        return idx
            previous_forward_slash = False
            previous_backward_slash = False
        else:
            if current_char == symbol:
                return idx
            previous_forward_slash = False
            previous_backward_slash = False
    return -1  # Symbol is not within the content
"""
