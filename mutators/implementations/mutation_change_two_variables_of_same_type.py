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
import itertools

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


# TODO and what if a property has a variable type and a variable?
# => can I switch both?
# TODO: If I change 2 arrays, they must have at least approx same length?
# @profile
def mutation_change_two_variables_of_same_type(content, state):
    # utils.dbg_msg("Mutation operation: Change two variables of same type")
    tagging.add_tag(Tag.MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE1)

    lines = content.split("\n")
    lines_length = len(lines)

    #  if variable_name1 == "arguments" or variable_name2 == arguments:
    skip_default_variables = True
    if utils.likely(0.1):
        # in 10% of cases also use default variables like "this", "arguments" and so on
        skip_default_variables = False

    # Find which variables can be exchanged (have same type) in which lines
    possibilities = set()
    mapping_datatype_and_line_to_variable_name = dict()     # key is something like "array_2" which means all entries are arrays in line 2
    for variable_name in state.variable_types:
        if skip_default_variables:
            if variable_name == "arguments" or variable_name == "this" or variable_name == "new.target":
                continue    # skip it
        if variable_name.startswith("func_"):
            continue
        for entry1 in state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry1
            if variable_type == "undefined" or variable_type == "function":
                continue
            if entry_line_number == lines_length:
                continue    # this would be a replace after the last line which is not possible because there is no such line (this data type is for append operations)
            key_value = "%s_%d" % (variable_type, entry_line_number)
            if key_value not in mapping_datatype_and_line_to_variable_name:
                mapping_datatype_and_line_to_variable_name[key_value] = []
            mapping_datatype_and_line_to_variable_name[key_value].append(variable_name)
    for key_value in mapping_datatype_and_line_to_variable_name:
        entries = mapping_datatype_and_line_to_variable_name[key_value]
        if len(entries) <= 1:
            continue
        # At least 2 entries => 2 variables which can be changed
        parts = key_value.rsplit("_", 1)
        data_type = parts[0]
        line_number = int(parts[1], 10)
        for combination in itertools.combinations(entries, 2):
            (variable_name1, variable_name2) = combination
            # In the line the data types are the same of both variables
            # If in the line e.g. "var_1_" is used it can be replaced by "var_2_"
            possibilities.add((variable_name1, variable_name2, line_number))
            possibilities.add((variable_name2, variable_name1, line_number))

    # Now iterate through all possible lines and check if the first variable is in this line
    # If yes, the variable can be replaced with the 2nd variable
    # Explanation: If the variables don't occur in the line, it would not make sense to replace them, because there is nothing to replace
    possibilities_filtered = []
    for entry in possibilities:
        (variable_name1, variable_name2, line_number) = entry
        try:
            associated_line = lines[line_number]
        except:
            # Debugging code, should never occur but can occur when I have a bug in my code to merge states

            # TODO: I think this currently really occurs because of a bug with string operations
            # some strings have strange unicode characters which fuck up my testcase content / state
            # Then this occurs...
            print("HERE, CAN'T ACCESS LINE NUMBER:")
            print("Line Number: %d" % line_number)
            print("Variable1: %s; Variable2: %s" % (variable_name1, variable_name2))
            print("lines_length: %d" % lines_length)
            for i in range(0, lines_length):
                print("%d: %s" % (i, lines[i]))
            print(content)
            print(state)
            print(tagging.get_current_tags())
            sys.exit(-1)

        if variable_name1 in associated_line:
            possibilities_filtered.append(entry)

    if len(possibilities_filtered) == 0:
        tagging.add_tag(Tag.MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE2_DO_NOTHING)
        return content, state  # Return the unmodified data because there is no mutation to perform
    random_entry = utils.get_random_entry(possibilities_filtered)
    (variable_name1, variable_name2, line_number) = random_entry
    # utils.dbg_msg("Going to replace variable >%s< with variable >%s< in line %d" % random_entry)

    if utils.get_random_bool():
        tagging.add_tag(Tag.MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE3)
        lines[line_number] = lines[line_number].replace(variable_name1, variable_name2)
    else:
        tagging.add_tag(Tag.MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE4)
        lines[line_number] = lines[line_number].replace(variable_name1, variable_name2, 1)  # just first occurrence

    new_content = "\n".join(lines)

    # Update the state
    # The replaced variable can also change the variable types in subsequent lines
    # E:g.: lets assume a code line like "var_1_ = true", when I change it to "var_2_ = true"
    # Then the data type of "var_2_" would change in later code lines
    # Currently I don't update the state with these changes...
    # TODO: Decide if I should update the state? Maybe make this based on a random decision?
    state.testcase_size = len(new_content)
    state.calculate_curly_bracket_offsets(new_content)

    return new_content, state
