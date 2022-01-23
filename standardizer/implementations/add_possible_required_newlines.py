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


def add_possible_required_newlines(code_to_minimize, required_coverage):
    tmp = code_to_minimize.replace(";", ";\n").replace("\n\n", "\n")
    if tmp != code_to_minimize:
        if standardizer_helpers.does_code_still_trigger_coverage(tmp, required_coverage):
            code_to_minimize = tmp  # replacement worked
    return code_to_minimize
