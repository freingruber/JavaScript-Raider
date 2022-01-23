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



# This mutation strategy tries to materialize values to trigger deeper
# paths in the compiler. Materialization basically means that a value is wrapped
# in an object. Then, during compilation, one of the phases "dematerializes" the object/value.
# This means that specific optimizations can't be performed before the dematerialization happens.
# And that therefore optimizations after dematerialization will be triggered.

# Example:
# Object.is(Math.expm1(x), -0);
#
# =>
#
# var var_22_ = {a: -0};
# Object.is(Math.expm1(x), var_22_.a);
#
# => To simplify stuff I create:
# Object.is(Math.expm1(x), {_:-0}._);
#
# This example was from Chromium issue/exploit 880208

# TODO: Check if this really leads to materialization / dematerialization!


import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import testcase_helpers


def mutation_materialize_values(content, state):
    # utils.dbg_msg("Mutation operation: Materialize values")
    tagging.add_tag(Tag.MUTATION_MATERIALIZE_VALUE1)

    lines = content.split("\n")
    positions_of_numbers = testcase_mutators_helpers.get_positions_of_all_numbers_in_testcase(content)

    positions_of_numbers_filtered = []
    for entry in positions_of_numbers:
        (start_idx, end_idx) = entry
        line_number = testcase_helpers.content_offset_to_line_number(lines, start_idx)
        line = lines[line_number]
        if "function " in line or "function\t" in line or "function*" in line:
            continue    # don't inject into function definitions because I can't add a line before the definition without destroying the syntax
        positions_of_numbers_filtered.append(entry)

    if len(positions_of_numbers_filtered) == 0:
        tagging.add_tag(Tag.MUTATION_MATERIALIZE_VALUE2_DO_NOTHING)
        return content, state   # nothing to materialize

    (start_idx, end_idx) = utils.get_random_entry(positions_of_numbers_filtered)
    original_value = content[start_idx:end_idx + 1]
    # utils.dbg_msg("Going to materialize value which starts at 0x%x and ends at 0x%x; value: %s" % (start_idx, end_idx, original_value))

    materialized_object = "({_:%s})._" % original_value

    new_content = content[:start_idx] + materialized_object + content[end_idx + 1:]
    added_length = len(materialized_object) - len(original_value)
    state.state_update_content_length(added_length, new_content)

    return new_content, state
