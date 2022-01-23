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



import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
from mutators.implementations.mutation_add_variable import mutation_add_variable
from mutators.implementations.mutation_change_proto import mutation_change_proto
from mutators.implementations.mutation_change_prototype import mutation_change_prototype
from mutators.implementations.mutation_change_two_variables_of_same_type import mutation_change_two_variables_of_same_type
from mutators.implementations.mutation_do_nothing import mutation_do_nothing        # only used for testing
from mutators.implementations.mutation_duplicate_line import mutation_duplicate_line
from mutators.implementations.mutation_enforce_call_node import mutation_enforce_call_node
from mutators.implementations.mutation_for_wrap_line import mutation_for_wrap_line
from mutators.implementations.mutation_for_wrap_operations import mutation_for_wrap_operations
from mutators.implementations.mutation_if_wrap_line import mutation_if_wrap_line
from mutators.implementations.mutation_if_wrap_operations import mutation_if_wrap_operations
from mutators.implementations.mutation_insert_multiple_random_operations_from_database import mutation_insert_multiple_random_operations_from_database
from mutators.implementations.mutation_insert_random_operation import mutation_insert_random_operation
from mutators.implementations.mutation_insert_random_operation_from_database import mutation_insert_random_operation_from_database
from mutators.implementations.mutation_materialize_values import mutation_materialize_values
from mutators.implementations.mutation_modify_number import mutation_modify_number
from mutators.implementations.mutation_modify_string import mutation_modify_string
from mutators.implementations.mutation_move_operation_around import mutation_move_operation_around
from mutators.implementations.mutation_remove_line import mutation_remove_line
from mutators.implementations.mutation_replace_number import mutation_replace_number
from mutators.implementations.mutation_replace_string import mutation_replace_string
from mutators.implementations.mutation_stresstest_transition_tree import mutation_stresstest_transition_tree
from mutators.implementations.mutation_while_wrap_line import mutation_while_wrap_line
from mutators.implementations.mutation_wrap_string_in_function import mutation_wrap_string_in_function
from mutators.implementations.mutation_wrap_string_in_function_argument import mutation_wrap_string_in_function_argument
from mutators.implementations.mutation_wrap_value_in_function import mutation_wrap_value_in_function
from mutators.implementations.mutation_wrap_value_in_function_argument import mutation_wrap_value_in_function_argument
from mutators.implementations.mutation_wrap_variable_in_function import mutation_wrap_variable_in_function
from mutators.implementations.mutation_wrap_variable_in_function_argument import mutation_wrap_variable_in_function_argument


# Mutations for development:
# mutation_operations_list = [
#     (1, mutation_do_nothing),
# ]

# late_mutation_operations_list = [
#     (1, mutation_if_wrap_operations),
# ]


# List of all mutations which will be performed
# A mutation function receives one testcase and the associated state and must return
# the modified testcase with the modified state
# E.g. if the mutation removes a line, the line number should be updated in the associated state file
# This is important so that subsequent mutations have a correct state file
# The first number is the frequency, e.g. 3 means the function will be inserted 3 times into the final list
# (it's 3 times more frequent executed than functions with a 1)
mutation_operations_list = [
    (7, mutation_insert_random_operation),
    (12, mutation_insert_random_operation_from_database),
    (7, mutation_insert_multiple_random_operations_from_database),
    (5, mutation_add_variable),
    (2, mutation_stresstest_transition_tree),
    ]


# TODO: The configuration needs a lot of fine tuning: Some mutations should be done way more frequently than others
late_mutation_operations_list = [
    (15, mutation_change_two_variables_of_same_type),        # very common => it's important to mix testcases & operations with testcases
    (10, mutation_replace_number),
    (10, mutation_modify_number),
    (10, mutation_move_operation_around),
    (7, mutation_materialize_values),   # TODO: also materialize values and function calls and variables! like my master thesis page 96
    (7, mutation_enforce_call_node),
    (4, mutation_replace_string),
    (4, mutation_modify_string),
    (3, mutation_duplicate_line),
    (3, mutation_change_prototype),
    (3, mutation_change_proto),
    (1, mutation_remove_line),           # make this very uncommon
    (1, mutation_if_wrap_line),
    (1, mutation_for_wrap_line),
    (1, mutation_while_wrap_line),
    (1, mutation_wrap_value_in_function),        # refactor all of the following mutations + also implement them for function calls like var_1_.someFunction() to be wrapped but also Math.sign(..) and other function calls or global variables!
    (1, mutation_wrap_value_in_function_argument),
    (1, mutation_wrap_string_in_function),
    (1, mutation_wrap_string_in_function_argument),
    (1, mutation_wrap_variable_in_function),
    (1, mutation_wrap_variable_in_function_argument),
    (3, mutation_if_wrap_operations),
    (3, mutation_for_wrap_operations),
]

# Create the mutations based on the count:
mutation_operations = []
for entry in mutation_operations_list:
    (count, mutation_function) = entry
    for i in range(count):
        mutation_operations.append(mutation_function)

late_mutation_operations = []
for entry in late_mutation_operations_list:
    (count, mutation_function) = entry
    for i in range(count):
        late_mutation_operations.append(mutation_function)



def randomly_mutate_js_sample(content, state):
    global mutation_operations
    mutation_operation_func = utils.get_random_entry(mutation_operations)
    state = state.deep_copy()
    return mutation_operation_func(content, state)


def randomly_mutate_late_js_sample(content, state):
    global mutation_operations
    mutation_operation_func = utils.get_random_entry(late_mutation_operations)
    state = state.deep_copy()
    return mutation_operation_func(content, state)


# This function is mostly used combined with testcases to add array-operations
# at callback locations
def insert_random_array_operation_at_specific_line(content, state, line_number):
    tagging.add_tag(Tag.INSERT_RANDOM_ARRAY_OPERATION_AT_SPECIFIC_LINE1)

    possible_arrays = state.get_available_arrays_in_line_with_lengths(line_number)

    array_variable_names = list(possible_arrays.keys())
    if "arguments" in array_variable_names:
        array_variable_names.remove("arguments")

    if len(array_variable_names) == 0:
        tagging.add_tag(Tag.INSERT_RANDOM_ARRAY_OPERATION_AT_SPECIFIC_LINE2_DO_NOTHING)
        return None, None  # do nothing because there are no arrays

    random_array_name = utils.get_random_entry(array_variable_names)
    random_array_lengths_list = possible_arrays[random_array_name]
    line_to_add = testcase_mutators_helpers.get_random_array_operation(content, state, line_number, random_array_name, random_array_lengths_list)

    # Now just insert the new line to the testcase & state
    lines = content.split("\n")
    lines.insert(line_number, line_to_add)
    new_content = "\n".join(lines)

    state.state_insert_line(line_number, new_content, line_to_add)
    return new_content, state


def disable_database_based_mutations():
    global mutation_operations
    utils.msg("[i] Going to disable all mutations which depend on databases!")

    utils.remove_all_from_list(mutation_operations, mutation_insert_random_operation_from_database)
    utils.remove_all_from_list(mutation_operations, mutation_insert_multiple_random_operations_from_database)
    utils.remove_all_from_list(mutation_operations, mutation_stresstest_transition_tree)
