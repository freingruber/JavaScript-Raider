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



# This mutation strategy replaces a random number with another randomly generated number.

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js


def mutation_replace_number(content, state):
    # utils.dbg_msg("Mutation operation: Replace number")
    tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER1)

    prefix = ""
    was_minus_zero = False

    positions_of_numbers = testcase_mutators_helpers.get_positions_of_all_numbers_in_testcase(content)
    if len(positions_of_numbers) == 0:
        tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER2_DO_NOTHING)
        return content, state  # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions_of_numbers)
    # utils.dbg_msg("Replacing number which starts at 0x%x and ends at 0x%x" % (start_idx, end_idx))

    if utils.likely(0.2):   # 20% of cases
        tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER3)
        original_number = content[start_idx:end_idx + 1]
        if original_number == "-0":
            was_minus_zero = True
        (random_number, prefix) = testcase_mutators_helpers.decompose_number(original_number)
    else:
        if utils.likely(0.1):       # 10% of cases
            tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER4)
            random_number = js.get_double()
        else:
            if utils.likely(0.5):
                tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER5)
                random_number = js.get_int()
                if utils.likely(0.1):   # in 10% of cases
                    tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER6)
                    (random_number, prefix) = testcase_mutators_helpers.decompose_number(random_number)     # also decompose the self created number
            else:
                tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER7)
                random_number = js.get_special_value()

    if random_number[0] != "-":     # only if the number is not already negative
        if utils.likely(0.2) and was_minus_zero is False:   # 20% of cases make it negative
            try:
                if content[start_idx - 1] != "-":           # if it's not already negative.
                    tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER8)
                    random_number = "-" + random_number     # make it negative
            except:
                tagging.add_tag(Tag.MUTATION_REPLACE_NUMBER9_SHOULD_NEVER_OCCUR)
                random_number = "-" + random_number         # make it negative

    new_content = content[:start_idx] + random_number + content[end_idx + 1:]
    added_length = len(random_number) - (end_idx - start_idx + 1)       # can also become negative, but that's ok
    state.state_update_content_length(added_length, new_content)

    if prefix != "":
        # Prefix requires a state update to update all code lines
        new_content = prefix + new_content
        state.state_insert_line(0, new_content, prefix.strip())

    return new_content, state
