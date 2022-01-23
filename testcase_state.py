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


# Implements the class which stores the state of a testcase/operation
#
# Some Notes:
# The design of this class is important for the fuzzer. First, several thousand instances
# of it will be in-memory during fuzzing.
# E.g.: with a corpus of 13 000 entries and a database of variable operations of ~45 000 entries
# there will be 58 000 instances of it in-memory. Since I'm using dictionaries which store lists of tuples and so on,
# this will use a lot of space! And the longer I fuzz, the bigger the corpus gets and the more variable operations I get
#
# Another important consideration is the speed. During mutations, I often merge two state objects.
# This operation must be as fast as possible, otherwise it has a huge impact on the fuzzers performance.
#
# At the moment I have a memory usage of over 1 GB RAM when I load my corpus + database operations.
# I did several tests to reduce the size.
# E.g.:  at the moment I store variable data types like:
# "var_1_": (1, "real_number")
#
# Which is pretty stupid. Its stupid to store "real_number" as string and not as integer value (...)
# Moreover, "var_1_" can also be replaced with the integer value 1.
# I already implemented such a transformation in a debugging script.
# However, for the database operations I could just reduce the RAM usage from 334 MB to ~260 MB
# which is not a lot..
#
# Therefore I'm still storing stuff using strings (as shown above) although it's stupid.
# The reason is that I would have to rewrite a lot of code to store the state differently.
# (e.g. change the database operations + generic database operations + states of all corpus entries + template files
# and then I need to change mutation code, state creation code and JavaScript operations extraction code
#
# I'm still planning to implement this improvement at some point, but not right now.
# I need to first better understand how I can reduce the memory usage more extensive.
# The current problem is that I store a lot of datastructures such as dictionaries, lists and tuples
# and they consume a lot of memory. Storing data as strings instead of integers wasts some memory, but a lot more
# memory is wasted because of the required bytes of data structures.
#
# Another important thing to consider:
# If I store variable names sometimes as integers (e.g. var_5_ would be stored as 5+3=8; (I always add +3 to the ID)
# because IDs 0-2 are used for the common tokens "this", "arguments" and "new.target")
# Then I need to perform an additional check if the variable_name is numeric because I also have other variable names
# like "randomVariableNameWhichCouldntBeRenamed"
# I need to check if this additional check reduces fuzzer performance.
# => In general I would say that fuzzer performance is more important than RAM usage.
# (but I must still be able to run the fuzzer on cheap GCE/AWS instances)
#
# It also depends on the target cloud system I will use for fuzzing
# E.g.: there are systems with 2 GB RAM and 2 cores, but that would not be enough for my current fuzzer
# because 2 cores with 2 running fuzzer instances, but a fuzzer instance now consumes ~1,4GB RAM
# But there are also systems with 4 cores and 16 GB RAM, but I need to check if the pricing scales good for them.
# If there is not a lot of a price differences between using 2 2GB-RAM/2cores systems and 1 16GB-RAM/4core system
# then I don't need to reduce RAM usage.
# Edit: I had to use 16-core fuzzing systems to not run into GCE quota limitations. The RAM of these systems is enough.
#
# All of this needs additional extensive testing.


import pickle
import config as cfg
import native_code.speed_optimized_functions as speed_optimized_functions
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag


# Saves a state object to a file
def save_state(state_obj, save_filepath):
    with open(save_filepath, 'wb') as fout:
        pickle.dump(state_obj, fout, pickle.HIGHEST_PROTOCOL)


# Loads a state object from a file
def load_state(filepath):
    with open(filepath, 'rb') as finput:
        state_obj = pickle.load(finput)
    # Fix older pickle versions of the class
    if hasattr(state_obj, 'deterministic_processing_was_done') is False:
        state_obj.deterministic_processing_was_done = False
    if hasattr(state_obj, 'lines_where_code_with_start_coma_can_be_inserted') is False:
        state_obj.lines_where_code_with_start_coma_can_be_inserted = []     # empty list
    if hasattr(state_obj, 'testcase_filename') is False:
        state_obj.testcase_filename = ""
    if hasattr(state_obj, 'array_items_or_properties') is False:
        state_obj.array_items_or_properties = dict()
    return state_obj




class Testcase_State:
    def __init__(self, number_variables, number_functions, number_classes):

        self.testcase_filename = ""

        self.number_variables = number_variables
        self.number_functions = number_functions
        self.number_classes = number_classes

        # entries are tuples like (2,7) which means in line 2 a block starts and it ends in line 7
        self.block_structure = []   

        # key is the variable name; the value is a list of tuples such as (2,TYPE) 
        # which means in line 2 the data type of the variable is TYPE
        self.variable_types = dict()   

        # Array items like var_1_[5] or properties like var_1_.propertyName1
        # could be also stored in self.variable_types, but I want to keep them separated so that the fuzzer
        # can decide if he wants to have a variable or array-item/property
        self.array_items_or_properties = dict()

        # stores the length of variables per line;
        # a variable can have multiple length values per line, e.g. inside a loop
        self.array_lengths = dict()

        # Variables which are always undefined can be ignored, I collect them here
        self.unused_variables = set()

        # maps the function name to the number of arguments which it expects
        self.function_arguments = dict()

        # e.g. inside objects like:
        # obj_xyz = {
        #     prop1: 123,
        #     prop2: "foobar",
        # }
        # => here code can't be inserted because it won't be executed and it will destroy the structure
        # I store in this variable in which lines I can insert code
        self.lines_where_code_can_be_inserted = []
        self.lines_where_code_with_coma_can_be_inserted = []
        self.lines_where_code_with_start_coma_can_be_inserted = []
        self.lines_which_are_executed_at_least_one_thousand_times = []
        self.lines_where_inserted_code_leads_to_timeout = []
        self.lines_where_inserted_code_leads_to_exception = []
        self.lines_which_are_not_executed = []

        # This list contains the offsets where a { } block starts and ends
        # This is important when I combine testcases, e.g.: I can't include code lines from one testcase
        # across the blocks because then the number of { or } symbols would be wrong in the final testcase
        # note: The list is not sorted
        self.curly_brackets_list = []

        # How often the file was executed as sub-testcase during fuzzing
        self.number_of_executions = 0
        self.number_of_success_executions = 0
        self.number_of_timeout_executions = 0
        self.number_of_exception_executions = 0
        self.number_of_crash_executions = 0
        self.number_total_triggered_edges = 0
        self.unique_triggered_edges = 0     # TODO: This will take longer to implement
        self.unreliable_score = 0           # Not really implemented/used yet
        self.testcase_size = 0
        self.testcase_number_of_lines = 0
        self.runtime_length_in_ms = 0
        self.deterministic_processing_was_done = False


    def __str__(self):
        tmp = ""
        tmp += "\n"
        tmp += "State:\n"

        tmp += "Initial testcase: %s\n" % self.testcase_filename
        tmp += "Size: %d bytes\n" % self.testcase_size
        tmp += "Code lines: %d\n" % self.testcase_number_of_lines
        tmp += "Runtime: %d ms\n" % self.runtime_length_in_ms
        tmp += "Unreliable score: %d\n" % self.unreliable_score
        if self.deterministic_processing_was_done:
            tmp += "Deterministically preprocessed: YES"
        else:
            tmp += "Deterministically preprocessed: NO"
        tmp += "\n"

        # TODO: I think the edges values are currently not correctly set
        # => The executor extracts them correctly, but I'm re-verifying the results multiple times
        # and while doing this, I think I lose the real value and set them to 0 somewhere. => Fix this.
        # The number of unique edges can be useful in a selection strategy which testcases should be mutated next
        # tmp += "Total triggered edges: %d\n" % self.number_total_triggered_edges
        # tmp += "Unique triggered edges: %d\n" % self.unique_triggered_edges
        # tmp += "\n"

        tmp += "Variables: %d\n" % self.number_variables
        tmp += "Functions: %d\n" % self.number_functions
        tmp += "Classes: %d\n" % self.number_classes
        tmp += "Unused variables (always undefined): %s\n" % ",".join(self.unused_variables)
        tmp += "\n"

        for func_name in self.function_arguments:
            tmp += "Function >%s< expects %d parameters\n" % (func_name, self.function_arguments[func_name])
        tmp += "Number of executions: %d\n" % self.number_of_executions
        tmp += "Number of success executions: %d\n" % self.number_of_success_executions
        tmp += "Number of timeouts: %d\n" % self.number_of_timeout_executions
        tmp += "Number of exceptions: %d\n" % self.number_of_exception_executions
        tmp += "Number of crashes: %d\n" % self.number_of_crash_executions
        tmp += "\n"

        tmp += "Lines where code can be inserted: %s\n" % _int_list_to_string(self.lines_where_code_can_be_inserted)
        tmp += "lines where code can be coma inserted: %s\n" % _int_list_to_string(self.lines_where_code_with_coma_can_be_inserted)
        tmp += "lines where code can be start-coma inserted: %s\n" % _int_list_to_string(self.lines_where_code_with_start_coma_can_be_inserted)
        tmp += "Lines which execute at least 1000 times: %s\n" % _int_list_to_string(self.lines_which_are_executed_at_least_one_thousand_times)
        tmp += "Lines where inserted code leads to timeout: %s\n" % _int_list_to_string(self.lines_where_inserted_code_leads_to_timeout)
        tmp += "Lines where inserted code throws exception: %s\n" % _int_list_to_string(self.lines_where_inserted_code_leads_to_exception)
        tmp += "Lines which are not executed: %s\n" % _int_list_to_string(self.lines_which_are_not_executed)
        tmp += "\n"

        tmp += "Variable types:\n"
        for variable_name in self.variable_types:
            tmp += "\t%s:\n" % variable_name
            for entry in self.variable_types[variable_name]:
                (line_number, variable_type) = entry
                tmp += "\t\tline %d => %s\n" % (line_number, variable_type)
            tmp += "\n"
        
        tmp += "Array items / properties:\n"
        for variable_name in self.array_items_or_properties:
            tmp += "\t%s:\n" % variable_name
            for entry in self.array_items_or_properties[variable_name]:
                (line_number, variable_type) = entry
                tmp += "\t\tline %d => %s\n" % (line_number, variable_type)
            tmp += "\n"

        tmp += "Array lengths:\n"
        for variable_name in self.array_lengths:
            tmp += "\t%s:\n" % variable_name
            for entry in self.array_lengths[variable_name]:
                (line_number, array_length_list) = entry
                tmp += "\t\tline %d " % line_number
                tmp += "=> "
                tmp += ",".join(str(x) for x in array_length_list)
                tmp += "\n"
            tmp += "\n"

        tmp += "Curly bracket offsets:\n"       # note: The list is not sorted!
        for entry in self.curly_brackets_list:
            (opening_bracket_index, closing_bracket_index) = entry
            tmp += ("\tOpen offset: 0x%02x, close offset: 0x%02x\n" % (opening_bracket_index, closing_bracket_index))
        tmp += "\n"

        tmp += "-"*20
        tmp += "\n"*3
        return tmp

    # Prints only most important stuff
    # a full __str__ call would result in a very long state output
    def get_summary(self):
        tmp = ""
        tmp += "Initial testcase: %s\n" % self.testcase_filename
        tmp += "Code lines: %d\n" % self.testcase_number_of_lines
        # tmp += "Runtime: %d ms\n" % self.runtime_length_in_ms
        tmp += "Variables: %d\n" % self.number_variables
        tmp += "Functions: %d\n" % self.number_functions
        tmp += "Classes: %d\n" % self.number_classes
        for func_name in self.function_arguments:
            tmp += "Function >%s< expects %d parameters\n" % (func_name, self.function_arguments[func_name])
        tmp += "Lines where code can be inserted: %s\n" % _int_list_to_string(self.lines_where_code_can_be_inserted)
        tmp += "lines where code can be coma inserted: %s\n" % _int_list_to_string(self.lines_where_code_with_coma_can_be_inserted)
        tmp += "lines where code can be start-coma inserted: %s\n" % _int_list_to_string(self.lines_where_code_with_start_coma_can_be_inserted)

        tmp += "Variable types:\n"
        for variable_name in self.variable_types:
            tmp += "\t%s:\n" % variable_name
            for entry in self.variable_types[variable_name]:
                (line_number, variable_type) = entry
                tmp += "\t\tline %d => %s\n" % (line_number, variable_type)

        tmp += "Array items / properties:\n"
        for variable_name in self.array_items_or_properties:
            tmp += "\t%s:\n" % variable_name
            for entry in self.array_items_or_properties[variable_name]:
                (line_number, variable_type) = entry
                tmp += "\t\tline %d => %s\n" % (line_number, variable_type)

        tmp += "Array lengths:\n"
        for variable_name in self.array_lengths:
            tmp += "\t%s:\n" % variable_name
            for entry in self.array_lengths[variable_name]:
                (line_number, array_length_list) = entry
                tmp += "\t\tline %d " % line_number
                tmp += "=> "
                tmp += ",".join(str(x) for x in array_length_list)
                tmp += "\n"

        tmp += "-"*20
        return tmp

    # Adds a mapping that in a specific line the variable has a specific type
    def add_variable_type(self, variable_name, line_number, variable_type):
        if variable_name not in self.variable_types:
            self.variable_types[variable_name] = []
        self.variable_types[variable_name].append((line_number, variable_type))


    def add_array_item_or_property_type(self, variable_name, line_number, variable_type):
        if variable_name not in self.array_items_or_properties:
            self.array_items_or_properties[variable_name] = []
        self.array_items_or_properties[variable_name].append((line_number, variable_type))


    def recalculate_unused_variables(self, content):
        self.unused_variables = set()   # remove old entries

        # Fix it via variable names
        for variable_name in self.variable_types:
            always_undefined = True
            for entry in self.variable_types[variable_name]:
                (line_number, variable_type) = entry
                if variable_type != "undefined":
                    always_undefined = False
                    break
            if always_undefined:
                self.unused_variables.add(variable_name)

        # Fix it via variable-IDs which should be available
        for variable_id in range(1, self.number_variables + 1):
            token_name = "var_%d_" % variable_id
            if token_name not in content:
                self.unused_variables.add(token_name)

        # Fix the array items/properties
        for variable_name in self.array_items_or_properties:
            always_undefined = True
            for entry in self.array_items_or_properties[variable_name]:
                (line_number, variable_type) = entry
                if variable_type != "undefined":
                    always_undefined = False
                    break
            if always_undefined:
                self.unused_variables.add(variable_name)


    def add_array_length(self, variable_name, line_number, array_length_list):
        if variable_name not in self.array_lengths:
            self.array_lengths[variable_name] = []
        self.array_lengths[variable_name].append((line_number, array_length_list))

    def get_variable_types_in_line(self, variable_name, line_number):
        ret = []
        if variable_name not in self.variable_types:
            return None

        # print("Start of loop, variable_name: %s, line_number: %d" % (variable_name, line_number))
        for entry in self.variable_types[variable_name]:
            # print("In loop iteration")
            (entry_line_number, variable_type) = entry
            if entry_line_number == line_number:
                ret.append(variable_type)
        return ret


    def get_available_variables_in_line(self, line_number, exclude_undefined=True):
        ret = []
        for variable_name in self.variable_types:
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if exclude_undefined and variable_type == "undefined":
                    continue
                if entry_line_number == line_number:
                    if variable_name not in ret:
                        ret.append(variable_name)
                    break   # break first loop and go to the next variable
        return ret

    def is_variable_available_and_not_undefined_in_line(self, variable_name, line_number):
        if variable_name not in self.variable_types:
            return False
        for entry in self.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == line_number and variable_type != "undefined":
                return True
        return False

    def get_available_variables_in_line_with_datatypes(self, line_number, exclude_undefined=True):
        tmp = dict()
        for variable_name in self.variable_types:
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if exclude_undefined and variable_type == "undefined":
                    continue
                if entry_line_number == line_number:
                    # We found a valid entry for a line
                    if variable_name not in tmp:
                        tmp[variable_name] = set()  # we need a list because a variable can have different data types in a line
                    tmp[variable_name].add(variable_type)
        return tmp

    def get_available_array_items_or_properties_in_line_with_datatypes(self, line_number, exclude_undefined=True):
        tmp = dict()
        for variable_name in self.array_items_or_properties:
            for entry in self.array_items_or_properties[variable_name]:
                (entry_line_number, variable_type) = entry
                if exclude_undefined and variable_type == "undefined":
                    continue
                if entry_line_number == line_number:
                    # We found a valid entry for a line
                    if variable_name not in tmp:
                        tmp[variable_name] = set()  # we need a list because a variable can have different data types in a line
                    tmp[variable_name].add(variable_type)
        return tmp

    # a "token" is either a variable or an array item / variable property
    # Important: "numeric" means "real_number" or "special_number", but not BigInt
    # => It's often not possible to mix BigInt with other numeric values in operations like "**="
    # Therefore I don't consider BigInt numeric here
    def get_available_numeric_tokens_in_line(self, line_number):
        tmp = set()
        # Check variables:
        for variable_name in self.variable_types:
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    if variable_type == "real_number" or variable_type == "special_number":
                        tmp.add(variable_name)
        # Check array items / properties:
        for variable_name in self.array_items_or_properties:
            for entry in self.array_items_or_properties[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    if variable_type == "real_number" or variable_type == "special_number":
                        tmp.add(variable_name)
        return tmp

    def get_used_array_indexes_in_line(self, array_name, line_number):
        found_indexes = set()
        array_name2 = array_name + "["
        for variable_name in self.array_items_or_properties:
            if variable_name.startswith(array_name2) is False:
                continue

            for entry in self.array_items_or_properties[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    array_index_str = variable_name[len(array_name2):-1]
                    found_indexes.add(array_index_str)
        return found_indexes

    def get_available_arrays_in_line_with_lengths(self, line_number):
        tmp = dict()
        for variable_name in self.array_lengths:
            for entry in self.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                if entry_line_number == line_number:
                    # found a valid entry for a line
                    tmp[variable_name] = array_length_list
        return tmp

    # The performance of this function has a strong impact on the overall fuzzer performance
    def calculate_curly_bracket_offsets(self, content):
        tmp_content = content
        tmp_offset = 0
        opening_bracket_offsets = []
        closing_bracket_offsets = []

        should_calculate_precise = cfg.precise_curly_bracket_calculation_mode_enabled
        if should_calculate_precise and content.count("{") >= 100:
            # Disable it because precise mode with many { takes very long!
            should_calculate_precise = False

        if should_calculate_precise is False:
            # Buggy approach, but it's a lot faster. If the "{" occurs in a string, it can lead to problems
            # I will use this approach in most cases although it's buggy, but it's really a lot faster! (a lot!)
            # Just to put this into number:
            # If I add 2 variables to a testcase via a mutation, 8% of the overall time would be spent on the precise-calculation path (the else-path)
            # so I only use 92% of the time for fuzzing and 8% just to calculate the { and } offsets
            # On the other hand: By taking this path with the 'buggy approach' I just use 0.04 % for this code (instead of 8%)
            # => Therefore I'm using this code in most cases

            # Edit: I re-implemented get_index_of_next_symbol_not_within_string() in C code and now this function
            # is a lot faster
            opening_bracket_offsets = _find_all(content, '{')
            closing_bracket_offsets = _find_all(content, '}')
        else:
            # try to find the open/close brackets by taking strings into account
            while True:
                idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(tmp_content, "{")
                idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(tmp_content, "}")
                if idx == -1 and idx2 == -1:
                    break
                if (idx2 != -1 and idx2 < idx) or idx == -1:
                    # idx2 ({) is the next symbol
                    closing_bracket_offsets.append(idx2 + tmp_offset)
                    tmp_content = tmp_content[idx2+1:]
                    tmp_offset += idx2+1
                else:
                    # idx (}) is the next symbol
                    opening_bracket_offsets.append(idx + tmp_offset)
                    tmp_content = tmp_content[idx+1:]
                    tmp_offset += idx+1

        curly_brackets_list = []
        # I can find the pairs of brackets by starting with the first closing bracket and going "backward"
        # to find the correct starting bracket
        # This only works if the testcase is good and the number of opening and closing brackets is the same
        # if this is not the case, the testcase has some string strings containing the brackets which I can
        # currently not parse (But this should not happen)
        if len(opening_bracket_offsets) == len(closing_bracket_offsets):
            while len(closing_bracket_offsets) != 0:
                closing_bracket_index = closing_bracket_offsets.pop(0)
                # Now find the associated opening bracket
                opening_bracket_index = -1
                for possible_idx in opening_bracket_offsets:
                    if opening_bracket_index == -1:
                        opening_bracket_index = possible_idx
                    elif possible_idx < closing_bracket_index:
                        opening_bracket_index = possible_idx
                # print("Found opening_bracket_index: %d" % opening_bracket_index)
                # Now opening_bracket_index should point to the correct offset
                if opening_bracket_index >= closing_bracket_index:
                    # utils.perror("The testcase is wrong and the brackets close before they open....")
                    # This occurs in some testcases where the current parsing logic is not fully working
                    # e.g.: testcases containing this code:
                    #  ``.replace(/"/g, '`'),
                    # Currently regex strings are not supported and therefore /"/ is not detected as a regex string
                    # instead it assumes that " starts a string... and then everything screws up
                    self.curly_brackets_list = []   # just ignore the brackets in this testcase...
                    return

                opening_bracket_offsets.remove(opening_bracket_index)
                curly_brackets_list.append((opening_bracket_index, closing_bracket_index))
            # Safe result in the state
            self.curly_brackets_list = curly_brackets_list


    def sort_all_entries(self):
        self.lines_where_code_can_be_inserted.sort()
        self.lines_where_code_with_coma_can_be_inserted.sort()
        self.lines_which_are_executed_at_least_one_thousand_times.sort()
        self.lines_where_inserted_code_leads_to_timeout.sort()
        self.lines_where_inserted_code_leads_to_exception.sort()
        self.lines_which_are_not_executed.sort()

        for variable_name in self.variable_types:
            self.variable_types[variable_name].sort(key=lambda a: a[0])

        for variable_name in self.array_items_or_properties:
            self.array_items_or_properties[variable_name].sort(key=lambda a: a[0])

        for variable_name in self.array_lengths:
            self.array_lengths[variable_name].sort(key=lambda a: a[0])

    # This function is mainly used in state creation for template files
    # where I manually perform state modifications..
    def remove_all_entries_for_line_number(self, line_number):
        if line_number in self.lines_where_code_can_be_inserted:
            self.lines_where_code_can_be_inserted.remove(line_number)
        if line_number in self.lines_where_code_with_coma_can_be_inserted:
            self.lines_where_code_with_coma_can_be_inserted.remove(line_number)
        if line_number in self.lines_which_are_executed_at_least_one_thousand_times:
            self.lines_which_are_executed_at_least_one_thousand_times.remove(line_number)
        if line_number in self.lines_where_inserted_code_leads_to_timeout:
            self.lines_where_inserted_code_leads_to_timeout.remove(line_number)
        if line_number in self.lines_where_inserted_code_leads_to_exception:
            self.lines_where_inserted_code_leads_to_exception.remove(line_number)
        if line_number in self.lines_which_are_not_executed:
            self.lines_which_are_not_executed.remove(line_number)
      
        # Fix variable_types
        for variable_name in self.variable_types:
            entries_to_remove = []
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    entries_to_remove.append(entry)
            for entry in entries_to_remove:
                self.variable_types[variable_name].remove(entry)
            
        # Fix array items/properties
        for variable_name in self.array_items_or_properties:
            entries_to_remove = []
            for entry in self.array_items_or_properties[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    entries_to_remove.append(entry)
            for entry in entries_to_remove:
                self.array_items_or_properties[variable_name].remove(entry)

        # Fix array lengths
        for variable_name in self.array_lengths:
            entries_to_remove = []
            for entry in self.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                if entry_line_number == line_number:
                    entries_to_remove.append(entry)
            for entry in entries_to_remove:
                self.array_lengths[variable_name].remove(entry)



    def update_all_line_number_lists_with_insertion_of_second_testcase(self, testcase2_state, line_number_where_insertion_happens):
        self.lines_where_code_can_be_inserted = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_where_code_can_be_inserted,
            testcase2_state.lines_where_code_can_be_inserted,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_where_code_with_coma_can_be_inserted = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_where_code_with_coma_can_be_inserted,
            testcase2_state.lines_where_code_with_coma_can_be_inserted,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_where_code_with_start_coma_can_be_inserted = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_where_code_with_start_coma_can_be_inserted,
            testcase2_state.lines_where_code_with_start_coma_can_be_inserted,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_which_are_executed_at_least_one_thousand_times = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_which_are_executed_at_least_one_thousand_times,
            testcase2_state.lines_which_are_executed_at_least_one_thousand_times,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_where_inserted_code_leads_to_timeout = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_where_inserted_code_leads_to_timeout,
            testcase2_state.lines_where_inserted_code_leads_to_timeout,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_where_inserted_code_leads_to_exception = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_where_inserted_code_leads_to_exception,
            testcase2_state.lines_where_inserted_code_leads_to_exception,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

        self.lines_which_are_not_executed = _update_line_number_list_with_insertion_of_second_testcase(
            self.lines_which_are_not_executed,
            testcase2_state.lines_which_are_not_executed,
            line_number_where_insertion_happens,
            testcase2_state.testcase_number_of_lines)

    # TODO: why did I use here camelcase for a func name? Rename it here and at all other occurrences
    # Maybe use the __copy__ or __deepcopy__ magic function?
    def deep_copy(self):
        ret = Testcase_State(self.number_variables, self.number_functions, self.number_classes)

        if hasattr(self, 'testcase_filename') is False:
            ret.testcase_filename = ""
        else:
            ret.testcase_filename = self.testcase_filename

        ret.testcase_size = self.testcase_size
        ret.testcase_number_of_lines = self.testcase_number_of_lines
        ret.runtime_length_in_ms = self.runtime_length_in_ms
        ret.unreliable_score = self.unreliable_score
        ret.deterministic_processing_was_done = self.deterministic_processing_was_done
        ret.number_total_triggered_edges = self.number_total_triggered_edges
        ret.unique_triggered_edges = self.unique_triggered_edges

        ret.unused_variables = self.unused_variables.copy()
        ret.function_arguments = self.function_arguments.copy()

        ret.number_of_executions = self.number_of_executions
        ret.number_of_success_executions = self.number_of_success_executions
        ret.number_of_timeout_executions = self.number_of_timeout_executions
        ret.number_of_exception_executions = self.number_of_exception_executions
        ret.number_of_crash_executions = self.number_of_crash_executions

        ret.lines_where_code_can_be_inserted = self.lines_where_code_can_be_inserted.copy()
        ret.lines_where_code_with_coma_can_be_inserted = self.lines_where_code_with_coma_can_be_inserted.copy()
        ret.lines_where_code_with_start_coma_can_be_inserted = self.lines_where_code_with_start_coma_can_be_inserted.copy()
        ret.lines_which_are_executed_at_least_one_thousand_times = self.lines_which_are_executed_at_least_one_thousand_times.copy()
        ret.lines_where_inserted_code_leads_to_timeout = self.lines_where_inserted_code_leads_to_timeout.copy()

        ret.lines_where_inserted_code_leads_to_exception = self.lines_where_inserted_code_leads_to_exception.copy()
        ret.lines_which_are_not_executed = self.lines_which_are_not_executed.copy()

 
        # Note: a dict can also be copied by using copy.deepcopy(..)
        # => However, that's extremely slow. Also other approaches with pickle or json (or ujson) are very slow
        # The fastest approach was to manually copy the data like below..
        tmp = dict()
        for variable_name in self.variable_types:
            tmp[variable_name] = self.variable_types[variable_name].copy()
        ret.variable_types = tmp

        tmp = dict()
        for variable_name in self.array_items_or_properties:
            tmp[variable_name] = self.array_items_or_properties[variable_name].copy()
        ret.array_items_or_properties = tmp
            
        tmp = dict()
        for variable_name in self.array_lengths:
            tmp[variable_name] = []
            for entry in self.array_lengths[variable_name]:
                (line_number, array_length_list) = entry
                array_length_list = array_length_list.copy()
                tmp[variable_name].append((line_number, array_length_list))
        ret.array_lengths = tmp

        ret.curly_brackets_list = self.curly_brackets_list.copy()
        return ret

    def state_update_content_length(self, added_length, new_content):
        self.testcase_size += added_length
        # Curley brackets are now calculated lazily
        # state.calculate_curly_bracket_offsets(new_content)



    def state_insert_line(self, line_number, new_content, inserted_line):
        tagging.add_tag(Tag.STATE_INSERT_LINE1)
        inserted_line_length = len(inserted_line)
        self.testcase_size += (inserted_line_length + 1)  # +1 because also a "\n" was added
        self.testcase_number_of_lines += 1

        self.lines_where_code_can_be_inserted = _state_insert_line_number_list(self.lines_where_code_can_be_inserted, line_number)
        self.lines_where_code_with_coma_can_be_inserted = _state_insert_line_number_list(self.lines_where_code_with_coma_can_be_inserted, line_number)
        self.lines_where_code_with_start_coma_can_be_inserted = _state_insert_line_number_list(self.lines_where_code_with_start_coma_can_be_inserted, line_number)
        self.lines_which_are_executed_at_least_one_thousand_times = _state_insert_line_number_list(self.lines_which_are_executed_at_least_one_thousand_times, line_number)
        self.lines_where_inserted_code_leads_to_timeout = _state_insert_line_number_list(self.lines_where_inserted_code_leads_to_timeout, line_number)
        self.lines_where_inserted_code_leads_to_exception = _state_insert_line_number_list(self.lines_where_inserted_code_leads_to_exception, line_number)
        self.lines_which_are_not_executed = _state_insert_line_number_list(self.lines_which_are_not_executed, line_number)

        self.lines_where_code_can_be_inserted.append(line_number)
        self.lines_where_code_can_be_inserted.sort()

        for variable_name in self.variable_types:
            tmp = []
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number < line_number:
                    tmp.append((entry_line_number, variable_type))
                elif entry_line_number == line_number:
                    # Duplicate the entry for both lines because the variables should then be also available
                    # before and after the inserted line
                    tmp.append((entry_line_number, variable_type))
                    tmp.append((entry_line_number + 1, variable_type))
                else:  # entry_line_number > line_number:
                    tmp.append((entry_line_number + 1, variable_type))
            self.variable_types[variable_name] = tmp

        for variable_name in self.array_lengths:
            tmp = []
            for entry in self.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                if entry_line_number < line_number:
                    tmp.append((entry_line_number, array_length_list))
                elif entry_line_number == line_number:
                    # Duplicate the entry for both lines because the array should then be also available
                    # before and after the inserted line
                    tmp.append((entry_line_number, array_length_list))
                    tmp.append((entry_line_number + 1, array_length_list))
                else:  # entry_line_number > line_number:
                    tmp.append((entry_line_number + 1, array_length_list))
            self.array_lengths[variable_name] = tmp

        # TODO: What is with self.array_items_or_properties ???

        # Currently I don't update the curly bracket offsets, instead I'm using a "lazy loading" approach
        # Updating curly brackets takes for some reason very long, so I just update the list when I really want to access it
        # self.calculate_curly_bracket_offsets(new_content)




    def state_remove_lines(self, line_number, new_content, removed_line, number_of_lines_to_remove):
        tagging.add_tag(Tag.STATE_REMOVE_LINE1)
        removed_line_length = len(removed_line)
        self.testcase_size -= (removed_line_length + 1)  # +1 because also a "\n" gets removed
        self.testcase_number_of_lines -= number_of_lines_to_remove

        self.lines_where_code_can_be_inserted = _state_remove_line_numbers_in_list(self.lines_where_code_can_be_inserted, line_number, number_of_lines_to_remove)
        self.lines_where_code_with_coma_can_be_inserted = _state_remove_line_numbers_in_list(self.lines_where_code_with_coma_can_be_inserted, line_number, number_of_lines_to_remove)
        self.lines_where_code_with_start_coma_can_be_inserted = _state_remove_line_numbers_in_list(self.lines_where_code_with_start_coma_can_be_inserted, line_number, number_of_lines_to_remove)
        self.lines_which_are_executed_at_least_one_thousand_times = _state_remove_line_numbers_in_list(self.lines_which_are_executed_at_least_one_thousand_times, line_number, number_of_lines_to_remove)
        self.lines_where_inserted_code_leads_to_timeout = _state_remove_line_numbers_in_list(self.lines_where_inserted_code_leads_to_timeout, line_number, number_of_lines_to_remove)
        self.lines_where_inserted_code_leads_to_exception = _state_remove_line_numbers_in_list(self.lines_where_inserted_code_leads_to_exception, line_number, number_of_lines_to_remove)
        self.lines_which_are_not_executed = _state_remove_line_numbers_in_list(self.lines_which_are_not_executed, line_number, number_of_lines_to_remove)

        if removed_line.lower().lstrip().startswith("return"):
            # If the removed line was something like "return 5", then the next line would be executed
            # The subsequent lines would also get executed, but here I just mark the next line so the fuzzer can insert code here
            if line_number in self.lines_which_are_not_executed:
                self.lines_which_are_not_executed.remove(line_number)

        # Adapt the variable types:
        to_delete = set()
        for variable_name in self.variable_types:
            tmp = []
            for entry in self.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number < line_number:
                    tmp.append((entry_line_number, variable_type))
                elif line_number <= entry_line_number < (line_number + number_of_lines_to_remove):
                    # elif entry_line_number == line_number:
                    pass  # don't add the removed lines
                else:  # entry_line_number > line_number:
                    tmp.append((entry_line_number - number_of_lines_to_remove, variable_type))
            self.variable_types[variable_name] = tmp
            if len(tmp) == 0:  # check if variable is no longer available
                to_delete.add(variable_name)
        for variable_name in to_delete:
            del self.variable_types[variable_name]

        # Adapt the array lengths:
        to_delete.clear()
        for variable_name in self.array_lengths:
            tmp = []
            for entry in self.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                if entry_line_number < line_number:
                    tmp.append((entry_line_number, array_length_list))
                elif line_number <= entry_line_number < (line_number + number_of_lines_to_remove):
                    # elif entry_line_number == line_number:
                    pass  # don't add the removed lines
                else:  # entry_line_number > line_number:
                    tmp.append((entry_line_number - number_of_lines_to_remove, array_length_list))
            self.array_lengths[variable_name] = tmp
            if len(tmp) == 0:  # check if array length is no longer available
                to_delete.add(variable_name)
        for variable_name in to_delete:
            del self.array_lengths[variable_name]

        # Adapt the array items / properties
        to_delete.clear()
        for variable_name in self.array_items_or_properties:
            tmp = []
            for entry in self.array_items_or_properties[variable_name]:
                (entry_line_number, variable_type) = entry
                if entry_line_number < line_number:
                    tmp.append((entry_line_number, variable_type))
                elif line_number <= entry_line_number < (line_number + number_of_lines_to_remove):
                    pass  # don't add the removed lines
                else:  # entry_line_number > line_number:
                    tmp.append((entry_line_number - number_of_lines_to_remove, variable_type))
            self.array_items_or_properties[variable_name] = tmp
            if len(tmp) == 0:  # check if array item / property is no longer available
                to_delete.add(variable_name)
        for variable_name in to_delete:
            del self.array_items_or_properties[variable_name]

        # Currently I don't pre-calculate curly brackets and just calculate them when I really use them
        # I'm doing this lazy because calculating curly bracket offsets is a time-consuming task (at the moment)
        # self.calculate_curly_bracket_offsets(new_content)

    # Note: This function doesn't compare curly bracket offsets the size or runtime of the testcases
    # Reason: I use this function to compare state creation for operations which are applied to two different data types
    # If I calculate a state for data type XYZ and re-calculate the state for the same operation but with one variable
    # being datatype ABCDEF instead, the size of the code will be different (because ABCDEF is longer than XYZ)
    # This also means the offsets will be different => therefore I'm not checking them
    # Instead this function mainly compares the data types of variables / arrays / ...
    # TODO: if the runtime of both states is very close to MAX runtime, then comparing them maybe doesn't work
    # because maybe one state creation execution maybe has a timeout?
    # Maybe also let the function return "unkown" in such cases?
    def compare_state(self, other_state):
        # Check if the number of variables is the same
        if len(self.variable_types) != len(other_state.variable_types):
            return False    # different number of variables
        if len(self.array_items_or_properties) != len(other_state.array_items_or_properties):
            return False    # different number of properties / array items
        if len(self.array_lengths) != len(other_state.array_lengths):
            return False    # different number array length entries

        if self.number_variables != other_state.number_variables:
            return False
        if self.number_functions != other_state.number_functions:
            return False
        if self.number_classes != other_state.number_classes:
            return False

        if len(self.unused_variables) != len(other_state.unused_variables):
            return False
        for variable_name in other_state.unused_variables:
            if variable_name not in self.unused_variables:
                return False
        
        if len(self.function_arguments) != len(other_state.function_arguments):
            return False
        for func_name in other_state.function_arguments:
            if func_name not in self.function_arguments:
                return False
            if other_state.function_arguments[func_name] != self.function_arguments[func_name]:
                return False

        if self.lines_where_code_can_be_inserted != other_state.lines_where_code_can_be_inserted:
            return False
        if self.lines_where_code_with_coma_can_be_inserted != other_state.lines_where_code_with_coma_can_be_inserted:
            return False
        if self.lines_where_code_with_start_coma_can_be_inserted != other_state.lines_where_code_with_start_coma_can_be_inserted:
            return False
        if self.lines_which_are_executed_at_least_one_thousand_times != other_state.lines_which_are_executed_at_least_one_thousand_times:
            return False
        if self.lines_where_inserted_code_leads_to_timeout != other_state.lines_where_inserted_code_leads_to_timeout:
            return False
        if self.lines_where_inserted_code_leads_to_exception != other_state.lines_where_inserted_code_leads_to_exception:
            return False
        if self.lines_which_are_not_executed != other_state.lines_which_are_not_executed:
            return False

        # Check if the data types of all variables are correct
        for variable_name in other_state.variable_types:
            entries_other_state = other_state.variable_types[variable_name]
            if variable_name not in self.variable_types:
                return False
            for current_entry in self.variable_types[variable_name]:
                if current_entry in entries_other_state:
                    continue
                # If this point is reached there is an entry with a different datatype/line number
                # => the states are not the same
                return False

        # Now check array items and properties
        for variable_name in other_state.array_items_or_properties:
            entries_other_state = other_state.array_items_or_properties[variable_name]
            if variable_name not in self.array_items_or_properties:
                return False
            for current_entry in self.array_items_or_properties[variable_name]:
                if current_entry in entries_other_state:
                    continue
                return False

        # And now check array length entries
        for variable_name in other_state.array_lengths:
            entries_other_state = other_state.array_lengths[variable_name]
            if variable_name not in self.array_lengths:
                return False
            for current_entry in self.array_lengths[variable_name]:
                if current_entry in entries_other_state:
                    continue
                return False
    
        return True


def _update_line_number_list_with_insertion_of_second_testcase(current_list, additional_list, line_number_where_insertion_happens, testcase2_number_of_lines):
    new_list = []
    # Add the first part of testcase1
    for entry_line_number in current_list:
        if entry_line_number <= line_number_where_insertion_happens:
            # Add every line before and the insertion line
            new_list.append(entry_line_number)

    # Now add the lines from the 2nd testcase
    for entry_line_number in additional_list:
        new_line_number = entry_line_number + line_number_where_insertion_happens
        if new_line_number not in new_list:  # this can be false for the insertion code line / entry_line_number is zero
            new_list.append(new_line_number)

    # Add the second/last part of testcase1
    for entry_line_number in current_list:
        if entry_line_number > line_number_where_insertion_happens:
            # Add every line after and the insertion line
            new_line_number = entry_line_number + testcase2_number_of_lines
            if new_line_number not in new_list:
                new_list.append(new_line_number)
    return new_list


def _int_list_to_string(list_to_convert, separator=","):
    strings = [str(integer) for integer in list_to_convert]
    return separator.join(strings)


def _find_all(a_str, sub):
    start = 0
    x = []
    while True:
        start = a_str.find(sub, start)
        if start == -1: return x
        # yield start
        x.append(start)
        start += len(sub)       # use start += 1 to find overlapping matches


def _state_insert_line_number_list(old_list, inserted_line_number):
    tmp = []
    for entry_line_number in old_list:
        if entry_line_number < inserted_line_number:
            tmp.append(entry_line_number)
        else:  # entry_line_number >= removed_line_number:
            tmp.append(entry_line_number + 1)  # +1 because one line was added
    return tmp


def _state_remove_line_numbers_in_list(old_list, removed_line_number_start, number_of_lines_to_remove):
    tmp = []
    for entry_line_number in old_list:
        if entry_line_number < removed_line_number_start:
            tmp.append(entry_line_number)
        elif removed_line_number_start <= entry_line_number < (
                removed_line_number_start + number_of_lines_to_remove):
            pass  # don't add the removed lines
        else:  # entry_line_number > removed_line_number_start:
            tmp.append(entry_line_number - number_of_lines_to_remove)
    return tmp
