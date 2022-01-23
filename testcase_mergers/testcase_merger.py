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



# This script contains the exposed functions to merge testcases
# Basically just two functions should be used by callers:
#
# *) merge_two_testcases_randomly()
#       This function is used during fuzzing to merge two testcases randomly.
#       To more more testcases, this function can be invoked repeatedly.
#
# *) merge_testcase2_into_testcase1_at_line()
#       This function is used to merge something into another testcase at a specific line
#       This is mainly used to fill identified callback locations with data
#       (e.g. other testcases or variable operations from the database)


import sys
import utils
import operator
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
from testcase_mergers.implementations.merge_testcase_append import merge_testcase_append
from testcase_mergers.implementations.merge_testcase_insert import merge_testcase_insert
import javascript.js_helpers as js_helpers

# This global variable configures which merging operations can be used by the fuzzer
# It also defines the frequency of the merging operation
# E.g.: if merge method A is saved two times in the list and
# merge method B is just stored one time, then A will be invoked
# two times more frequently than B
merge_operations = [merge_testcase_append, merge_testcase_insert]


def merge_two_testcases_randomly(testcase1_content, testcase1_state, testcase2_content, testcase2_state):
    if testcase1_state == testcase2_state:
        # this can happen if testcase1 == testcase2 which means both states point to the same list..
        # E.g.: if testcase1 has var_1_, then testcase2 (which is the same as testcase1) would be updated to
        # use "var_2_" instead of "var_1_". However, this would also update the state of testcase1 to use "var_2_"
        # because they are the same. A copy must therefore be created
        testcase2_state = testcase2_state.deep_copy()
    merging_operation_func = utils.get_random_entry(merge_operations)
    return merging_operation_func(testcase1_content, testcase1_state, testcase2_content, testcase2_state)



def merge_testcase2_into_testcase1_at_line(testcase1_content, testcase1_state, testcase2_content, testcase2_state, line_number):
    tagging.add_tag(Tag.MERGE_TESTCASE2_INTO_TESTCASE1_AT_LINE1)

    # TODO: These are calculations which I plan to use in the future, but which currently don't work
    # More details below
    total_number_variables = testcase1_state.number_variables + testcase2_state.number_variables
    total_number_functions = testcase1_state.number_functions + testcase2_state.number_functions
    total_number_classes = testcase1_state.number_classes + testcase2_state.number_classes

    (testcase2_content, testcase2_state) = _adapt_second_testcase_to_first_testcase(testcase2_content, testcase2_state, testcase1_state)

    possible_newline = ""
    if testcase2_content.endswith("\n") is False:
        possible_newline = "\n"

    new_content = ""
    testcase1_content_lines = testcase1_content.split("\n")
    # print(testcase1_content)
    # print(testcase1_state)
    # print("len(testcase1_content_lines): %d" % len(testcase1_content_lines) )
    # print("line_number: %d" % line_number)
    for idx in range(0, line_number):
        try:
            new_content += testcase1_content_lines[idx] + "\n"
        except:
            print("PROBLEM HERE1")
            print("idx: %d" % idx)
            print("line_number: %d" % line_number)
            print("Testcase1:")
            print(testcase1_content)
            print(testcase1_state)
            print("Testcase2:")
            print(testcase2_content)
            print(testcase2_state)
            sys.exit(-1)
    new_content += testcase2_content + possible_newline
    for idx in range(line_number, len(testcase1_content_lines)):
        try:
            new_content += testcase1_content_lines[idx] + "\n"
        except:
            print("PROBLEM HERE2")
            print("idx: %d" % idx)
            print("line_number: %d" % line_number)
            print("Testcase1:")
            print(testcase1_content)
            print(testcase1_state)
            print("Testcase2:")
            print(testcase2_content)
            print(testcase2_state)
            sys.exit(-1)
    new_content = new_content.rstrip("\n")  # remove the last newline

    # Now update the state

    # The next call makes all variables / tokens / available to the result state
    result_state = _state_update_all_line_numbers(testcase1_state, testcase2_state, line_number)

    result_state.testcase_filename = "%s + %s" % (testcase1_state.testcase_filename, testcase2_state.testcase_filename)
    result_state.testcase_size = len(new_content)
    result_state.testcase_number_of_lines = len(new_content.split("\n"))

    # TODO: Don't call this here, it's very slow!
    # result_state.calculate_curly_bracket_offsets(new_content)       # TODO: should I really do this here? this operation is slow and maybe I don't need it

    # The following values are just estimations
    # E.g.: I assume that when I combine testcase1 with testcase2 the total runtime will be
    # runtime of testcase1 plus runtime of testcase2
    # However, if I add testcase2 inside an loop of testcase1 this estimation can be completely off
    # These are therefore just very rough values for the fuzzer to make decisions
    result_state.runtime_length_in_ms += testcase2_state.runtime_length_in_ms
    result_state.unreliable_score += testcase2_state.unreliable_score
    result_state.number_total_triggered_edges += testcase2_state.number_total_triggered_edges
    result_state.unique_triggered_edges += testcase2_state.unique_triggered_edges

    result_state.number_of_executions += testcase2_state.number_of_executions
    result_state.number_of_success_executions += testcase2_state.number_of_success_executions
    result_state.number_of_timeout_executions += testcase2_state.number_of_timeout_executions
    result_state.number_of_exception_executions += testcase2_state.number_of_exception_executions
    result_state.number_of_crash_executions += testcase2_state.number_of_crash_executions

    result_state.number_variables = js_helpers.get_number_variables_all(new_content)
    result_state.number_functions = js_helpers.get_number_functions_all(new_content)
    result_state.number_classes = js_helpers.get_number_classes_all(new_content)

    # TODO:
    # The plan is to use >total_number_variables< (and the others) instead of recalculating the number of variables
    # with js_helpers.get_number_variables_all() because recalculation is slow and currently a bottleneck
    # However: The problem is that I had a bug in the state creation, e.g. a testcase like:
    # var var_7_ = Object.defineProperty(Object,var_TARGET_,gc);
    # => There was a bug in the minimizer that it didn't change var_7_ to var_1_ and
    # in my state creation I just counted the variables until I don't find one. So the state says this testcase doesn't
    # use a variable because var_1_ does not exist. Therefore the full calculation is wrong
    # => I need to recalculate the database operations first, which I will do in a later cycle.
    # After that I can start to use >total_number_variables< which would then also be a lot faster
    """
    # DEBUGGING:
    if result_state.number_variables != total_number_variables:
        print("Found problem in merge_testcase2_into_testcase1_at_line(), different total number variables")
        print("result_state.number_variables: %d" % result_state.number_variables)
        print("total_number_variables: %d" % total_number_variables)
        print("testcase1_content:")
        print(testcase1_content)
        print("testcase2_content:")
        print(testcase2_content)
        print("testcase1_state:")
        print(testcase1_state)
        print("testcase2_state:")
        print(testcase2_state)
        sys.exit(-1)
    if result_state.number_functions != total_number_functions:
        print("Found problem in merge_testcase2_into_testcase1_at_line(), different total number functions")
        print("result_state.number_functions: %d" % result_state.number_functions)
        print("total_number_functions: %d" % total_number_functions)
        print("testcase1_content:")
        print(testcase1_content)
        print("testcase2_content:")
        print(testcase2_content)
        print("testcase1_state:")
        print(testcase1_state)
        print("testcase2_state:")
        print(testcase2_state)
        sys.exit(-1)
    if result_state.number_classes != total_number_classes:
        print("Found problem in merge_testcase2_into_testcase1_at_line(), different total number classes")
        print("result_state.number_classes: %d" % result_state.number_classes)
        print("total_number_classes: %d" % total_number_classes)
        print("testcase1_content:")
        print(testcase1_content)
        print("testcase2_content:")
        print(testcase2_content)
        print("testcase1_state:")
        print(testcase1_state)
        print("testcase2_state:")
        print(testcase2_state)
        sys.exit(-1)
    """

    result_state.recalculate_unused_variables(new_content)

    for func_name in testcase2_state.function_arguments:
        if func_name in result_state.function_arguments:  # safety check
            """
            print("Current testcase state:")
            print(result_state)
            print("\n\n")
            print("Operation state:")
            print(testcase2_state)
            print("\n\n")
            print("Adapted operation code:")
            print(testcase2_content)
            """
            utils.perror("Logic flaw, this should never occur. Did I forget to update the function names in state2?")
        result_state.function_arguments[func_name] = testcase2_state.function_arguments[func_name]

    return new_content, result_state




def _adapt_second_testcase_to_first_testcase(testcase2_content, testcase2_state, testcase1_state):
    # When I merge two testcases, e.g. by appending the 2nd to the 1st
    # I need to first modify the variable, function and class names
    # So that they are not overlapping.
    # E.g: if testcase1 uses "var_1_" and testcase2 also uses "var_1_"
    # => Then I need to change var_1_ to var_2_ in testcase2
    # To ensure that this works I need to update the testcase2 to use a not yet used variable ID (same for classes or functions)

    # There is a problem:
    # Let's assume testcase1 uses var_1_ and testcase2 uses var_1_, var_2_ and var_3_
    # In this case the next free id would be var_2_ which means "var_1_" from testcase2
    # gets renamed to "var_2_". However, now the name overlaps with the original "var_2_" name
    # That means the next iteration, which would rename "var_2_" to "var_3_" would also incorrectly
    # rename all previous "var_1_" variables
    # To solve this I first rename "var_1_" to "var_UGLYHACKTOFIXNAMES2_"
    # This name contains "UGLYHACKTOFIXNAMES" as additional string
    # At the end of the function I remove this string

    tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE1)

    mapping_old_variable_names_to_new = dict()
    mapping_old_function_names_to_new = dict()
    mapping_old_class_names_to_new = dict()

    # Fix the variables (in the code)
    next_free_id = testcase1_state.number_variables + 1
    start_id = 1
    end_id = testcase2_state.number_variables
    for current_id in range(start_id, end_id + 1):
        token_name = "var_%d_" % current_id
        if token_name in testcase2_content:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE2)
            new_token_name = "var_UGLYHACKTOFIXNAMES%d_" % next_free_id
            next_free_id += 1
            testcase2_content = testcase2_content.replace(token_name, new_token_name)
            mapping_old_variable_names_to_new[token_name] = new_token_name.replace("UGLYHACKTOFIXNAMES", "")

    # Fix the functions (in the code)
    next_free_id = testcase1_state.number_functions + 1
    start_id = 1
    end_id = testcase2_state.number_functions
    for current_id in range(start_id, end_id + 1):
        token_name = "func_%d_" % current_id
        if token_name in testcase2_content:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE3)
            new_token_name = "func_UGLYHACKTOFIXNAMES%d_" % next_free_id
            next_free_id += 1
            testcase2_content = testcase2_content.replace(token_name, new_token_name)
            mapping_old_function_names_to_new[token_name] = new_token_name.replace("UGLYHACKTOFIXNAMES", "")

    # Fix the classes (in the code)
    next_free_id = testcase1_state.number_classes + 1
    start_id = 1
    end_id = testcase2_state.number_classes
    for current_id in range(start_id, end_id + 1):
        token_name = "cl_%d_" % current_id
        if token_name in testcase2_content:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE4)
            new_token_name = "cl_UGLYHACKTOFIXNAMES%d_" % next_free_id
            next_free_id += 1
            testcase2_content = testcase2_content.replace(token_name, new_token_name)
            mapping_old_class_names_to_new[token_name] = new_token_name.replace("UGLYHACKTOFIXNAMES", "")

    # Now update the state which encodes the variable types

    # Fix the Variable types (in the state)
    new_dict = dict()
    for variable_name in testcase2_state.variable_types:
        if variable_name in mapping_old_variable_names_to_new:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE5)
            new_variable_name = mapping_old_variable_names_to_new[variable_name]
        else:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE6)
            new_variable_name = variable_name  # same as before, e.g. variables like "this"
        new_dict[new_variable_name] = testcase2_state.variable_types[variable_name]
    testcase2_state.variable_types = new_dict

    # Fix the Array lengths (in the state)
    new_dict = dict()
    for variable_name in testcase2_state.array_lengths:
        if variable_name in mapping_old_variable_names_to_new:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE7)
            new_variable_name = mapping_old_variable_names_to_new[variable_name]
        else:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE8)
            new_variable_name = variable_name  # same as before, e.g. variables like "this"
        new_dict[new_variable_name] = testcase2_state.array_lengths[variable_name]
    testcase2_state.array_lengths = new_dict

    # Fix array items / properties
    new_dict = dict()
    for variable_name in testcase2_state.array_items_or_properties:
        tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE11)
        fixed_variable_name = variable_name
        for old_variable_name in mapping_old_variable_names_to_new:
            if old_variable_name in fixed_variable_name:
                tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE12)
                # This means there was an array item like "var_1_[123]" and
                # var_1_ was renamed to something else like var_5_
                # I must therefore change "var_1_[123]" to "var_5_[123]"
                new_variable_name = mapping_old_variable_names_to_new[old_variable_name].replace("var_",
                                                                                                 "var_UGLYHACKTOFIXNAMES")
                fixed_variable_name = fixed_variable_name.replace(old_variable_name, new_variable_name)

        # Also code such as the following can occur (at least I think so?):
        # like var_1_[func_1_()]
        # TODO: Do I currently really allow "()" inside an array item access? (check the create_state_file.py code!)
        for old_func_name in mapping_old_function_names_to_new:
            if old_func_name in fixed_variable_name:
                tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE13)
                new_func_name = mapping_old_function_names_to_new[old_func_name].replace("func_",
                                                                                         "func_UGLYHACKTOFIXNAMES")
                fixed_variable_name = fixed_variable_name.replace(old_func_name, new_func_name)

        for old_class_name in mapping_old_class_names_to_new:
            if old_class_name in fixed_variable_name:
                tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE14)
                new_class_name = mapping_old_class_names_to_new[old_class_name].replace("cl_", "cl_UGLYHACKTOFIXNAMES")
                fixed_variable_name = fixed_variable_name.replace(old_class_name, new_class_name)

        fixed_variable_name = fixed_variable_name.replace("UGLYHACKTOFIXNAMES", "")  # remove the hack again
        new_dict[fixed_variable_name] = testcase2_state.array_items_or_properties[variable_name]
    testcase2_state.array_items_or_properties = new_dict

    # Fix the Functions (in the state)
    # now fix the dict which stores per function the number of arguments it receives
    new_dict = dict()
    for function_name in testcase2_state.function_arguments:
        if function_name in mapping_old_function_names_to_new:  # should always be true (?)
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE9)
            new_function_name = mapping_old_function_names_to_new[function_name]
        else:
            tagging.add_tag(Tag.ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE10)
            new_function_name = function_name  # same as before (I think this will never occur with function names?)
        new_dict[new_function_name] = testcase2_state.function_arguments[function_name]
    testcase2_state.function_arguments = new_dict

    testcase2_content = testcase2_content.replace("UGLYHACKTOFIXNAMES", "")  # remove the hack again
    return testcase2_content, testcase2_state


def _state_update_all_line_numbers(result_state, testcase2_state, line_number_where_insertion_happens):
    tagging.add_tag(Tag.STATE_UPDATE_ALL_LINE_NUMBERS1)

    # First make variables from testcase1 also available to testcase2
    for variable_name in result_state.variable_types:
        for entry in result_state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == line_number_where_insertion_happens:
                # These are the variables which are available in testcase1 at the line where
                # testcase2 gets inserted
                # And these are therefore also the variables which are available to testcase2
                tmp = []
                for line_nr in testcase2_state.lines_where_code_can_be_inserted:
                    tmp.append((line_nr, variable_type))
                for line_nr in testcase2_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, variable_type))
                for line_nr in testcase2_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, variable_type))
                if variable_name not in testcase2_state.variable_types:     # don't overwrite something like "this", "arguments", ...
                    testcase2_state.variable_types[variable_name] = tmp

    # Now make variables from testcase2 also available in testcase1
    # Because some code of testcase1 can run after testcase2, the variables at the end of testcase2 should
    # also be available in these last lines of testcase1
    for variable_name in testcase2_state.variable_types:
        if variable_name in result_state.variable_types:
            continue    # skip "this", "arguments", .. and also skip variables which were added in the code above from testcase1 to testcase2
        for entry in testcase2_state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == testcase2_state.testcase_number_of_lines:   # available after the last line of testcase2 executed
                # These are the variables which are available after testcase2 executed
                # And these are therefore also the variables which should be available in testcase1
                # in the code lines after testcase2 insertion
                tmp = []
                for line_nr in result_state.lines_where_code_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        tmp.append((line_nr, variable_type))
                for line_nr in result_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, variable_type))
                for line_nr in result_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, variable_type))
                result_state.variable_types[variable_name] = tmp

    # Make array lengths of testcase1 available to testcase2...
    for variable_name in result_state.array_lengths:
        for entry in result_state.array_lengths[variable_name]:
            (entry_line_number, array_length_list) = entry
            if entry_line_number == line_number_where_insertion_happens:
                tmp = []
                for line_nr in testcase2_state.lines_where_code_can_be_inserted:
                    tmp.append((line_nr, array_length_list))
                for line_nr in testcase2_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, array_length_list))
                for line_nr in testcase2_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, array_length_list))
                if variable_name not in testcase2_state.array_lengths:  # don't overwrite something like "this", "arguments", ...
                    testcase2_state.array_lengths[variable_name] = tmp

    # And now make testcase2 array lengths also available to the last lines of testcase1...
    for variable_name in testcase2_state.array_lengths:
        if variable_name in result_state.array_lengths:
            continue    # skip "this", "arguments", .. and also skip arrays which were added in the code above from testcase1 to testcase2
        for entry in testcase2_state.array_lengths[variable_name]:
            (entry_line_number, array_length_list) = entry
            if entry_line_number == testcase2_state.testcase_number_of_lines:   # available after the last line of testcase2 executed
                tmp = []
                for line_nr in result_state.lines_where_code_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        tmp.append((line_nr, array_length_list))
                for line_nr in result_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, array_length_list))
                for line_nr in result_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, array_length_list))
                result_state.array_lengths[variable_name] = tmp

    # And now for or array items or properties
    # Make testcase1 entries available to testcase2
    for variable_name in result_state.array_items_or_properties:
        for entry in result_state.array_items_or_properties[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == line_number_where_insertion_happens:
                # These are the entries which are available in testcase1 at the line where
                # testcase2 gets inserted
                # And these are therefore also the entries which are available to testcase2
                tmp = []
                for line_nr in testcase2_state.lines_where_code_can_be_inserted:
                    tmp.append((line_nr, variable_type))
                for line_nr in testcase2_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, variable_type))
                for line_nr in testcase2_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr not in tmp:
                        tmp.append((line_nr, variable_type))
                if variable_name not in testcase2_state.array_items_or_properties:  # don't overwrite something like "this", "arguments", ...
                    testcase2_state.array_items_or_properties[variable_name] = tmp

    # Now make array items & properties from testcase2 available to testcase1
    for variable_name in testcase2_state.array_items_or_properties:
        if variable_name in result_state.array_items_or_properties:
            continue    # skip "this", "arguments", .. and also skip variables which were added in the code above from testcase1 to testcase2
        for entry in testcase2_state.array_items_or_properties[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == testcase2_state.testcase_number_of_lines:   # available after the last line of testcase2 executed
                # These are the variables which are available after testcase2 executed
                # And these are therefore also the variables which should be available in testcase1
                # in the code lines after testcase2 insertion
                tmp = []
                for line_nr in result_state.lines_where_code_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        tmp.append((line_nr, variable_type))
                for line_nr in result_state.lines_where_code_with_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, variable_type))
                for line_nr in result_state.lines_where_code_with_start_coma_can_be_inserted:
                    if line_nr > line_number_where_insertion_happens:   # Only code lines AFTER the insertion code line
                        if line_nr not in tmp:
                            tmp.append((line_nr, variable_type))
                result_state.array_items_or_properties[variable_name] = tmp



    result_state.update_all_line_number_lists_with_insertion_of_second_testcase(testcase2_state, line_number_where_insertion_happens)



    # Fix the variable types:
    # Note: Via variable hoisting testcase2 variables should also be available for read access in part1 of testcase1
    # However, I currently dont support this because I don't mark variables as read only..
    # I split testcase1 into two parts: part1 is before the Insertion line (where testcase2) gets inserted
    # and part2 is the code after the insertion.
    # First fix the line numbers of part2:
    for variable_name in result_state.variable_types:
        tmp = []
        for entry in result_state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number <= line_number_where_insertion_happens:
                tmp.append(entry)
            else:
                # it's a line after insertion line
                # because testcase2 gets inserted in between, the lines must be updated by the number of lines of testcase2
                tmp.append((entry_line_number + testcase2_state.testcase_number_of_lines, variable_type))
        result_state.variable_types[variable_name] = tmp

    # And now add testcase2 to the state:
    for variable_name in testcase2_state.variable_types:
        if variable_name not in result_state.variable_types:
            result_state.variable_types[variable_name] = []
        for entry in testcase2_state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            new_entry = (entry_line_number+line_number_where_insertion_happens, variable_type)
            if new_entry not in result_state.variable_types[variable_name]:
                result_state.variable_types[variable_name].append(new_entry)

    # And now sort everything:
    for variable_name in result_state.variable_types:
        result_state.variable_types[variable_name].sort(key=operator.itemgetter(0))

    # Same code for the array items / properties
    for variable_name in result_state.array_items_or_properties:
        tmp = []
        for entry in result_state.array_items_or_properties[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number <= line_number_where_insertion_happens:
                tmp.append(entry)
            else:
                # it's a line after insertion line
                # because testcase2 gets inserted in between, the lines must be updated by the number of lines of testcase2
                tmp.append((entry_line_number + testcase2_state.testcase_number_of_lines, variable_type))
        result_state.array_items_or_properties[variable_name] = tmp
    # And now add testcase2 to the state:
    for variable_name in testcase2_state.array_items_or_properties:
        if variable_name not in result_state.array_items_or_properties:
            result_state.array_items_or_properties[variable_name] = []
        for entry in testcase2_state.array_items_or_properties[variable_name]:
            (entry_line_number, variable_type) = entry
            new_entry = (entry_line_number+line_number_where_insertion_happens, variable_type)
            if new_entry not in result_state.array_items_or_properties[variable_name]:
                result_state.array_items_or_properties[variable_name].append(new_entry)
    # And now sort everything:
    for variable_name in result_state.array_items_or_properties:
        result_state.array_items_or_properties[variable_name].sort(key=operator.itemgetter(0))

    # Fix array length values:
    # First fix part2 of testcase1:
    for variable_name in result_state.array_lengths:
        tmp = []
        for entry in result_state.array_lengths[variable_name]:
            (entry_line_number, array_length_list) = entry
            if entry_line_number <= line_number_where_insertion_happens:
                tmp.append(entry)
            else:
                # it's a line after insertion line
                # because testcase2 gets inserted in between, the lines must be updated by the number of lines of testcase2
                tmp.append((entry_line_number + testcase2_state.testcase_number_of_lines, array_length_list))
        result_state.array_lengths[variable_name] = tmp
    # And now merge testcase2 into testcase1:
    for variable_name in testcase2_state.array_lengths:
        if variable_name in result_state.array_lengths:
            # must append to an already existing list
            for entry in testcase2_state.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                entry_line_number += line_number_where_insertion_happens
                found = False
                for entry2 in result_state.array_lengths[variable_name]:
                    (entry_line_number2, array_length_list2) = entry2
                    if entry_line_number == entry_line_number2:
                        found = True
                        if array_length_list2 == array_length_list:
                            break   # this ensures that the later "array_length_list2 += array_length_list" line doesn't modify array_length_list !
                        result_state.array_lengths[variable_name].remove(entry2)
                        array_length_list2 += array_length_list
                        array_length_list2 = list(dict.fromkeys(array_length_list2))    # Remove duplicates
                        array_length_list = list(dict.fromkeys(array_length_list))  # This should not be required but just to get sure!
                        result_state.array_lengths[variable_name].append((entry_line_number, array_length_list2))
                        break
                if found is False:
                    result_state.array_lengths[variable_name].append((entry_line_number, array_length_list))
        else:   # not in result_state, so we can just write a new entry for it
            tmp = []
            for entry in testcase2_state.array_lengths[variable_name]:
                (entry_line_number, array_length_list) = entry
                tmp.append((entry_line_number+line_number_where_insertion_happens, array_length_list))
            result_state.array_lengths[variable_name] = tmp
    # And now sort everything:
    for variable_name in result_state.array_lengths:
        result_state.array_lengths[variable_name].sort(key=operator.itemgetter(0))

    return result_state
