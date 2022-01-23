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



# This mutation strategy tries to moves operations around in the testcase.

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import re
import javascript.js_parsing as js_parsing


# TODO:
# The current code is just a simple heuristic, and often doesn't move lines around (although it would be possible)
# what I really would need is to create a dependency tree, e.g. which line/operation depends on which other operations
# and then I can create an order and know which lines I'm allowed to move where...
# e.g. currently I don't move lines like "var var_1_ = " around, because my code currently can move it everywhere
# and it's likely that the variable is used later. However, it should be fine to move this line backwards (in the current block)
# However, the line itself could also access other variables and the line must therefore be executed after the other variables are
# created.
# TODO: At least implement that variable declarations can be moved backwards (in the current block)
# TODO: Also note that this mutation will not do a lot when executed on a single testcase
# my corpus is heavily size optimized, so it's likely that no lines can easily be moved around
# => it's mainly useful when I combine multiple testcases or I insert new code lines (e.g. from the database)
def mutation_move_operation_around(content, state):
    # utils.dbg_msg("Mutation operation: Move operation around")
    tagging.add_tag(Tag.MUTATION_MOVE_OPERATION_AROUND1)

    lines = content.split("\n")
    number_of_lines = len(lines)
    possible_line_numbers_to_move = []
    lines_within_try_block = testcase_mutators_helpers.get_line_numbers_within_try_block(content)
    # print(state)
    for line_number in state.lines_where_code_can_be_inserted:
        if line_number == number_of_lines:
            continue
        if line_number in lines_within_try_block:
            continue

        # TODO: Maybe sometimes (very unlikely) ignore these rules and still try to move
        # lines around which likely result in an exception?

        current_line = lines[line_number].lstrip(" \t")
        if "do{" in current_line or "do {" in current_line or current_line == "do":
            continue
        if "try{" in current_line or "try {" in current_line or current_line == "try":
            continue
        # if "for(" in current_line or "for (" in current_line or current_line == "for":
        #    continue
        if "`" in current_line:
            # at the moment I don't support `-strings (which are maybe multi-line)
            continue
        if current_line == "}" or current_line.startswith("}"):
            continue
        if "function " in current_line:
            continue
        if "super(" in current_line or "super." in current_line:
            continue
        if "throw " in current_line:
            continue
        if "break " in current_line or "break;" in current_line:
            continue
        if "else " in current_line:
            continue
        if "class " in current_line:
            continue
        if "return " in current_line or "return;" in current_line:
            continue
        if "const " in current_line or "var " in current_line or "let " in current_line:
            # TODO just skip this sometimes
            # The problem is that if I move these lines around, then it's likely that an exception will be created
            # because a specific variable will not be available in one of the following code lines
            continue

        if current_line.startswith("var_"):     # TODO: and what is with other variables? but it's hard for variables such as "v" to implement the following checks
            current_line_without_space = current_line.replace(" ", "")
            if "_=" in current_line_without_space and "_==" not in current_line_without_space:
                # It's a line like: "var_1_ = ..." which maybe defines a variable for the first time. Moving this line around (especially to a higher line number) likely leads in an exception
                variable_name_end_idx = 4   # len("var_")
                while current_line[variable_name_end_idx] != "_" and variable_name_end_idx < len(current_line):    # var_1_ => I'm searching for the 2nd "_" (the end of the variable name)
                    # TODO maybe check if the ID in var_ID_ is numeric?
                    variable_name_end_idx += 1

                variable_name = current_line[:variable_name_end_idx + 1]
                if state.is_variable_available_and_not_undefined_in_line(variable_name, line_number) is False:
                    # the variable is not defined in the line, however, the variable is accessed ! (in line like "var_1_ =")
                    # => It's therefore a variable declaration and should be skipped
                    continue

        # TODO: I still have the problem that all these checks are just "initial" checks for the current_line and not
        # for the operation. If the current line is an if-statement and in the if-body a variable declaration is found
        # then I still move lines around (which can result in exceptions). That's because I just check "current_line"
        # and not "instr_to_move" (which gets calculated later)

        # print("LINE: %d : %s" % (line_number, current_line))
        # TODO: "return" in the line? => this should just be moved around within the function context!
        possible_line_numbers_to_move.append(line_number)

    if len(possible_line_numbers_to_move) == 0:
        tagging.add_tag(Tag.MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING2)
        return content, state

    # print("possible_line_numbers_to_move:")
    # print(possible_line_numbers_to_move)

    line_number_instr = utils.get_random_entry(possible_line_numbers_to_move)
    # print("line_number_instr: %d" % (line_number_instr))
    instr_to_move = js_parsing.parse_next_instruction('\n'.join(lines[line_number_instr:]))
    # print("instr_to_move: %s" % (instr_to_move))
    if instr_to_move is None or instr_to_move.startswith('"use strict"'):
        # This means parsing didn't work, most likely because I started parsing inside a string
        # e.g. inside a multi-line `-string which is later evaluated and therefore contains something code-like
        # if the eval is inside a try-catch block it's very likely that the code is not valid and therefore
        # parsing will not work (e.g. a } is missing)
        # Theoretically I could check other line numbers here, but I don't want to introduce too long loops here
        # so I'm just returning and do nothing
        tagging.add_tag(Tag.MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING3)
        return content, state
    instr_to_move_number_of_lines = len(instr_to_move.split("\n"))
    # print("Instr: %s" % instr_to_move)
    # print("Number of lines: %d" % instr_to_move_number_of_lines)
    # print("Testcase: %s" % state.testcase_filename)

    # Currently it also shifts if() statements around. do I really want this?
    # theoretically I could also support for() loops ...

    # do - while and try-catch would need some extra engineering... because try is followed by catch/finally
    # or do is followed by while which must be parsed

    forbidden_line_targets = set()
    if "func_" in instr_to_move:
        # there is a function invocation in the instruction, so I must check if e.g. func_1_() doesn't call itself
        # in an endless loop => this would lead to an exception (max. recursion depth)
        # => so I first extract the names of all functions

        # TODO: I should measure the runtime of regex checks vs. manual implementation?
        all_function_names = set(re.findall(r'func_[\d]*_', instr_to_move))
        for func_name in all_function_names:
            lines_of_func = testcase_mutators_helpers.get_all_codelines_of_function(func_name, content)
            # print("FUNCTION CODE LINES: %s" % func_name)
            # print(lines_of_func)
            forbidden_line_targets |= lines_of_func


    must_be_available_variables = js_parsing.extract_variables_which_must_be_available_in_instr(instr_to_move, line_number_instr, instr_to_move_number_of_lines, state)
    # print("must_be_available_variables:")
    # print(must_be_available_variables)
    # TODO: The array lengths would also need to match in the moved line.... (same for properties)
    # hm.. but maybe it's good that I'm "fuzzing" this a little bit... I just need to ensure that
    # I don't create too many exceptions

    # Calculate lines to which the code can be moved...
    possible_destinations = []

    possible_lines_where_code_can_be_inserted = list(set(state.lines_where_code_can_be_inserted) - set(state.lines_which_are_not_executed))
    for line_number in possible_lines_where_code_can_be_inserted:
        if line_number_instr <= line_number <= (line_number_instr + instr_to_move_number_of_lines):
            # Note the 2nd check with "<=" instead of "<"
            # The equal sign is required because I also want to skip the line after the current instruction
            # If I would move the operation exactly after the operation, I would remove the operation from it's place
            # and insert it back again exactly after it's previous position => the line would not move, so I would do nothing
            # therefore such lines are not valid targets
            continue    # line number would be inside the instr which gets moved

        if line_number in forbidden_line_targets:
            continue

        if testcase_mutators_helpers.check_if_variables_are_available_in_line(must_be_available_variables, line_number, state) is False:
            continue    # not all variables are available and therefore moving instr to this line would likely create an exception, so skip it
        possible_destinations.append(line_number)

    if len(possible_destinations) == 0:
        tagging.add_tag(Tag.MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING4)
        return content, state

    random_new_line_number = utils.get_random_entry(possible_destinations)

    instr_lines = []
    for idx in range(instr_to_move_number_of_lines):
        instr_lines.append(lines[line_number_instr])
        del lines[line_number_instr]

    if random_new_line_number > line_number_instr:
        random_new_line_number -= instr_to_move_number_of_lines     # because I removed the lines

    # print("instr verification: %s" % "\n".join(instr_lines))
    instr_lines.reverse()   # insert backwards, then I don't need to change the index during insertion
    for instr_line in instr_lines:
        lines.insert(random_new_line_number, instr_line)

    content = "\n".join(lines)
    # print("Final code:")
    # print(content)
    # print("-----------")
    # input("<press enter>")

    # TODO: The state must be updated!
    # Edit: currently I'm not doing it, this would just be required if array lengths change
    # or if the moved instruction creates variables...
    # => Maybe it makes sense to make this a "late mutation" which doesn't need to change the state?
    # => Or I maybe implement the state modification when I have more time (and motivation)

    return content, state
