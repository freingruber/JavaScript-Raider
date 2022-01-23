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


def mutation_if_wrap_line(content, state):
    utils.dbg_msg("Mutation operation: IF-wrap code line")
    tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE1)

    # Simple mutation to add IF:
    # console.log("code")
    # =>
    # if (1) console.log("code")

    # TODO: This can lead to problems if it injects inside a "(" and ")" or inside a "{" and "}"
    # For example, if I create  an object over multiple lines and it injects the if in the property
    # definitions...

    lines = content.split("\n")
    possibilities_top_insert_if = testcase_mutators_helpers.get_code_lines_without_forbidden_words(lines)
    if len(possibilities_top_insert_if) == 0:
        tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE2_DO_NOTHING)
        return content, state   # nothing to modify

    random_line_number = utils.get_random_entry(possibilities_top_insert_if)
    old_line = lines[random_line_number]

    code_to_append = "if (1) "

    if utils.likely(0.1):   # 10% of cases try to use a variable instead of the "1"

        possible_boolean_variables = []
        possible_variables = []
        # Check if there is a boolean variable available!
        for variable_name in state.variable_types:
            for entry in state.variable_types[variable_name]:
                (tmp_line_number, variable_type) = entry
                if tmp_line_number == random_line_number and variable_type == "boolean":
                    possible_boolean_variables.append(variable_name)
                elif tmp_line_number == random_line_number:
                    possible_variables.append(variable_name)

        if len(possible_boolean_variables) != 0:
            tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE3)
            random_boolean_variable = utils.get_random_entry(possible_boolean_variables)
            code_to_append = "if (%s) " % random_boolean_variable
        else:
            # no boolean variables, then just use any other available variable...
            if len(possible_variables) != 0:
                tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE4)
                random_variable = utils.get_random_entry(possible_variables)
                code_to_append = "if (%s) " % random_variable
            else:
                # Note:
                # Previously I just set the condition to false, however
                # this resulted in 80% of the cases in exceptions and just 20% were successful
                # From 1000 executed cases it resulted 2 times in new coverage
                # I therefore keep the code but make it very unlikely to occur
                if utils.likely(0.01):
                    tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE5_MANY_EXCEPTIONS)
                    code_to_append = "if (false) "      # make it just false (=> line will not be executed)
                else:
                    tagging.add_tag(Tag.MUTATION_IF_WRAP_LINE6)
                    code_to_append = "if (true) "

    new_line = code_to_append + old_line
    lines[random_line_number] = new_line

    new_content = "\n".join(lines)

    added_length = len(code_to_append)
    state.state_update_content_length(added_length, new_content)

    return new_content, state
