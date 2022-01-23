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



# Note:
# Since the inputs are standardized the code here assumes that either { or } is in one line
# e.g. there can't be lines where { and } are in the same line
# If code like: try { xxx } catch { yyyy} is in the testcase this function does not work
# Code must be in the form:
# try
# {
#   xxxx
# }
# catch
# {
#   yyyyy
# }


import minimizer.minimizer_helpers as minimizer_helpers


def remove_try_catch_blocks(code, required_coverage):
    new_code = code
    # Fix  "try {" code
    code_tmp = ""
    for line in new_code.split("\n"):
        tester = line.replace(" ", "").replace("\t", "")
        if "try{" in tester:
            line = line.replace("try", "try\n")
            code_tmp += line + "\n"
        else:
            code_tmp += line + "\n"
    new_code = code_tmp

    # Fix  "catch {" code
    code_tmp = ""
    for line in new_code.split("\n"):
        tester = line.replace(" ", "").replace("\t", "")
        if "catch{" in tester:
            line = line.replace("catch", "catch\n")
            code_tmp += line + "\n"
        else:
            code_tmp += line + "\n"
    new_code = code_tmp

    # Fix  "} catch" code
    code_tmp = ""
    for line in new_code.split("\n"):
        tester = line.replace(" ", "").replace("\t", "")
        if "}catch" in tester:
            line = line.replace("catch", "\ncatch")
            code_tmp += line + "\n"
        else:
            code_tmp += line + "\n"
    new_code = code_tmp

    # Fix added empty lines
    code_tmp = ""
    for line in new_code.split("\n"):
        if line.strip() == "":
            continue
        code_tmp += line + "\n"
    new_code = code_tmp

    if minimizer_helpers.does_code_still_trigger_coverage(new_code, required_coverage):
        code = new_code     # replacement is save

    # print("Adapted code:")
    # print(code)
    # input("waiter")

    lines = code.split("\n")
    lines_length = len(lines)

    keep_line = [True] * lines_length
    for possible_line_nr_to_remove in range(lines_length):
        line = lines[possible_line_nr_to_remove]
        try:
            if "try" in line:
                tmp_line_number = possible_line_nr_to_remove
                # print("possible_line_nr_to_remove: %d" % possible_line_nr_to_remove)
                # Find opening "{" of the try block
                while True:
                    line = lines[tmp_line_number]
                    if "{" in line:
                        break
                    else:
                        tmp_line_number += 1
                # print("tmp_line_number1: %d" % tmp_line_number)

                depth = -1
                # Now tmp_line_number points to the line where the "{" is found
                # Now find the "{" end of the try block
                while True:
                    line = lines[tmp_line_number]
                    if "{" in line:
                        depth += 1
                    if "}" in line:
                        if depth == 0:
                            break
                        depth -= 1
                        tmp_line_number += 1
                    else:
                        tmp_line_number += 1
                # print("tmp_line_number2: %d" % tmp_line_number)

                depth = 0
                # Now find the "catch"
                while True:
                    line = lines[tmp_line_number]
                    if "try" in line:
                        depth += 1
                    if "catch" in line:
                        if depth == 0:
                            break
                        depth -= 1
                        tmp_line_number += 1
                    else:
                        tmp_line_number += 1
                # print("tmp_line_number3: %d" % tmp_line_number)

                # Now find the "{" of the catch block
                while True:
                    line = lines[tmp_line_number]
                    if "{" in line:
                        break
                    else:
                        tmp_line_number += 1
                # print("tmp_line_number4: %d" % tmp_line_number)

                depth = -1
                # Now find the "}" if the catch block
                while True:
                    line = lines[tmp_line_number]
                    if "{" in line:
                        depth += 1
                    if "}" in line:
                        if depth == 0:
                            break
                        depth -= 1
                        tmp_line_number += 1
                    else:
                        tmp_line_number += 1
                # print("tmp_line_number5: %d" % tmp_line_number)

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
                # print("possible_line_nr_to_remove: %d" % possible_line_nr_to_remove)
                # print(code_with_removed_lines)
                # print("-------------------")
                # input("waiter")
                if minimizer_helpers.does_code_still_trigger_coverage(code_with_removed_lines, required_coverage):
                    for x in range(possible_line_nr_to_remove, tmp_line_number + 1):
                        keep_line[x] = False   # The line is not important because it could be minimized away
        except:
            pass    # ignore invalid accesses in malformed testcases

    final_code = ""
    for line_index in range(lines_length):
        if keep_line[line_index]:
            final_code += lines[line_index] + "\n"
    return final_code
