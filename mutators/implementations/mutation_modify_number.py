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



# This mutation strategy tries to modify a number.
# Modifying means that a number is added to the start or end.
# (On the other hand, the replace number mutation strategy would replace
# a number which means the original number can't be found in the result).
# Example:
# var var_1_ = -123
#
# =>
#
# var var_1_ = -Math.round(-0.1)>>123
#
# or
#
# var var_1_ = -123%(-~(~(-0)))+(-0))

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js


def mutation_modify_number(content, state):
    # utils.dbg_msg("Mutation operation: Modify number")
    tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER1)

    prefix = ""

    positions_of_numbers = testcase_mutators_helpers.get_positions_of_all_numbers_in_testcase(content)
    if len(positions_of_numbers) == 0:
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER2_DO_NOTHING)
        return content, state   # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions_of_numbers)

    if utils.get_random_bool():
        # add stuff in front of string
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER3)
        pos_to_insert = start_idx
    else:
        # add stuff after the string
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER4)
        pos_to_insert = end_idx + 1
    # utils.dbg_msg("Modify number at offset 0x%x" % (pos_to_insert))

    possibilities = [1, 2, 3]
    random_choice = utils.get_random_entry(possibilities)
    if random_choice == 1:
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER5)
        new_number = js.get_special_value()
    elif random_choice == 2:
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER6)
        new_number = js.get_int()
    else:
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER7)
        new_number = js.get_double()

    if utils.likely(0.2):
        tagging.add_tag(Tag.MUTATION_MODIFY_NUMBER8)
        (new_number, prefix) = testcase_mutators_helpers.decompose_number(new_number)

    random_math_operation = js.get_random_js_math_operation()   # something like "+" or "*""

    if pos_to_insert == start_idx:
        # insert in front
        added_content = new_number + random_math_operation
    else:
        # insert after
        added_content = random_math_operation + new_number

    added_length = len(added_content)

    new_content = content[:pos_to_insert] + added_content + content[pos_to_insert:]
    state.state_update_content_length(added_length, new_content)

    if prefix != "":
        # Prefix requires a state update to update all code lines
        new_content = prefix + new_content
        state.state_insert_line(0, new_content, prefix.strip())

    return new_content, state
