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


def remove_semicolon_lines(code_to_minimize, required_coverage):
    # First attempt is to remove multiple occurrences of a semicolon after each other
    # E.g.:
    # ;;;1+2;;
    # Will become:
    # ;1+2;
    tmp = code_to_minimize
    while ";;" in tmp:
        tmp = tmp.replace(";;", ";")

    if tmp != code_to_minimize:
        if standardizer_helpers.does_code_still_trigger_coverage(tmp, required_coverage):
            code_to_minimize = tmp  # replacement worked


    # Now remove empty lines which just contain ";"
    # And also remove the trailing ";" from lines like:
    # ;1+2
    # =>
    # 1+2
    tmp = ""
    for line in code_to_minimize.split("\n"):
        if line.strip() == ";":
            continue    # skip these lines
        elif line.startswith(";"):
            tmp += line[1:] + "\n"      # remove the ";"
        else:
            tmp += line + "\n"

    if tmp != code_to_minimize:
        if standardizer_helpers.does_code_still_trigger_coverage(tmp, required_coverage):
            code_to_minimize = tmp  # replacement worked

    return code_to_minimize
