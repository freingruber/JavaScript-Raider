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



import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


# Important: the operation should just have EXACTLY ONE LINE
# Other code depends on this which updates states / line numbers
# If a sequence of operations should be added another function must be used
def mutation_insert_random_operation_at_specific_line(content, state, line_number):
    tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION_AT_SPECIFIC_LINE1)
    line_to_add = testcase_mutators_helpers.get_random_operation(content, state, line_number)

    # Now just insert the new line to the testcase & state
    lines = content.split("\n")
    lines.insert(line_number, line_to_add)
    new_content = "\n".join(lines)

    state.state_insert_line(line_number, new_content, line_to_add)
    return new_content, state
