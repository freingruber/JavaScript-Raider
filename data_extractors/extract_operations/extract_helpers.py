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
import sys
import native_code.speed_optimized_functions as speed_optimized_functions
import testcase_helpers
import re
import javascript.js_helpers as js_helpers

# TODO: Merge some of these functions into the general javascript parsing module

# TODO: Merge the code with "javascript.js_parsing -> parse_next_instruction()"
# TODO: The whole code is untested and maybe doesn't really work for all cases
# It's also completely unoptimized and performance is likely very bad
# => the code was just a small PoC to get the fuzzer running, I'm planning to rewrite this soon

# TODO Code "with (0)"
# => this is not an instruction alone. The code must also add the following codelines to make this a single instruction

# Same for code like "if (var_2_) while (1);"

# try {
#      [].filter(undefined);
# }
# => This is missing the "finally" or "catch" part
#
#
# "while(....)"
# => parse the condition from the while header

#  for (var_2_ of [0]) {
# ...
def parse_next_instruction(full_content_left):
    # Check for multi-line operations like:
    # this.__defineSetter__(42, function(var_1_) {
    # }
    # );
    # Examples of multi-line operations in: tc1771.js, tc2986.js, ...
    default_high_value = 999999  # must just be longer than every possible line

    idx_bracket_type1 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(full_content_left, "(", default_high_value)
    idx_bracket_type2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(full_content_left, "[", default_high_value)
    idx_bracket_type3 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(full_content_left, "{", default_high_value)

    idx_newline = full_content_left.index("\n") if "\n" in full_content_left else default_high_value

    # Note: I should also check for closing } and so on =>
    # e.g. if I would need to add a previous line. But that will be covered via the previous line
    # and it will just lead to an invalid operation when the current code closes a bracket which was not
    # opened before. This will be filtered out during executions of the operations, so I dont implement this.
    if idx_newline < idx_bracket_type1 and idx_newline < idx_bracket_type2 and idx_newline < idx_bracket_type3:
        smallest = idx_newline
    elif idx_bracket_type1 < idx_bracket_type2 and idx_bracket_type1 < idx_bracket_type3 and idx_bracket_type1 < idx_newline:
        smallest = idx_bracket_type1
    elif idx_bracket_type2 < idx_bracket_type1 and idx_bracket_type2 < idx_bracket_type3 and idx_bracket_type2 < idx_newline:
        smallest = idx_bracket_type2
    elif idx_bracket_type3 < idx_bracket_type1 and idx_bracket_type3 < idx_bracket_type2 and idx_bracket_type3 < idx_newline:
        smallest = idx_bracket_type3
    else:
        smallest = default_high_value

    if smallest == default_high_value:
        if "\n" in full_content_left:
            print("Should never occur")
            print("full_content_left: >%s<" % full_content_left)
            print("smallest: %d" % smallest)
            print("idx_newline: %d" % idx_newline)

            sys.exit(-1)
            # return full_content_left.split("\n")[0]
        return full_content_left, ""  # no ( and { or [ => nothing to add
    else:  # smallest != default_high_value:
        # Handle multi-line operations
        char_there = full_content_left[smallest]
        if char_there == "(":
            next_char = ")"
        elif char_there == "[":
            next_char = "]"
        elif char_there == "{":
            next_char = "}"
        elif char_there == "\n":
            # In this case only the code until "\n" needs to be returned
            code_to_return = full_content_left[:smallest]
            rest = full_content_left[smallest:].lstrip("\n")
            return code_to_return, rest
        else:
            print("Internal dev error: %s" % char_there)
            # print("Testcase was: %s" % filename)
            sys.exit(-1)

        content_part1 = full_content_left[:smallest + 1]  # +1 to include the "char_there"
        content_part2 = full_content_left[smallest + 1:]  # must still be filtered to and at "next_char"
        pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content_part2, next_char)
        if pos == -1:
            """
            print("TODO will likely occur, should just continue but I want to see the testcase")
            print("Testcase was: %s" % filename)
            print("full_content_left:")
            print(full_content_left)
            print("-------------")
            """
            return "", ""
        content_part2_real = content_part2[:pos + 1]

        # Now we need to add everything until the newline is found
        # e.g. var_2_.someFunction().SomeOtherFunction
        # => currently "content_part1 + content_part2_real" would just be "var_2_.someFunction()"
        # => but it's required to also add ".SomeOtherFunction"
        content_part2_rest = content_part2[pos + 1:]

        already_handled_part = content_part1 + content_part2_real
        content_left = full_content_left[len(already_handled_part):]

        (code_to_return, rest) = parse_next_instruction(content_left)  # Start recursion
        code_to_return = already_handled_part + code_to_return
        return code_to_return, rest.lstrip("\n")


def extract_variable_names_in_code(code, state):
    all_used_variable_names = set()
    for i in range(state.number_variables+1):
        variable_name = "var_%d_" % i
        if variable_name in code:
            # Now I need to find the datatype...
            # I could exactly lookup the data type by calculating the line number of the instruction
            # and then checking the code.
            # however, I will just add the instr for all data types for the variable
            # later in the check-phase the correct data type will be identified because other will result in an exception
            # print("Variable_name: %s" % variable_name)
            # print("Variable types:")
            # print(state.variable_types)
            if variable_name not in state.variable_types:
                # can occur in code like:
                # var_2_().catch(var_1_ => {}).then(1, 1);
                # => then "var_1_" will not have an entry in a state because it can't be accessed in a code line
                continue

            all_identified_variable_types = set()
            for entry in state.variable_types[variable_name]:
                (line_number, variable_type) = entry
                if variable_type == "undefined":
                    continue
                all_identified_variable_types.add(variable_type)

            for variable_type in all_identified_variable_types:
                all_used_variable_names.add((variable_name, variable_type))

    for i in range(state.number_functions+1):
        variable_name = "func_%d_" % i
        if variable_name in code:
            all_used_variable_names.add((variable_name, "function"))
    return all_used_variable_names


# This function ensures that the main_variable_name becomes "var_TARGET_" and
# that all other variable names are modified accordingly to be contiguous
# this also includes function and class names
# => The "var_TARGET_" is then used by the fuzzer when the operation is inserted
# e.g. the fuzzer knows that var_5_ in a testcase has the correct type, then
# the fuzzer renames "var_TARGET_" to "var_5_"
# Note: "var_TARGET_" is used and not something like "var_1_" to ensure that the state creation
# for operations doesn't pick up "var_TARGET_"
def fix_token_names_in_operation(content, main_variable_name):
    if main_variable_name is not None:
        # In this case the >main_variable_name< must be renamed to >var_TARGET_<
        content = content.replace(main_variable_name, "var_TARGET_")

    # Now I need to fix all other variable/func/class names to be consecutive
    content = testcase_helpers.ensure_all_variable_names_are_contiguous(content)
    content = testcase_helpers.ensure_all_function_names_are_contiguous(content)
    content = testcase_helpers.ensure_all_class_names_are_contiguous(content)
    return content


def replace_token_with_dummy_value(code, token):
    new_tmp = "A"*len(token)    # Replace it with a token of same length => offsets don't change
    code = code.replace(token, new_tmp)
    return code


def remove_all_handled_variables(content, handled_variables):
    for variable_name in handled_variables:
        content = replace_token_with_dummy_value(content, variable_name)
    return content


def find_codeline_which_creates_variable(variable_name, code_lines, state, current_code):
    # print("find_codeline_which_creates_variable() called for variable: %s" % variable_name)
    # Hint: The code line can also be in an if / for statement
    # e.g.: if(var var_1_ = 1; ...)
    # Then I need to extract: var_1_ = 1;
    possible_create_variable_lines = set()

    # Try to detect the line via assignment
    for code_line in code_lines:
        code_line_tmp = code_line.replace(" ", "").replace("\t", "")
        tmp = "%s=" % variable_name
        tmp2 = "%s==" % variable_name
        # print("code_line_tmp:" + code_line_tmp)
        # print("tmp:"+tmp)
        if tmp in code_line_tmp and tmp2 not in code_line_tmp:  # code is something like: "var_5_ =" ; but not "var_5_==2"
            # print("INSIDE")
            # if ("if(" in code_line or "if (" in code_line or "if\t(" in code_line) and "'if" not in code_line and '"if' not in code_line:
            #    print("TODO1 implement this line:")
            #    print(code_line)
            #    sys.exit(-1)
            if "for" in code_line:
                # print("TODO2 implement this line:")
                # print("Variable: %s" % variable_name)
                # print(code_line)

                # dirty hacks to parse it....
                code_line = code_line.replace("for (", "").replace("for(", "").replace("for\t(", "")
                code_line = code_line.rstrip()
                if code_line.endswith(")"):
                    code_line = code_line[:-1]  # remove the ) from the end of the for header

                parts = re.split(r'[;,]', code_line)
                # print("TMP: %s" % tmp)
                for part in parts:
                    # print("Parts:")
                    # print(part)
                    part_tmp = part.replace(" ", "").replace("\t", "")
                    if tmp in part_tmp:
                        # print("ADDING PART:")
                        # print(part)
                        possible_create_variable_lines.add(part)

            # elif "while" in code_line:
            #    print("TODO3 implement this line:")
            #    print(code_line)
            #    sys.exit(-1)
            # elif "catch" in code_line and ".catch" not in code_line:
            #    print("TODO4 implement this line:")
            #    print(code_line)
            #    sys.exit(-1)
            # elif "with" in code_line:
            #    print("TODO5 implement this line:")
            #    print(code_line)
            #    sys.exit(-1)
            else:
                # default case => I can just use the line
                possible_create_variable_lines.add(code_line)

        # TODO: Is the string "fucnctionfunc" really correct?!?
        if "functionfunc" in code_line_tmp and variable_name in code_line_tmp:
            try:
                function_name = code_line.split("function")[-1].strip().split("(", 1)[0].strip()
                function_arguments = code_line.split("function")[-1].strip().split("(", 1)[1].split(")", 1)[0]
                function_argument_number = 0
                found = False
                for func_arg in function_arguments.split(","):
                    func_arg = func_arg.strip()
                    if variable_name == func_arg:
                        found = True
                        break
                    function_argument_number += 1
                if found:
                    # Now search for function invocations:
                    invocation_code = function_name + "("
                    for possible_function_invocation_code in code_lines:
                        possible_function_invocation_code = possible_function_invocation_code.strip()
                        if invocation_code in possible_function_invocation_code and possible_function_invocation_code.startswith("function") is False:
                            # ("Found function invocation: %s" % possible_function_invocation_code)
                            invocation_args = possible_function_invocation_code.split("(", 1)[-1].split(")", 1)[0]
                            invocation_args_parts = invocation_args.split(",")
                            if len(invocation_args_parts) > function_argument_number:
                                value = invocation_args_parts[function_argument_number].strip()
                                if value == "":
                                    possible_create_variable_lines.add("var %s = undefined;" % variable_name)
                                else:
                                    possible_create_variable_lines.add("var %s = %s;" % (variable_name, value))
                            else:
                                # it means the argument is not defined => therefore the value is "undefined"
                                possible_create_variable_lines.add("var %s = undefined;" % variable_name)
            except:
                pass

    # Try to detect the line via the state. This should result in most cases in the same identified lines...
    found_line_numbers = dict()
    if variable_name in state.variable_types:
        for entry in state.variable_types[variable_name]:
            (line_number, variable_type) = entry
            if line_number not in found_line_numbers:
                found_line_numbers[line_number] = []
            found_line_numbers[line_number].append(variable_type)

    first = True
    prev_datatypes = None
    for i in range(len(code_lines) + 1):
        if i in found_line_numbers:
            if first:
                prev_datatypes = found_line_numbers[i]
                first = False
                if i == 0:
                    continue  # would be variable hoisting
                code_line = code_lines[i - 1]
                if variable_name in code_line:
                    # print("HERE1")
                    # print(code_line)
                    if code_line.startswith("function ") is False:
                        possible_create_variable_lines.add(code_line)
            else:  # first = False
                current_datatypes = found_line_numbers[i]
                if current_datatypes != prev_datatypes:
                    # data type changes which means the last operation must have assigned something to the variable
                    code_line = code_lines[i - 1]
                    if variable_name in code_line:
                        # print("HERE2")
                        # print(code_line)
                        if code_line.startswith("function ") is False:
                            possible_create_variable_lines.add(code_line)
                prev_datatypes = current_datatypes

    # print("Found following code lines which create variable: %s" % variable_name)

    tmp_possible_create_variable_lines = []

    for x in possible_create_variable_lines:
        should_take_codeline = True
        for already_stored_codeline in current_code.split("\n"):
            if x == already_stored_codeline:
                should_take_codeline = False
                break
        if should_take_codeline:
            tmp_possible_create_variable_lines.append(x)

    return tmp_possible_create_variable_lines


def find_codelines_of_class(token_name, lines):
    content = "\n".join(lines)

    original_content = content

    to_search = "class %s" % token_name
    pos = content.find(to_search)
    if pos == -1:
        return None

    start_position = pos
    end_position = start_position
    content = content[pos:]

    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "{")  # class ... { <---
    if pos == -1:
        print("TODO2 HERE class")
        sys.exit(-1)
    pos += 1  # +1 to skip the "{", otherwise a search for "}" would not work
    end_position += pos
    content = content[pos:]
    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "}")  # class ... { ... } <---
    if pos == -1:
        print("TODO3 HERE class")
        sys.exit(-1)
    end_position += pos

    class_code = original_content[start_position:end_position + 1]
    return class_code


def find_codelines_of_function(token_name, lines):
    content = "\n".join(lines)
    # print("Content is:")
    # print(content)

    original_content = content

    to_search = "function %s" % token_name
    # print("To search:")
    # print(to_search)

    pos = content.find(to_search)
    if pos == -1:
        # Fallback to generators
        to_search = "function* %s" % token_name
        pos = content.find(to_search)
        if pos == -1:
            return None

    start_position = pos
    end_position = start_position
    content = content[pos:]

    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "(")  # function xxx( <---
    if pos == -1:
        return None
    pos += 1  # +1 to skip the "(", otherwise a search for ")" would not work
    end_position += pos
    content = content[pos:]
    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, ")")  # function xxx(..) <---
    if pos == -1:
        return None
    end_position += pos
    content = content[pos:]
    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "{")  # function xxx(..) { <---
    if pos == -1:
        return None
    pos += 1  # +1 to skip the "{", otherwise a search for "}" would not work
    end_position += pos
    content = content[pos:]
    pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "}")  # function xxx(..) { ... } <---
    if pos == -1:
        return None
    end_position += pos

    function_code = original_content[start_position:end_position + 1]
    # print("Function code is:")
    # print(function_code)
    # print("-------------")
    return function_code


def get_hash_of_normalized_operation(code):
    code = testcase_helpers.remove_numbers_from_testcase(code)
    code = testcase_helpers.remove_strings_from_testcase(code)
    # Note: Just removing strings is not enough, I would also need to change the string symbols
    # e.g.:
    # 'foobar' will become ''
    # "foobar" will become ""
    # => '' and "" are different and would therefore still be added to the operations
    # but changing '' to "" could lead to some problems (?) and therefore I'm currently not doing this
    # can this really lead to problems? Should not happen too often..
    code = code.strip().rstrip(";").strip()
    sample_hash = utils.calc_hash(code)
    return sample_hash


def get_code_to_instantiate_obj(variable_type):
    datatype_str = js_helpers.convert_datatype_str_to_real_JS_datatype(variable_type)   # e.g. "dataview" => "DataView"

    if datatype_str is None:
        code_to_instantiate_obj = ""
        utils.perror("[-] Error with data type (convert_datatype_str_to_real_JS_datatype() returned None): %s" % variable_type)
    else:
        code_to_instantiate_obj = js_helpers.get_code_to_create_variable_of_datatype(datatype_str)

    code = "var var_TARGET_ = %s;" % code_to_instantiate_obj
    return code


def check_if_instruction_is_valid(code):
    idx_start = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "(", 999999)
    idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, ")", 999999)
    if idx_end < idx_start:
        return False

    idx_start = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "[", 999999)
    idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "]", 999999)
    if idx_end < idx_start:
        return False

    idx_start = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "{", 999999)
    idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "}", 999999)
    if idx_end < idx_start:
        return False

    code = code.strip()

    if "var var_" in code:
        # code like:
        # var var_5_ = 1234;
        # is not an operation which I want to save
        return False

    if "const var_" in code:
        return False
    if "let var_" in code:
        return False

    if code.startswith("class "):
        return False  # new class definitions are not "operations" for me
    if code.startswith("function ") or code.startswith("async function "):
        return False  # same for functions
    if code.startswith("catch "):
        return False

    if code == "yield;" or code == "yield":
        return False

    if code.startswith("continue ") or code.startswith("return "):
        # TODO: later maybe add "return" but ensure that this operation is just added in a function context..
        return False  # could make sense to add these operations, however, when I will test the operations in an empty testcase they would already throw an exception and would therefore not be included

    if code.startswith("switch "):
        return False

    if code.startswith("while("):
        return False

    if code.startswith("while ("):
        return False

    if code.startswith("if ("):
        return False

    if code.startswith("if("):
        return False
    if code == "if" or code == "while" or code == "yield" or code == "throw" or code == "switch" or code == "continue" or code == "return" or code == "function" or code == "class" or code == "catch":
        return False

    if code.startswith("throw "):
        return False

    if code.startswith("%OptimizeFunctionOnNextCall") or code.startswith("%PrepareFunctionForOptimization") or code.startswith(
            "%NeverOptimizeFunction") or code.startswith("%DeoptimizeFunction"):
        # adding them to generic operations would result in a lot of operations because as dependencies it would
        # add all different functions
        # therefore I skip them and add these operations manually via a mutation
        return False

    if code.startswith("new cl_"):
        return False  # same principal as above, just for classes

    # TODO: invalid escape sequence?
    if bool(re.search(r"func_[0-9]_\(", code)):
        return False  # function invocations are also not added

    return True
