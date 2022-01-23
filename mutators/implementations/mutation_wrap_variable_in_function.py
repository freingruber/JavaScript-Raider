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



# This mutation wraps a variable in a function. The assumption is that this
# can maybe trigger deeper paths in the compiler.
#
# Example:
# let x = var_1_
#
# =>
#
# let r0 = () => var_1_; let x = r0()
#
# from: https://github.com/tunz/js-vuln-db/blob/master/chakra/CVE-2017-11802.md
#
# I simplified it to:
# let x = (() => var_1_)()


import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


def mutation_wrap_variable_in_function(content, state):
    # utils.dbg_msg("Mutation operation: Wrap variable in function")
    tagging.add_tag(Tag.MUTATION_WRAP_VARIABLE_IN_FUNCTION1)

    positions_of_variables = testcase_mutators_helpers.get_positions_of_all_variables_in_testcase_without_assignment(content)
    if len(positions_of_variables) == 0:
        tagging.add_tag(Tag.MUTATION_WRAP_VARIABLE_IN_FUNCTION2_DO_NOTHING)
        return content, state       # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions_of_variables)
    original_variable = content[start_idx:end_idx + 1]
    new_code = "(() => %s)()" % original_variable

    new_content = content[:start_idx] + new_code + content[end_idx + 1:]
    added_length = len(new_code) - len(original_variable)
    state.state_update_content_length(added_length, new_content)

    return new_content, state
