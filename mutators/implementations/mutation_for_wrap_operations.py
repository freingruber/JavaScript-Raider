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


def mutation_for_wrap_operations(content, state):
    tagging.add_tag(Tag.MUTATION_FOR_WRAP_OPERATIONS1)

    lines = content.split("\n")
    number_of_lines = len(lines)

    (start_line, end_line) = testcase_mutators_helpers.get_start_and_end_lines_to_wrap(content, state, lines, number_of_lines)
    if start_line == -1 or end_line == -1:
        # could not find a place to wrap code
        return content, state   # unmodified testcase

    # Get a variable:
    state.number_variables = state.number_variables + 1
    next_free_variable_id = state.number_variables
    new_variable_name = "var_%d_" % next_free_variable_id

    number_of_iterations = utils.get_random_int(0, 60)
    code_prefix = "for (var %s = 0; %s < %d; ++%s) {" % (new_variable_name, new_variable_name, number_of_iterations, new_variable_name)
    code_suffix = "}"

    # TODO make the >new_variable_name< available in the state in the new code lines
    # Important: Attention for the line numbers because at that point the >code_prefix< line was not added

    return testcase_mutators_helpers.wrap_codelines(state, lines, start_line, end_line, code_prefix, code_suffix)
