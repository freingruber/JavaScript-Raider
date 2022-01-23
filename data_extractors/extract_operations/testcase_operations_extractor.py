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


# To extract operations from a testcase, the function extract_operations_from_testcase()
# must be called on testcases. After that, the extracted operations can be
# accessed via the get_extracted_operations() function.
# TODO: I should rewrite this script to a class

import data_extractors.extract_operations.extract_helpers as extract_helpers
import re
import native_code.speed_optimized_functions as speed_optimized_functions



all_variable_operations = dict()
all_generic_operations = set()


# This function tries to extract all operations which occur in a testcase
# It extracts identified operations and adds all required dependencies
# For example: If one operation also uses a 2nd variable, it adds the code which creates the 2nd variable
# The function overestimates the number of operations because every possible operation is returned
# This is useful because I later check which operations result in an exception or not
# So it's better to return here "too many" instead of "too less" operations.
# TODO: The current implement is buggy and doesn't really parse the JavaScript code. It can heavily be optimized.
def extract_operations_from_testcase(content, state):
    # print("TESTCASE CONTENT:")
    # print(content)
    # print("\n"*3)
    lines = content.split("\n")

    if len(content) > 1700:
        # skip bigger files for the moment,they take very long;
        # TODO: Maybe remove the check again: However, operations from bigger files are typically useless
        return

    all_identified_instructions = set()

    for line_number in range(0, len(lines)):
        content_left = "\n".join(lines[line_number:])

        while True:
            (new_instruction, content_left) = extract_helpers.parse_next_instruction(content_left)
            if new_instruction == "":
                break
            all_identified_instructions.add(new_instruction)

        content_left = "\n".join(lines[line_number:])

        (new_instructions, state) = get_instructions_for_implicit_variables(content_left, state)
        if new_instructions is not None:
            for new_instruction in new_instructions:
                if new_instruction is not None and new_instruction != "":
                    all_identified_instructions.add(new_instruction)

    to_add = []
    for instr in all_identified_instructions:
        if "=" in instr:
            first = True
            for part in instr.split("="):
                if first:
                    # e.g:
                    # Code is: "var_TARGET_.prototype = null"
                    # Then I don't want to add the left side like:
                    # "var_TARGET_.prototype"
                    # => I just want to add "null" (because instead of null it could also be some generic operation)
                    first = False
                    continue

                part = part.strip()
                if part == "":
                    continue
                to_add.append(part)
        if "," in instr:
            for part in instr.split(","):
                part = part.strip()
                if part == "":
                    continue
                to_add.append(part)
        if "(" in instr:        # e.g. code like "if (*code*) ..." => but I also try to find this code using other techniques
            first = True
            for part in re.split(r"[\(\)]", instr):     # TODO is the regex correct??
                if first:
                    # e.g. if code is:
                    # var_1_.someFunc(someCode);
                    # => then I just want to add "someCode" as a new operation
                    # Because adding "var_1_.someFunc" without the function invocation doesn't make a lot of sense
                    first = False
                    continue
                part = part.strip()
                if part == "":
                    continue
                to_add.append(part)
                # the following code is not 100% correct, a testcase can also have && and ||
                # like if(operation1 || operation2 && operation3)
                # In this case I would not obtain "operation2" alone
                # TODO: implement all of this better, there could also be other code than "&&" and "||"
                if "&&" in part:
                    for subpart in part.split("&&"):
                        subpart = subpart.strip()
                        if subpart == "":
                            continue
                        to_add.append(subpart)
                if "||" in part:
                    for subpart in part.split("||"):
                        subpart = subpart.strip()
                        if subpart == "":
                            continue
                        to_add.append(subpart)

    for part in to_add:
        if ";\n" in part:
            for x in part.split(";\n"):
                all_identified_instructions.add(x)
        else:
            all_identified_instructions.add(part)

    # print("Before filter:")
    # for instr in all_identified_instructions:
    #    print(instr)
    #    print("----------")
    all_identified_instructions = set(filter(extract_helpers.check_if_instruction_is_valid, all_identified_instructions))
    # print("After filter:")
    # for instr in all_identified_instructions:
    #    print(instr)
    #    print("----------")

    for instr in all_identified_instructions:
        if instr.lstrip().startswith("{"):
            # I'm skipping operations which start with "{" because this are a lot
            # For example, let's assume a testcase code is:
            # function func_1_()
            # {
            # XXXXX
            # }
            # => Then a generic operation could be:
            # {
            # XXXXX
            # }
            # => Since there are a lot of different functions in all testcases, every function creates
            # such "useless" entries
            # => Therefore I remove all generic operations which start with "{"
            # => Later I identified that the same also applies to variable_operations
            continue

        identified_variables = extract_helpers.extract_variable_names_in_code(instr, state)

        """
        # Debugging code:
        print("Instruction:")
        print(instr)
        for entry in identified_variables:
            (variable_name, variable_type) = entry
            print("Variable: %s with type: %s" % (variable_name, variable_type))
        print("\n\n\n")
        """

        if len(identified_variables) == 0:
            # It's a generic operation without a variable!
            extracted_operations = add_required_dependencies(None, instr, lines, state)
            add_operation_to_global_list(None, None, extracted_operations, instr)
        else:
            for entry in identified_variables:
                (variable_name, variable_type) = entry
                extracted_variable_operations = add_required_dependencies(variable_name, instr, lines, state)
                add_operation_to_global_list(variable_name, variable_type, extracted_variable_operations, instr)


def add_operation_to_global_list(variable_name, variable_type, extracted_operations, instr):
    global all_variable_operations, all_generic_operations

    if variable_name is None:
        operations_set = all_generic_operations
    else:
        if variable_type not in all_variable_operations:
            all_variable_operations[variable_type] = set()
        operations_set = all_variable_operations[variable_type]

    if len(extracted_operations) == 0:
        extracted_operations = set()
        extracted_operations.add(instr)

    for extracted_operation in extracted_operations:
        extracted_operation = extracted_operation.strip().rstrip(";").rstrip()
        if extracted_operation == "":
            continue

        if len(extracted_operation.split("\n")) > 15:
            # operation contains more than 15 code lines
            # => in this case I skip it because I dont want to have so long operations
            continue

        extracted_operation = extract_helpers.fix_token_names_in_operation(extracted_operation, variable_name)
        operations_set.add(extracted_operation)


def get_extracted_operations():
    global all_variable_operations, all_generic_operations
    return all_variable_operations, all_generic_operations


def clear_extracted_operations():
    global all_variable_operations, all_generic_operations
    all_variable_operations = dict()
    all_generic_operations = set()


def add_required_dependencies(variable_name, current_line, lines, state):
    # print("add_required_dependencies() called for:")
    # print(current_line)
    # print("Variable_name is: %s" % variable_name)

    final_code = ""
    work_queue = []

    final_code = current_line.strip()
    already_handled_variables = []
    if variable_name is not None:
        already_handled_variables.append(variable_name)

    results = []
    work_queue.append((final_code, already_handled_variables))

    while len(work_queue) != 0:
        # print("Length of work queue at iteration start: %d" % len(work_queue))
        final_code, already_handled_variables = work_queue.pop(0)

        if len(work_queue) > 2500:
            # prevent endless loops
            return []  # stupid hack, but it just affects 1-2 testcases which result in an endless loop

        final_code_adapted = extract_helpers.remove_all_handled_variables(final_code, already_handled_variables)

        # print("Current entry is:")
        # print(final_code)
        # print("Adapted entry:")
        # print(final_code_adapted)
        # print("------------------------------\n\n\n")

        # Now search if there are any other referenced variables, functions or classes..
        found = False
        for i in range(5000):
            token_name = "var_%d_" % i
            if token_name in final_code_adapted:
                # print("Found additional dependency variable: %s" % token_name)
                possible_new_codelines = extract_helpers.find_codeline_which_creates_variable(token_name, lines, state, final_code)

                # Note: final_code can contain something like:  const var_2_ = var_5_ % var_1_;
                # And token_name is "var_2_" Since the line already creates the variable
                # The function find_codeline_which_creates_variable() will not return another line
                # Therefore I can check if the result is empty and just use the final_code in the current state
                if len(possible_new_codelines) == 0:
                    new_already_handled_variables = already_handled_variables.copy()
                    new_already_handled_variables.append(token_name)
                    work_queue.append((final_code, new_already_handled_variables))
                else:
                    for new_codeline in possible_new_codelines:
                        new_code = new_codeline + "\n" + final_code
                        new_already_handled_variables = already_handled_variables.copy()
                        new_already_handled_variables.append(token_name)
                        # print("Adding:")
                        # print(new_code)
                        # print("------------------------------\n")
                        work_queue.append((new_code, new_already_handled_variables))
                found = True
                break
        if found:
            continue

        for i in range(100):
            token_name = "func_%d_" % i
            if token_name in final_code_adapted:
                # print("DEBUGGING: Found additional dependencies-function: %s" % token_name)
                # print("final_code_adapted: %s" % final_code_adapted)
                # sys.exit(-1)

                # Note: the following code can sometimes not work, but currently I ignore these cases
                # e.g.: => if the operation is already inside the function itself like:
                #
                # function func_1_() {
                #   with(func_1_) eval("arguments[0]");
                # }
                #
                # Then it maybe creates code like:
                # function func_1_() {
                #   with(func_1_) eval("arguments[0]");
                # }
                # with(func_1_) eval("arguments[0]");

                # => I ignore these cases for the moment
                tmp = "function %s" % token_name
                if tmp in final_code_adapted:
                    new_already_handled_variables = already_handled_variables.copy()
                    new_already_handled_variables.append(token_name)
                    work_queue.append((final_code, new_already_handled_variables))
                else:
                    function_codelines = extract_helpers.find_codelines_of_function(token_name, lines)
                    if function_codelines is not None:
                        new_code = function_codelines + "\n" + final_code
                        new_already_handled_variables = already_handled_variables.copy()
                        new_already_handled_variables.append(token_name)
                        work_queue.append((new_code, new_already_handled_variables))

                found = True
                break
        if found:
            continue

        for i in range(100):
            token_name = "cl_%d_" % i
            if token_name in final_code_adapted:

                tmp = "class %s" % token_name
                if tmp in final_code_adapted:
                    new_already_handled_variables = already_handled_variables.copy()
                    new_already_handled_variables.append(token_name)
                    work_queue.append((final_code, new_already_handled_variables))
                else:
                    class_codelines = extract_helpers.find_codelines_of_class(token_name, lines)
                    if class_codelines is not None:
                        new_code = class_codelines + "\n" + final_code
                        new_already_handled_variables = already_handled_variables.copy()
                        new_already_handled_variables.append(token_name)
                        work_queue.append((new_code, new_already_handled_variables))

                found = True
                break
        if found:
            continue

        # No more dependencies, so the code is a result
        results.append(final_code)

    return results


def get_instructions_for_implicit_variables(code, state):
    first_line = code.split("\n")[0]
    # Assume first_line is something like:
    # const var_1_ = "".lastIndexOf("",3704176153);
    # => Then this function rewrites the testcase to:
    # var var_66_ = "";
    # const var_1_ = var_66_.lastIndexOf("",3704176153);
    # => Then I can extract the "lastIndexOf()" function call as an operation for strings
    # Note: var_66_ is just some unused variable ID
    new_instructions = []

    default_high_value = 999999
    idx_apostrophe_type1 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(first_line, '"', default_high_value)
    idx_apostrophe_type2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(first_line, "'", default_high_value)
    idx_apostrophe_type3 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(first_line, "`", default_high_value)

    idx_regex = speed_optimized_functions.get_index_of_next_symbol_not_within_string(first_line, "/", default_high_value)
    # print("idx_regex: %d" % idx_regex)

    found_symbols = []
    if idx_apostrophe_type1 != default_high_value:
        found_symbols.append((idx_apostrophe_type1, '"'))
    if idx_apostrophe_type2 != default_high_value:
        found_symbols.append((idx_apostrophe_type2, '"'))
    if idx_apostrophe_type3 != default_high_value:
        found_symbols.append((idx_apostrophe_type3, '"'))
    if idx_regex != default_high_value:
        found_symbols.append((idx_regex, '/'))

    if len(found_symbols) == 0:
        return None, state  # nothing to do

    for entry in found_symbols:
        (target_idx, target_symbol) = entry

        # Now find the end of the string / regexp

        code_before = code[:target_idx]

        rest = code[target_idx + 1:]

        end_idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, target_symbol, default_high_value)
        if end_idx == default_high_value:
            return None, state  # not a real string because there is no end symbol
        # print("end_idx: %d" % end_idx)

        string_content = rest[:end_idx]
        code_afterwards = rest[end_idx + 1:]

        # print("Code before: %s" % code_before)
        # print("Code afterwards: %s" % code_afterwards)
        # print("String content: %s" % string_content)

        # rewritten_code = "var var_666_ = %s%s%s;\n" % (target_symbol, string_content, target_symbol)
        next_id = state.number_variables + 1
        state.number_variables += 2
        new_variable_name = "var_%d_" % next_id
        rewritten_code = code_before + new_variable_name + code_afterwards
        # print(rewritten_code)
        (new_instruction, rewritten_code) = extract_helpers.parse_next_instruction(rewritten_code)

        new_instructions.append(new_instruction)
        # Now add the data type so that the later code knows that this is a string operation
        if target_symbol == "/":
            # it was a Regex
            state.variable_types[new_variable_name] = []
            state.variable_types[new_variable_name].append((0, "regexp"))

            # Note for the RegExp type:
            # It can happen that this doesn't work correctly because I end the Regex-String at the "/" symbol
            # However, consider this code:
            # /55/i.exec("foobar")
            # => the "i" is outside the "/" symbols, so I would incorrectly generate code like:
            # var_666_i.exec("foobar")
            # => the "i" would not be removed.
            # => Currently I just ignore this because the invalid code will later be filtered out
            # but it would be better to implement better regex handling
        else:
            # it was a string
            state.variable_types[new_variable_name] = []
            state.variable_types[new_variable_name].append((0, "string"))  # line number is 0 because the line number doesn't matter

    return new_instructions, state
