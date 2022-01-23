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



import native_code.coverage_helpers as coverage_helpers

tmp_coverage_filepath = None


# TODO: Can I remove this call and get the value from cfg?
def initialize(current_coverage_filepath):
    global tmp_coverage_filepath
    tmp_coverage_filepath = current_coverage_filepath


# TODO: Move this function maybe into >coverage_helpers.py< ?
def does_code_still_trigger_coverage(new_code, required_coverage):
    global tmp_coverage_filepath
    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(new_code, tmp_coverage_filepath)
    for coverage_entry in required_coverage:
        if coverage_entry not in triggered_coverage:
            return False
    return True
