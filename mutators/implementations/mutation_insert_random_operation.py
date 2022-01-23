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
from mutators.implementations.mutation_insert_random_operation_at_specific_line import mutation_insert_random_operation_at_specific_line


def mutation_insert_random_operation(content, state):
    # utils.dbg_msg("Mutation operation: Insert random operation")
    tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION1)

    random_line_number = testcase_mutators_helpers.get_random_line_number_to_insert_code(state)

    # possible_lines = state.lines_where_code_can_be_inserted + state.lines_where_code_with_coma_can_be_inserted
    # random_line_number = utils.get_random_entry(possible_lines)
    # utils.dbg_msg("Going to insert at line: %d" % random_line_number)
    # if random_line_number in state.lines_where_code_can_be_inserted:
    #    end_line_with = ";"
    # else:
    #    end_line_with = ","

    return mutation_insert_random_operation_at_specific_line(content, state, random_line_number)
