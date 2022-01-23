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


def remove_line_by_line(code, required_coverage):
    lines = code.split("\n")
    lines_length = len(lines)

    keep_line = [True]*lines_length
    # I iterate backwards to start to remove the last lines
    # This is important because variable declarations come typically first
    # So removing a variable declaration if there is still code afterwards which uses the variable
    # can't work because it leads to an exception.
    # I therefore start from the end and go backwards to the first line
    # Note: With >variable hoisting< this can still lead to problems, but this should work most of the time
    # It can also create problems with functions & function calls, however, I handle them before I start with this code here
    for line_to_remove in range(lines_length-1, -1, -1):
        code_with_removed_line = ""
        for line_index in range(lines_length):
            if line_index == line_to_remove:
                continue    # skip the add
            if keep_line[line_index]:
                code_with_removed_line += lines[line_index] + "\n"
        # Now >code_with_removed_line< holds the code with one line removed
        # Now check if it still triggers the same behavior
        # print("-----------------------")
        # print(code_with_removed_line)
        # print("-----------------------")
        # print("\n"*3)

        # keep_line[line_to_remove] = False
        # print("here1: %d line" % line_to_remove)
        if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_line, required_coverage):
            keep_line[line_to_remove] = False   # The line is not important because it could be minimized away
        else:
            keep_line[line_to_remove] = True    # the line is important

    final_code = ""
    for line_index in range(lines_length):
        if keep_line[line_index]:
            final_code += lines[line_index] + "\n"
    return final_code
