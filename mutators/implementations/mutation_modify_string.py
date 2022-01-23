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



# This mutation strategy tries to modify a string.
# Modifying means that a string is added to the start or end.
# (On the other hand, the replace string mutation strategy would replace
# a string which means the original string can't be found in the result).
# Example:
# let var_1_ = {style: "percent"}
#
# =>
#
# style: "0001-01-01T01:01+-s_0b:01.001Z"+"percent"
#
# => The "0001-01-01T01:01+-s_0b:01.001Z" is the new string which was added
# at the start of the original string


import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js


def mutation_modify_string(content, state):
    # utils.dbg_msg("Mutation operation: Modify string")
    tagging.add_tag(Tag.MUTATION_MODIFY_STRING1)

    positions_of_strings = testcase_mutators_helpers.get_positions_of_all_strings_in_testcase(content)
    if len(positions_of_strings) == 0:
        tagging.add_tag(Tag.MUTATION_MODIFY_STRING2_DO_NOTHING)
        return content, state   # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions_of_strings)

    if utils.get_random_bool():
        # add stuff in front of string
        tagging.add_tag(Tag.MUTATION_MODIFY_STRING3)
        pos_to_insert = start_idx
    else:
        # add stuff after the string
        tagging.add_tag(Tag.MUTATION_MODIFY_STRING4)
        pos_to_insert = end_idx+1

    # utils.dbg_msg("Modifying string at position 0x%x" % (pos_to_insert))
    if utils.get_random_bool():
        tagging.add_tag(Tag.MUTATION_MODIFY_STRING5)
        random_string = js.get_str()
    else:
        # only 1 character
        tagging.add_tag(Tag.MUTATION_MODIFY_STRING6)
        random_char = utils.get_random_entry(js.possible_chars_all)
        random_string = "\""+random_char+"\""

    if pos_to_insert == start_idx:
        # insert in front
        random_string = random_string+"+"
    else:
        # insert after
        random_string = "+"+random_string

    # utils.dbg_msg("New random string: %s" % (random_string))

    added_content = random_string
    added_length = len(added_content)

    new_content = content[:pos_to_insert] + added_content + content[pos_to_insert:]
    state.state_update_content_length(added_length, new_content)

    return new_content, state
