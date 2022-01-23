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
import testcase_mergers.testcase_merger as testcase_merger
import mutators.database_operations as database_operations


def mutation_insert_random_operation_from_database_at_specific_line(content, state, line_number, number_of_operations):
    tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE1)

    # old code?
    # (operation_to_add, operation_state, variable_name) = get_random_operation_from_database(content, state, line_number)

    # First decide if generic operations or variable operations (and for which variable) should be applied:

    # tagging.add_tag(Tag.GET_RANDOM_OPERATION_FROM_DATABASE1)
    possible_variables = testcase_mutators_helpers.get_all_available_variables_with_datatypes(state, line_number, exclude_undefined=True)
    if len(possible_variables) == 0 or utils.likely(0.04):
        tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE3)
        generic_operation = True
    else:
        tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE4)
        generic_operation = False
        random_variable_name = utils.get_random_entry(list(possible_variables))
        data_types_of_random_variable = possible_variables[random_variable_name]

    # print("Testcase initial:")
    # print(content)
    # print("State initial:")
    # print(state)
    # print("\n")
    for operation_number in range(number_of_operations):
        if generic_operation:
            (operation_to_add, operation_state, variable_name) = database_operations.get_random_operation_from_database_without_a_variable(content, state, line_number)
        else:
            (operation_to_add, operation_state, variable_name) = database_operations.get_random_variable_operation_from_database(content, state, line_number, random_variable_name, data_types_of_random_variable)

        if operation_to_add is None:
            tagging.add_tag(Tag.MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE2_DO_NOTHING)
        else:
            # print("Operation to add:")
            # print(operation_to_add)
            # print("Operation to add state:")
            # print(operation_state)
            # print("\n\n")
            (content, state) = testcase_merger.merge_testcase2_into_testcase1_at_line(content, state, operation_to_add, operation_state, line_number)

            # print("Testcase after merge:")
            # print(content)
            # print("State after merge:")
            # print(state)
            # print("\n")

            line_number += len(operation_to_add.split("\n"))    # ensure the next iteration adds the next operation in the line after the current operation

            if variable_name is not None:
                # Now rename the variable
                content = content.replace("var_TARGET_", variable_name)

                # Is it maybe required to make >variable_name< also available in the code lines from the operation?
                # because var_TARGET_ was not in the state, the operation state didn't encode in which lines var_TARGET_ is available...
                # it should basically be everywhere available because it's something like:
                # {
                # ...
                # var_TARGET_ = ...
                # operation1
                # ...
                # }
                # => therefore var_TARGET_ must be available in every code line of operation1
                # same for arrays => if it's an array, I must also update the array length fields
                # EDIT:
                # This is already implemented! the merge will make all variables which are available in the testcase in the line
                # before the operation also available in the full operation
                # => it therefore already works

    # TODO:
    # Now start to change two variable types:
    # e.g. if testcase1 has variable1 and testcase2 has variable2
    # and variable1 and variable2 have the same datatype
    # => Then change one or more occurrences in testcase2 (the operation) of variable2 to variable1?
    # => this helps to better "mix" the operation into the testcase

    return content, state
