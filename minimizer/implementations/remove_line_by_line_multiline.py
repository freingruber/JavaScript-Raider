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


def remove_line_by_line_multiline(code, required_coverage, start_symbol, end_symbol):
    lines = code.split("\n")
    lines_length = len(lines)

    keep_line = [True] * lines_length
    for possible_line_nr_to_remove in range(lines_length):
        line = lines[possible_line_nr_to_remove]
        # print("Line number: %d" % possible_line_nr_to_remove)
        if start_symbol in line:
            count_open = line.count(start_symbol)
            count_close = line.count(end_symbol)
            if count_open > count_close:
                # print("here1")
                diff = count_open - count_close
                # print("Diff is: %d" % diff)
                # go find end line (most likely next line)
                tmp_line_number = possible_line_nr_to_remove
                while True:
                    tmp_line_number += 1
                    if tmp_line_number >= lines_length:
                        tmp_line_number -= 1
                        break
                    if keep_line[tmp_line_number] is False:
                        continue
                    new_line = lines[tmp_line_number]
                    count_new_open = new_line.count(start_symbol)
                    count_new_close = new_line.count(end_symbol)
                    diff_new = count_new_open - count_new_close
                    # print("diff_new is: %d" % diff_new)
                    diff = diff + diff_new
                    # print("diff for next iteration: %d" % diff)
                    if diff <= 0:
                        # found the end!
                        break

                # print("End line number: %d" % tmp_line_number)
                code_with_removed_lines = ""
                for line_index in range(lines_length):
                    if line_index == possible_line_nr_to_remove:
                        continue    # skip the add
                    if possible_line_nr_to_remove < line_index <= tmp_line_number:
                        continue
                    if keep_line[line_index]:
                        code_with_removed_lines += lines[line_index] + "\n"

                # print("Attempting:")
                # print(code_with_removed_lines)
                # print("-------------------")
                if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_lines, required_coverage):
                    for x in range(possible_line_nr_to_remove, tmp_line_number + 1):
                        keep_line[x] = False   # The line is not important because it could be minimized away

    final_code = ""
    for line_index in range(lines_length):
        if keep_line[line_index]:
            final_code += lines[line_index] + "\n"
    return final_code
