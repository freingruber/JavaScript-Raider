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



# The idea of this function is to find variations of Chromium issue 992914 (2019)
# When operations are performed on objects of a specific data type, the JS engine
# will create transition trees. E.g.: If operations are performed in the same order
# on a new variable, the map of the original variable can be reused for the new variable.
# This mutation strategy tries to find flaws in the transition tree creation.
# It therefore tries to call multiple operations in slightly different order on variables of
# the same type.
# For more details see my master thesis page 42 and 43.

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import mutators.database_operations as database_operations
import testcase_mergers.testcase_merger as testcase_merger
import javascript.js_helpers as js_helpers
import config as cfg
import random

# TODO: Is the call to .state_update_content_length missing? Or do I manually set the new content length?


# TODO:
# Currently my operations are just the operations from the database
# but I also need other operations such as setting a double/object in an array/property
# But I think my code can currently not handle these operation?
def mutation_stresstest_transition_tree(content, state):
    # utils.dbg_msg("Mutation operation: Stresstest transition tree")
    tagging.add_tag(Tag.MUTATION_STRESSTEST_TRANSITION_TREE1)

    line_number = testcase_mutators_helpers.get_random_line_number_to_insert_code(state)
    # utils.dbg_msg("Going to insert at line: %d" % line_number)

    possible_variables = testcase_mutators_helpers.get_all_available_variables_with_datatypes(state, line_number, exclude_undefined=True)
    supported_datatypes = js_helpers.get_all_variable_types_lower_case_which_I_can_currently_instantiate()
    real_possible_variables_with_datatype = []

    # Filter for variables with supported data types
    for variable_name in possible_variables:
        data_types = possible_variables[variable_name]
        for data_type in data_types:
            if data_type in supported_datatypes:
                real_possible_variables_with_datatype.append((variable_name, data_type))

    if len(real_possible_variables_with_datatype) == 0:
        return content, state   # do nothing because this mutation can't be performed in the selected line

    # Get a random variable to apply mutations:
    random_entry = utils.get_random_entry(real_possible_variables_with_datatype)
    (variable_name, variable_type) = random_entry

    other_variables_with_same_datatype = []
    for entry in real_possible_variables_with_datatype:
        (entry_variable_name, entry_variable_type) = entry
        if entry_variable_type == variable_type and entry_variable_name != variable_name:
            other_variables_with_same_datatype.append(variable_name)

    number_of_mutations = utils.get_random_int(cfg.mutation_stresstest_transition_tree_number_of_mutations_min,
                                               cfg.mutation_stresstest_transition_tree_number_of_mutations_max)
    number_other_variables = utils.get_random_int(cfg.mutation_stresstest_transition_tree_number_other_variables_min,
                                                  cfg.mutation_stresstest_transition_tree_number_other_variables_max)

    missing_other_variables = number_other_variables
    target_variable_names = []
    target_variable_names.append(variable_name)

    while missing_other_variables > 0:
        if len(other_variables_with_same_datatype) == 0:
            break
        if utils.likely(cfg.mutation_stresstest_transition_likelihood_use_new_variable):
            break

        random_additional_variable = utils.get_random_entry(other_variables_with_same_datatype)
        target_variable_names.append(random_additional_variable)
        other_variables_with_same_datatype.remove(random_additional_variable)
        missing_other_variables -= 1

    # Create required additional variables
    for i in range(missing_other_variables):
        (content, state, new_variable_name) = testcase_mutators_helpers.add_variable_with_specific_data_type_in_line(content, state, variable_type, line_number)
        line_number += 1
        target_variable_names.append(new_variable_name)


    # Make the order of the the target variables random so that the order of mutations is also random
    random.shuffle(target_variable_names)

    variable_name_with_additional_operations = utils.get_random_entry(target_variable_names)
    perform_additional_mutation_after_mutations = []
    perform_additional_mutation_after_mutations.append(utils.get_random_int(0, number_of_mutations - 1))
    if utils.likely(cfg.mutation_stresstest_transition_likelihood_second_additional_mutation):
        # in some cases perform 2nd additional operation
        perform_additional_mutation_after_mutations.append(utils.get_random_int(0, number_of_mutations - 1))


    for operation_number in range(number_of_mutations):
        perform_additional_operation_in_this_iteration = False
        if operation_number in perform_additional_mutation_after_mutations:
            perform_additional_operation_in_this_iteration = True
            perform_additional_operation_at_counter = utils.get_random_int(0, len(target_variable_names))

        # Get a new operation
        (operation_to_add, operation_state, variable_name_fake_ignore_it) = database_operations.get_random_variable_operation_from_database(content, state, line_number, "fake_variable_name", [variable_type])
        if operation_to_add is None:
            continue    # does this really occur? Maybe in a small database (?) but effectively it should never occur

        if utils.likely(cfg.mutation_stresstest_transition_likelihood_shuffle_order_of_mutations):
            # Sometimes also change the order of the mutations
            # TODO: Don't use here random, I think I should hide the used "random implementation" in utils.py?
            random.shuffle(target_variable_names)

        # And now apply the operation on all target variables
        counter = 0
        for variable_name in target_variable_names:
            if perform_additional_operation_in_this_iteration and counter == perform_additional_operation_at_counter:
                # Perform the additional operation
                (additional_operation_content, additional_operation_state, variable_name_fake_ignore_it) = database_operations.get_random_variable_operation_from_database(content, state, line_number, "fake_variable_name", [variable_type])
                if additional_operation_content is not None:
                    additional_operation_state_copy = additional_operation_state.deep_copy()
                    (content, state) = testcase_merger.merge_testcase2_into_testcase1_at_line(content, state, additional_operation_content, additional_operation_state_copy, line_number)
                    line_number += len(additional_operation_content.split("\n"))    # ensure the next iteration adds the next operation in the line after the current operation
                    content = content.replace("var_TARGET_", variable_name_with_additional_operations)      # rename the variable in the operation

            operation_state_copy = operation_state.deep_copy()
            (content, state) = testcase_merger.merge_testcase2_into_testcase1_at_line(content, state, operation_to_add, operation_state_copy, line_number)
            line_number += len(operation_to_add.split("\n"))    # ensure the next iteration adds the next operation in the line after the current operation
            content = content.replace("var_TARGET_", variable_name)     # rename the variable in the operation
            counter += 1

        if perform_additional_operation_in_this_iteration and counter == perform_additional_operation_at_counter:
            # Perform the additional operation
            (additional_operation_content, additional_operation_state, variable_name_fake_ignore_it) = database_operations.get_random_variable_operation_from_database(content, state, line_number, "fake_variable_name", [variable_type])
            if additional_operation_content is not None:
                additional_operation_state_copy = additional_operation_state.deep_copy()
                (content, state) = testcase_merger.merge_testcase2_into_testcase1_at_line(content, state, additional_operation_content, additional_operation_state_copy, line_number)
                line_number += len(additional_operation_content.split("\n"))    # ensure the next iteration adds the next operation in the line after the current operation
                content = content.replace("var_TARGET_", variable_name_with_additional_operations)  # rename the variable in the operation

    return content, state
