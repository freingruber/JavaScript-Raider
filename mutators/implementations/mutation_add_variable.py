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
import javascript.js_helpers as js_helpers


# This mutation adds a new variable to the testcase which can be used to
def mutation_add_variable(content, state):
    # utils.dbg_msg("Mutation operation: Add variable")
    tagging.add_tag(Tag.MUTATION_ADD_VARIABLE1)

    random_line_number = testcase_mutators_helpers.get_random_line_number_to_insert_code(state, maybe_remove_line_zero=False)
    random_data_type_lower_case = js_helpers.get_random_variable_type_lower_case_which_I_can_currently_instantiate()

    # random_data_type_lower_case = "string" # debugging code

    (new_content, new_state, new_variable_name) = testcase_mutators_helpers.add_variable_with_specific_data_type_in_line(content, state, random_data_type_lower_case, random_line_number)
    return new_content, new_state
