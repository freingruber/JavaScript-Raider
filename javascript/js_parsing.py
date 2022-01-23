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



# TODO: This script can maybe be merged with the script which creates a database of variable operations?

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import native_code.speed_optimized_functions as speed_optimized_functions


# TODO:
# A multi-line instruction can also be something like:
# var_4_ += "  ];" +
# "}";
#
# so the first line can end with "+" (and likely similar characters)
# => at the moment I can't parse such instructions
def parse_next_instruction(content):
    default_high_value = 999999  # must just be longer than every possible line

    idx_bracket_type1 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "(", default_high_value)
    idx_bracket_type2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "[", default_high_value)
    idx_bracket_type3 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, "{", default_high_value)

    idx_newline = content.index("\n") if "\n" in content else default_high_value

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
        return content
    else:  # smallest != default_high_value:
        # Handle multi-line operations
        char_there = content[smallest]
        if char_there == "(":
            next_char = ")"
        elif char_there == "[":
            next_char = "]"
        elif char_there == "{":
            next_char = "}"
        elif char_there == "\n":
            # In this case only the code until "\n" needs to be returned
            return content[:smallest]

        content_part1 = content[:smallest + 1]  # +1 to include the "char_there"
        content_part2 = content[smallest + 1:]  # must still be filtered to and at "next_char"
        pos = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content_part2, next_char)
        if pos == -1:
            return None
        content_part2_real = content_part2[:pos + 1]

        # Now we need to add everything until the newline is found!
        # e.g. var_2_.someFunction().SomeOtherFunction
        # => currently "content_part1 + content_part2_real" would just be "var_2_.someFunction()"
        # => but it's required to also add ".SomeOtherFunction"
        content_part2_rest = content_part2[pos + 1:]

        already_handled_part = content_part1 + content_part2_real
        content_left = content[len(already_handled_part):]

        ret_recursion = parse_next_instruction(content_left)  # Start recursion
        if ret_recursion is None:
            code_to_return = already_handled_part + content_left
        else:
            code_to_return = already_handled_part + ret_recursion
        return code_to_return


def extract_variables_which_must_be_available_in_instr(instr, instr_line_number, instr_number_of_lines, state):
    variable_names = set()
    variable_names_final = set()

    for variable_name in state.variable_types:
        for entry in state.variable_types[variable_name]:
            (line_number, variable_type) = entry
            if instr_line_number <= line_number < (instr_line_number + instr_number_of_lines):
                variable_names.add(variable_name)
                break

    # Now >variable_names< contains variables which SHOULD be available, but which are maybe not used by the code
    for variable_name in variable_names:
        if variable_name in instr:  # note: this check should work fine for variables such as var_1_, var_2_, ... but is maybe bugged with variables like "v" or "i"
            test1 = "const %s" % variable_name
            test2 = "let %s" % variable_name
            test3 = "var %s" % variable_name
            test4 = "%s =" % variable_name
            test5 = "%s=" % variable_name
            test6 = "%s ==" % variable_name
            test7 = "%s==" % variable_name
            if test1 in instr or test2 in instr or test3 in instr:
                continue    # instruction declares it variable itself

            if test4 in instr and test6 not in instr:
                # hard to say, it could happen that the end of instr contains something like:
                # var_5_ = 123;
                # but that other code in front of this line already accesses var_5_
                # Currently I assume that this is not the case, but this maybe creates too many exceptions
                # I have to measure this
                continue

            if test5 in instr and test7 not in instr:
                continue    # same as above

            # TODO: Currently I don't take function declaration into account
            # e.g. function func_1_(var_1_)
            # => if this line is in the instruction, then var_1_ would be defined by the instr itself
            # but I'm currently not supporting this because this requires additional effort to implement

            variable_names_final.add(variable_name)

    return variable_names_final
