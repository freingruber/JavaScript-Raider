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


def mutation_change_proto(content, state):
    # utils.dbg_msg("Mutation operation: Change proto")
    tagging.add_tag(Tag.MUTATION_CHANGE_PROTO1)

    # TODO
    # Currently I don't return in "lhs" or "rhs" the __proto__ of a function
    # So code like this:
    # Math.abs.__proto__ = Math.sign.__proto__
    # Can currently not be created. Is this required?
    # => has such code an effect?

    random_line_number = testcase_mutators_helpers.get_random_line_number_to_insert_code(state)
    (start_line_with, end_line_with) = testcase_mutators_helpers.get_start_and_end_line_symbols(state, random_line_number, content)

    (lhs, code_possibilities) = testcase_mutators_helpers.get_proto_change_lhs(state, random_line_number)
    rhs = testcase_mutators_helpers.get_proto_change_rhs(state, random_line_number, code_possibilities)
    new_code_line = "%s%s.__proto__ = %s%s" % (start_line_with, lhs, rhs, end_line_with)

    # Now just insert the new line to the testcase & state
    lines = content.split("\n")
    lines.insert(random_line_number, new_code_line)
    new_content = "\n".join(lines)

    state.state_insert_line(random_line_number, new_content, new_code_line)
    return new_content, state
