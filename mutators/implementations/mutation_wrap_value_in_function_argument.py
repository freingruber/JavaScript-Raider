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



# This mutation wraps a value in a function. The assumption is that this
# can maybe trigger deeper paths in the compiler.
#
# Example:
# let x = 1337
#
# =>
#
# function inlinee() {
#    return inlinee.arguments[0];
# }
# let x = inlinee(1337)
#
# => Simplified to:
# let x = (function _() {return _.arguments[0]})(1337)


import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


def mutation_wrap_value_in_function_argument(content, state):
    # utils.dbg_msg("Mutation operation: Wrap value in function argument")
    tagging.add_tag(Tag.MUTATION_WRAP_VALUE_IN_FUNCTION_ARGUMENT1)

    positions_of_numbers = testcase_mutators_helpers.get_positions_of_all_numbers_in_testcase(content)
    if len(positions_of_numbers) == 0:
        tagging.add_tag(Tag.MUTATION_WRAP_VALUE_IN_FUNCTION_ARGUMENT2_DO_NOTHING)
        return content, state  # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions_of_numbers)
    original_number = content[start_idx:end_idx + 1]
    new_code = "(function _() {return _.arguments[0]})(%s)" % original_number

    new_content = content[:start_idx] + new_code + content[end_idx + 1:]
    added_length = len(new_code) - len(original_number)
    state.state_update_content_length(added_length, new_content)

    return new_content, state
