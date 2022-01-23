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
import native_code.speed_optimized_functions as speed_optimized_functions
import testcase_helpers
import javascript.js as js
import javascript.js_helpers as js_helpers
import re
import mutators.database_operations as database_operations


def get_start_and_end_lines_to_wrap(content, state, lines, number_of_lines):
    # TODO starts with:
    # const  => don't wrap these lines in a for loop, but in if it would be allowed (?)
    # class
    # function (?)
    # 'use strict' ???
    # => TODO "Avoid code lines"

    """
    Later I need to parse the operations correctly, e.g. Code like this:
    var var_5_ = [
    String.prototype = Promise.prototype,
    ];
    => I cannot wrap just the first code line because all 3 lines are just one operation
    """

    tagging.add_tag(Tag.GET_START_AND_END_LINES_TO_WRAP1)

    avoid_line_numbers = set()
    line_number = 0
    for line in lines:
        line_stripped = line.strip()
        if "let " in line:
            avoid_line_numbers.add(line_number)
        if "const " in line:
            avoid_line_numbers.add(line_number)
        if "function*" in line or "function " in line or "function(" in line:
            # the function would just be available in the if/for-block and therefore it will
            # very likely lead to an exception
            avoid_line_numbers.add(line_number)
        if line_stripped == "try" or "try " in line or "try{" in line:
            # TODO later I can also parse try and ensure that the catch/finally block is also
            # there but currently I'm not parsing the operations...
            avoid_line_numbers.add(line_number)
        if "`" in line:
            # I have some problems with `strings` and this skips them
            avoid_line_numbers.add(line_number)
        line_number += 1

    # utils.msg("[i] Avoid code lines: %s" % str(avoid_line_numbers))

    (possible_start_line_numbers_to_wrap, cached_curley_bracket_blocks) = get_possible_start_codelines_to_wrap(content, state, lines, number_of_lines)

    # Filter out all avoid lines
    possible_start_line_numbers_to_wrap = [x for x in possible_start_line_numbers_to_wrap if x not in avoid_line_numbers]

    if len(possible_start_line_numbers_to_wrap) == 0:
        tagging.add_tag(Tag.GET_START_AND_END_LINES_TO_WRAP2_DO_NOTHING)
        return -1, -1

    random_start_code_line = utils.get_random_entry(possible_start_line_numbers_to_wrap)

    possible_end_line_numbers_to_wrap = get_possible_end_codelines_to_wrap(content, state, lines, number_of_lines, random_start_code_line, cached_curley_bracket_blocks)

    # Filter out all avoid lines
    tmp = []
    for possible_end_line_number in possible_end_line_numbers_to_wrap:
        # utils.msg("[i] Testing possible end line: %d" % possible_end_line_number)
        should_skip = False
        for avoid_line in avoid_line_numbers:
            # utils.msg("[i] \tTesting avoid line: %d" % avoid_line)
            if random_start_code_line <= avoid_line <= possible_end_line_number:
                # the wrap-code lines contain an avoid_line, so remove this entry
                should_skip = True
                break
        if should_skip:
            # utils.msg("[i] skipping the end line!")
            continue
        tmp.append(possible_end_line_number)
    possible_end_line_numbers_to_wrap = tmp

    if len(possible_end_line_numbers_to_wrap) == 0:
        tagging.add_tag(Tag.GET_START_AND_END_LINES_TO_WRAP3_DO_NOTHING)
        return -1, -1

    random_end_code_line = utils.get_random_entry(possible_end_line_numbers_to_wrap)
    # utils.msg("[i] Selected as random start code line: %d" % random_start_code_line)
    # utils.msg("[i] Selected as random end code line: %d" % random_end_code_line)

    # Some final safety checks
    code_to_wrap = ""
    code_to_wrap_len = 0
    for line_number in range(random_start_code_line, random_end_code_line + 1):
        code_to_wrap += lines[line_number] + "\n"
        code_to_wrap_len += 1

    # print("Testcase:")
    # print(content)
    # print("-----------")
    # print("code_to_wrap:")
    # print(code_to_wrap)

    skip_mutation = False
    if "case " in code_to_wrap and "switch" not in code_to_wrap:
        skip_mutation = True
    if "{" not in code_to_wrap and code_to_wrap_len == 1:
        if "if " in code_to_wrap or "for " in code_to_wrap or "while " in code_to_wrap:
            # code like:
            # "if (!(var_1_ instanceof cl_1_))"
            # => the next line is required and it's not possible to just wrap it here
            skip_mutation = True

    # The following checks are not 100% correct because of strings,
    # and these checks will not be required as soon as I parse operations
    # but for the moment I add them as hotfix
    # TODO: Parse operations and remove these checks
    if code_to_wrap.count("(") != code_to_wrap.count(")"):
        skip_mutation = True
    elif code_to_wrap.count("[") != code_to_wrap.count("]"):
        skip_mutation = True
    elif code_to_wrap.count("{") != code_to_wrap.count("}"):
        skip_mutation = True

    if skip_mutation:
        tagging.add_tag(Tag.GET_START_AND_END_LINES_TO_WRAP4_DO_NOTHING)
        return -1, -1
    return random_start_code_line, random_end_code_line


def wrap_codelines(state, lines, start_code_line, end_code_line, code_prefix, code_suffix):
    tagging.add_tag(Tag.WRAP_CODELINES1)

    # Insert the START of the FOR-Loop
    new_code_line = code_prefix
    lines.insert(start_code_line, new_code_line)
    new_content = "\n".join(lines)                  # TODO I need to calculate here ".join()" just for state_insert_line() and below a 2nd time..: Improve performance
    state.state_insert_line(start_code_line, new_content, new_code_line)

    # Insert the END of the FOR-Loop
    end_code_line += 1+1   # +1 because I inserted a line in front of it; and +1 to add the code after the code line
    new_code_line = code_suffix
    lines.insert(end_code_line, new_code_line)
    new_content = "\n".join(lines)
    state.state_insert_line(end_code_line, new_content, new_code_line)
    return new_content, state


def get_possible_end_codelines_to_wrap(content, state, lines, number_of_lines, start_line_number, curley_bracket_blocks):
    last_line_of_block = -1
    is_start_of_a_block = False  # if start_line_number is the start of a block I need to wrap the full block!

    for entry in curley_bracket_blocks:
        (start_line, end_line) = entry
        if start_line == start_line_number:
            is_start_of_a_block = True
            break

    # There are two versions, one if it's the start of a block and below the one if it's not the start of a block
    if is_start_of_a_block:
        for entry in curley_bracket_blocks:
            (start_line, end_line) = entry
            if start_line == end_line:
                continue
            # It's important to use below "==" (if it start_line_number is within multiple blocks)
            if start_line_number == start_line and start_line_number < end_line:
                if last_line_of_block == -1:
                    last_line_of_block = end_line
                else:
                    # If it's the start of a block and there are multiple blocks, this means that
                    # I would need to take the bigger block, e.g. code like:
                    # 01: blabal {{{
                    # 02: }
                    # 03: }
                    # 04: }
                    # => Then I need to take 04 and not 02
                    if end_line > last_line_of_block:
                        last_line_of_block = end_line
    else:
        for entry in curley_bracket_blocks:
            (start_line, end_line) = entry
            if start_line == end_line:
                continue
            if start_line < start_line_number < end_line:
                # The start line is in the current block, so the last possible line to move is
                # end_line-1 because if I would wrap >end_line<, then the block would become invalid
                tmp = end_line - 1
                if last_line_of_block == -1:
                    last_line_of_block = tmp
                else:
                    # in this case another block was already found. We need to take the "smallest" block
                    # which always has "end_line" the smallest value
                    if tmp < last_line_of_block:
                        last_line_of_block = tmp

    if last_line_of_block == -1:
        # no block found, so we can wrap everything
        last_line_of_block = number_of_lines - 1  # set it to last line number

    candidates = []
    if is_start_of_a_block:
        candidates.append(last_line_of_block)
    else:
        # TODO This code doesn't take into account symbols such as "("
        # e.g. if an operation is multi-line like 2 lines, then this code maybe just wraps
        # the first line and not the 2nd, although the 2nd is required for the first line to work
        # This can be fixed by parsing the operations using my >parse_next_instruction()< function
        # but this function is not yet completely working and therefore I decided to not use it here yet
        # The code will therefore currently create some easily avoidable exceptions

        # print("Now performing check for start_line_number: %d" % start_line_number)
        for i in range(start_line_number, last_line_of_block + 1):
            possible_end_line_number = i
            # print("\tpossible_end_line_number candidate is: %d" % possible_end_line_number)
            # I'm now looking for blocks in which >possible_end_line_number< is, but in which
            # >start_line_number< not is. If that's the case I can surely not wrap these code lines
            # because I would wrap in the middle of a block (e.g. the block starts somewhere between
            # start_line_number and possible_end_line_number)
            # However, if the start of the block is after >start_line_number< and possible_end_line_number
            # is equal to the end of the block, then I can wrap because I would wrap the full block

            should_skip_this_entry = False
            for entry in curley_bracket_blocks:
                (start_line, end_line) = entry
                # Check1: Check for blocks which start after >start_line_number< (so start_line_number can't be in this block)
                # print("\tChecking block %d - %d" % (start_line, end_line))
                if start_line > start_line_number:
                    # print("\tstart_line_number > start_line")
                    # Check2: Check if >possible_end_line_number< is within this block:
                    if start_line <= possible_end_line_number <= end_line:
                        # print("\tpossible_end_line_number >= start_line and possible_end_line_number <= end_line")
                        # It's inside the block
                        if possible_end_line_number == end_line:
                            # print("\tpossible_end_line_number == end_line")

                            # it's the end of the block, so wrapping would wrap the full block
                            # which is possible and safe
                            continue
                        else:
                            # print("\tpossible_end_line_number != end_line")
                            # it's in the middle of a block, so wrapping would break the block
                            should_skip_this_entry = True
                            break

            if should_skip_this_entry:
                # print("Skipping")
                continue
            candidates.append(possible_end_line_number)

    return candidates


def get_possible_start_codelines_to_wrap(content, state, lines, number_of_lines):
    curley_bracket_blocks = get_curley_bracket_blocks_as_line_numbers(content, state)

    all_end_curley_bracket_lines = set()
    # Now get all end }-lines. A line where {-starts is a possible start line to wrap
    # because the full "{" block can be wrapped!
    # However, I can't wrap a line line "}" alone which will always throw an exception
    for entry in curley_bracket_blocks:
        (start_line, end_line) = entry
        if start_line != end_line:  # if "{" and "}" is in the same line, then I can also wrap this code line
            all_end_curley_bracket_lines.add(end_line)

    possible_locations = []
    for line_number in state.lines_where_code_can_be_inserted:
        if line_number == number_of_lines:
            continue  # skip the "append line" because this line doesn't exist yet and can therefore not be wrapped
        if line_number in all_end_curley_bracket_lines:
            continue

        code_line = lines[line_number]
        if "function()" in code_line or "function " in code_line:
            continue  # skip function because I don't want to if/for wrap function definitions
        if "class " in code_line:
            continue
        if '"use strict"' in code_line:
            continue

        possible_locations.append(line_number)

    return possible_locations, curley_bracket_blocks


# TODO: This function is very similar to
# get_lines_with_curly_brackets()
# I think I implemented the functionality twice, remove one of the functions...
# The other one returns a set and here I return a list
# and here I also recalculate the curley brackets (which is necessary)
def get_curley_bracket_blocks_as_line_numbers(content, state):
    ret = []
    state.calculate_curly_bracket_offsets(content)  # recalculate, in case some other modifications change the length of the content and didn't update the curley bracket list...

    for entry in state.curly_brackets_list:
        (opening_bracket_index, closing_bracket_index) = entry
        start_line = speed_optimized_functions.get_line_number_of_offset(content, opening_bracket_index)
        end_line = speed_optimized_functions.get_line_number_of_offset(content, closing_bracket_index)
        ret.append((start_line, end_line))
    return ret


def get_code_lines_without_forbidden_words(lines):
    forbidden_words = ["if", "for", "switch", "case", "{", "}", "async", "class", "catch", "var ", "let ", "const ", "default:", "do ", "do{", "finally", "function", "while", "with"]
    possibilities_top_insert_if = []
    line_number = -1
    for line in lines:
        line_number += 1
        ignore_line = False
        for forbidden_word in forbidden_words:
            if forbidden_word in line:
                # print("Forbidden word >%s< in line: %s" % (forbidden_word, line))
                ignore_line = True
                break
        if ignore_line:
            continue
        possibilities_top_insert_if.append(line_number)
    return possibilities_top_insert_if


def get_positions_of_all_numbers_in_testcase(content):
    identified_locations = []

    identified_locations += get_positions_of_regex_pattern(r"[-]{1}0[xX][0-9a-fA-F]+", content)  # negative hex numbers
    identified_locations += get_positions_of_regex_pattern(r"0[xX][0-9a-fA-F]+", content)  # positive hex numbers
    identified_locations += get_positions_of_regex_pattern(r"[-]{1}0[bB][0-1]+", content)  # negative binary numbers
    identified_locations += get_positions_of_regex_pattern(r"0[bB][0-1]+", content)  # positive binary numbers
    identified_locations += get_positions_of_regex_pattern(r"[-]{1}[\d]*[.]{0,1}[\d]+", content)  # negative numbers
    identified_locations += get_positions_of_regex_pattern(r"[\d]*[.]{0,1}[\d]+", content)  # positive numbers

    # Now something like:
    # 6.176516726456e-312;
    # -.1e3
    # 123.e-2
    identified_locations += get_positions_of_regex_pattern(r"[-]{0,1}[\d]*[.]{0,1}[\d]*[e][-]{0,1}[\d]+", content)
    # TODO: The above regex is for some testcases very slow
    # e.g. tc9804.js or tc9991.js

    identified_locations = list(dict.fromkeys(identified_locations))  # remove duplicates
    return identified_locations


def get_positions_of_all_bigints_in_testcase(content):
    identified_locations = []
    identified_locations += get_positions_of_regex_pattern(r"[-]{1}[\d]+n", content)  # negative bigints
    identified_locations += get_positions_of_regex_pattern(r"[\d]+n", content)  # positive bigints
    identified_locations = list(dict.fromkeys(identified_locations))  # remove duplicates
    return identified_locations


def get_positions_of_regex_pattern(pattern, content, ignore_additional_check=False):
    identified_locations = []
    matches = re.findall(pattern, content)
    content_search = content
    for matched_str in matches:
        if matched_str not in content_search:
            continue  # should not occur
        start_index = content_search.index(matched_str)
        length_of_number = len(matched_str)
        end_index = start_index + length_of_number
        if ignore_additional_check or check_if_correct_replacement_position(content_search, matched_str):
            identified_locations.append((start_index,
                                         end_index - 1))  # -1 because I just want that end_index points to the last character of the pattern (e.g. number) and not to the next symbol
        content_search = content_search[:start_index] + "a" * length_of_number + content_search[end_index:]
    return identified_locations


def get_positions_of_all_variables_in_testcase(content):
    return get_positions_of_regex_pattern(r"var_[\d]+_", content)


def get_positions_of_all_variables_in_testcase_without_assignment(content):
    identified_locations = []
    lines = content.split("\n")
    tmp = get_positions_of_all_variables_in_testcase(content)

    for entry in tmp:
        (start_offset, end_offset) = entry
        original_value = content[start_offset:end_offset + 1]
        line_number = speed_optimized_functions.get_line_number_of_offset(content, start_offset)
        line = lines[line_number]

        forbidden_substrings = []
        forbidden_substrings.append("let %s" % original_value)
        forbidden_substrings.append("var %s" % original_value)
        forbidden_substrings.append("const %s" % original_value)
        forbidden_substrings.append("%s=" % original_value)  # prevent variables in left-hand assignments
        forbidden_substrings.append("%s =" % original_value)  # prevent variables in left-hand assignments
        forbidden_substrings.append("%s\t=" % original_value)  # prevent variables in left-hand assignments
        forbidden_substrings.append("%s=" % original_value)  # prevent variables in left-hand assignments
        forbidden_substrings.append("catch (")  # catch(var_1_) => this is also an assignment to var_1_
        forbidden_substrings.append("catch\t(")  # catch(var_1_) => this is also an assignment to var_1_
        forbidden_substrings.append("catch(")  # catch(var_1_) => this is also an assignment to var_1_

        is_valid_entry = True
        for forbidden_substring in forbidden_substrings:
            if forbidden_substring in line:
                is_valid_entry = False
                break
        if is_valid_entry:
            identified_locations.append(entry)

    identified_locations = list(dict.fromkeys(identified_locations))  # remove duplicates
    return identified_locations


def check_if_correct_replacement_position(content_search, substr_to_replace):
    # print("check_if_correct_replacement_position()")
    # print("substr_to_replace: %s" % substr_to_replace)
    # print("content_search:")
    # print(content_search)
    # print("#######")

    if substr_to_replace not in content_search:
        return False  # It means it was already previously replaced
    idx = content_search.index(substr_to_replace)
    if idx == -1:
        utils.perror("Logic flow in check_if_correct_replacement_position()")
    if idx == 0:
        char_before = " "
    else:
        char_before = content_search[idx - 1]
    try:
        char_after = content_search[idx + len(substr_to_replace)]
    except:
        char_after = " "  # could happen if "substr_to_replace" is at the end of the testcase
    # print("Char before: %s" % char_before)
    # print("Char after: %s" % char_after)

    content_before = content_search[:idx]

    if char_after.isalnum() or char_after == "_":
        return False
    if char_before.isalnum() or char_before == "_":
        return False
    return True


def get_positions_of_all_strings_in_testcase(content):
    identified_locations = []
    identified_locations += get_all_string_positions_with_start_character(content, '"')
    identified_locations += get_all_string_positions_with_start_character(content, "'")
    identified_locations += get_all_string_positions_with_start_character(content, "`")
    identified_locations = list(dict.fromkeys(identified_locations))  # remove duplicates
    return identified_locations


def get_all_string_positions_with_start_character(content, start_character):
    identified_locations = []
    ensure_loop_ends = 0
    while True:
        ensure_loop_ends += 1
        if ensure_loop_ends > 5000:
            return []  # something strange happened, and this should never occur (and I'm pretty sure this code will never execute)
        idx_start = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, start_character)
        if idx_start == -1:
            return identified_locations

        content = content[:idx_start] + "X" + content[idx_start + 1:]  # temp. replace

        idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, start_character)
        if idx_end == -1:
            return identified_locations
        content = content[:idx_end] + "X" + content[idx_end + 1:]  # temp. replace

        identified_locations.append((idx_start, idx_end))


def get_lines_with_curly_brackets(content, state):
    lines = set()
    # In the testcase state only the indexes are stored of curly brackets
    # This helper functions converts them to line numbers
    for entry in state.curly_brackets_list:
        (opening_bracket_index, closing_bracket_index) = entry
        lines.add(speed_optimized_functions.get_line_number_of_offset(content, opening_bracket_index))
        lines.add(speed_optimized_functions.get_line_number_of_offset(content, closing_bracket_index))
    return lines



def check_if_variables_are_available_in_line(must_be_available_variables, line_number, state):
    # at_least_one_variable_is_undefined = False
    for variable_name in must_be_available_variables:
        variable_is_available = False
        for entry in state.variable_types[variable_name]:
            (entry_line_number, variable_type) = entry
            if entry_line_number == line_number:
                if variable_type == "undefined":
                    # If just one entry is undefined it means the variable is not available in that line
                    # e.g. it can happen that I have entries like:
                    # (1, 'undefined')
                    # (1, 'real_number')
                    # => that means that in line 1 the variable is one time undefined and later a number
                    # This happens when a code line is executed in a loop (and e.g. the loop body creates the variable)
                    # Then the variable is not available in the first iteration but in a later one
                    # But I still need to return False because the variable is not available in the first iteration
                    # and it's likely that could would therefore lead to an exception in the first iteration
                    # which expects that the variable is available
                    return False
                else:
                    variable_is_available = True
                    # break => don't break, maybe it's "undefined" in another entry (e.g. a loop which undefines a variable in a 2nd or n'th iteration)
        if variable_is_available is False:
            return False

    # tagging.add_tag(Tag.CHECK_IF_VARIABLES_ARE_AVAILABLE_IN_LINE1)
    # if at_least_one_variable_is_undefined == True:
    #     tagging.add_tag(Tag.CHECK_IF_VARIABLES_ARE_AVAILABLE_IN_LINE2)  # TODO check this tag
    return True


def get_all_codelines_of_function(func_name, content):
    identified_lines = set()

    content_test = content.replace("\t", " ").replace("\n", " ")  # don't change the length here

    pattern = "function %s" % func_name
    if pattern not in content_test:
        return identified_lines  # couldn't find the function (maybe the testcase uses a different syntax)

    lines = content.split("\n")

    idx = content_test.find(pattern)
    rest = content_test[idx:]
    start_idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "{")
    if start_idx == -1:
        return identified_lines

    rest2 = rest[
            start_idx + 1:]  # TODO: I should not copy here the strings... later remove the string copy to boost performance
    end_idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest2, "}")
    if end_idx == -1:
        return identified_lines

    func_start_idx = idx
    func_end_idx = func_start_idx + start_idx + 1 + end_idx

    func_start_line_number = testcase_helpers.content_offset_to_line_number(lines, func_start_idx)
    func_end_line_number = testcase_helpers.content_offset_to_line_number(lines, func_end_idx)
    for line_number in range(func_start_line_number, func_end_line_number + 1):
        identified_lines.add(line_number)

    return identified_lines


# TODO: At the moment I'm not moving lines inside try-catch blocks around
# theoretically I can move them WITHIN the try-catch block around.
# Maybe I will implement this later
# TODO: I should move these calculations into state calculations... and don't perform them during fuzzing
# => but then I need to perform some logic when merging states; I think it depends on how often I'm using this
# function during fuzzing. Because merging states are always performed, whereas this function is just sometimes called
# => maybe it's better to calculate this just on-demand
def get_line_numbers_within_try_block(content):
    identified_lines = set()
    lines = content.split("\n")

    content_left = content.replace("\t", " ").replace("\n", " ")  # make sure to also find try\t and try\n

    total_current_offset = 0

    while True:

        idx = -1
        if "try " in content_left:
            idx = content_left.find("try ")

        if "try{" in content_left:
            if idx == -1:
                # just get the idx because "try " was not in the content
                idx = content_left.find("try{")
            else:
                # in this case we need to identify which string occurs first
                idx2 = content_left.find("try{")
                if idx2 < idx:
                    idx = idx2

        if idx == -1:
            # no more try-blocks
            return identified_lines

        rest = content_left[idx:]
        start_idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "{")
        if start_idx == -1:
            return identified_lines

        rest2 = rest[
                start_idx + 1:]  # TODO: I should not copy here the strings... later remove the string copy to boost performance
        end_idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest2, "}")
        if end_idx == -1:
            return identified_lines

        try_start_idx = total_current_offset + idx
        try_end_idx = try_start_idx + start_idx + 1 + end_idx

        try_start_line_number = testcase_helpers.content_offset_to_line_number(lines, try_start_idx)
        try_end_line_number = testcase_helpers.content_offset_to_line_number(lines, try_end_idx)
        for line_number in range(try_start_line_number, try_end_line_number + 1):
            identified_lines.add(line_number)

        # Now update the content_left and the offset to it

        content_left = content_left[try_end_idx - total_current_offset + 1:]
        total_current_offset = try_end_idx + 1

        # some debugging tests; can later be removed
        # start_chr = content[try_start_idx]
        # end_chr = content[try_end_idx]
        # if start_chr != "t" or end_chr != "}":
        #    print("Logic flaw in get_line_numbers_within_try_block()!")
        #    print("start_chr: %s" % start_chr)
        #    print("end_chr: %s" % end_chr)
        #    print("try_start_idx: %d" % try_start_idx)
        #    print("try_end_idx: %d" % try_end_idx)
        #    print("idx: %d" % idx)
        #    print("start_idx: %d" % start_idx)
        #    print("end_idx: %d" % end_idx)
        #    print("Input was:")
        #    print(content)
        #    sys.exit(-1)

    return identified_lines     # TODO: This line can't be reached because it's after an endless loop??



def get_start_and_end_line_symbols(state, line_number, content):
    if line_number in state.lines_where_code_can_be_inserted:
        tagging.add_tag(Tag.GET_START_AND_END_LINE_SYMBOLS_SEMICOLON)
        start_line_with = ""
        end_line_with = ";"
    elif line_number in state.lines_where_code_with_coma_can_be_inserted:
        tagging.add_tag(Tag.GET_START_AND_END_LINE_SYMBOLS_END_COMA)
        start_line_with = ""
        end_line_with = ","
    elif line_number in state.lines_where_code_with_start_coma_can_be_inserted:
        tagging.add_tag(Tag.GET_START_AND_END_LINE_SYMBOLS_START_COMA)
        start_line_with = ","
        end_line_with = ""
    else:
        utils.msg("[i] Content:\n%s" % content)
        utils.msg("[i] State:\n%s" % state)
        utils.perror("Logic flaw in get_start_and_end_line_symbols() with line_number %d" % line_number)
    return start_line_with, end_line_with


def get_random_line_number_to_insert_code(state, maybe_remove_line_zero=True):
    possible_lines = state.lines_where_code_can_be_inserted + state.lines_where_code_with_coma_can_be_inserted + state.lines_where_code_with_start_coma_can_be_inserted
    possible_lines = list(set(possible_lines) - set(state.lines_which_are_not_executed))
    if maybe_remove_line_zero:
        if len(possible_lines) > 1:
            if 0 in possible_lines and utils.likely(0.85):
                # I'm mainly using this function to identify locations where I can apply operations
                # adding an operation in line 0 doesn't make so much sense because I can just add there generic operations
                # and not operations on variables
                # => the generic operation could create a new variable which can then be used in the first line of the original testcase
                # but that's just a corner case. In most cases I want to apply operations on available variables
                # So in most cases I remove line 0 to ensure at least some variables are available for mutations
                # TODO: That's a general problem.
                # if line 1-5 create 5 variables, then var_5_ will not receive as many variable operations as var_1_ during fuzzing
                # because var_1_ can be mutated in line 2,3,4,5,6
                # whereas var_5_ can just be mutated in line 6....
                possible_lines.remove(0)
    random_line_number = utils.get_random_entry(possible_lines)

    # utils.msg("[i] get_random_line_number_to_insert_code() returns line number %d with state: %s" % (random_line_number, state))
    return random_line_number


def get_proto_change_lhs(state, line_number):
    tagging.add_tag(Tag.GET_PROTO_CHANGE_LHS1)

    possibilities = set()
    for func_number in range(state.number_functions):
        possibilities.add("func_%d_" % (func_number + 1))
    for class_number in range(state.number_classes):
        possibilities.add("cl_%d_" % (class_number + 1))

    already_added = False
    if len(possibilities) == 0 or utils.likely(0.8):
        tagging.add_tag(Tag.GET_PROTO_CHANGE_LHS2)
        possibilities.update(js.get_all_globals())
        already_added = True

    # add variables
    available_variables = get_all_available_variables(state, line_number)
    possibilities.update(available_variables)

    lhs = utils.get_random_entry(list(possibilities))

    if already_added is False:
        possibilities.update(js.get_all_globals())

    return lhs, list(possibilities)


def get_prototype_change_lhs(state):
    tagging.add_tag(Tag.GET_PROTOTYPE_CHANGE_LHS1)

    possibilities = []
    for func_number in range(state.number_functions):
        possibilities.append("func_%d_" % (func_number + 1))
    for class_number in range(state.number_classes):
        possibilities.append("cl_%d_" % (class_number + 1))

    already_added = False
    if len(possibilities) == 0 or utils.likely(0.8):
        tagging.add_tag(Tag.GET_PROTOTYPE_CHANGE_LHS2)
        possibilities = possibilities + js.get_instanceable_builtin_objects_full_list()
        already_added = True
    lhs = utils.get_random_entry(possibilities)
    if already_added is False:
        possibilities = possibilities + js.get_instanceable_builtin_objects_full_list()
    return lhs, possibilities


def get_proto_change_rhs(state, line_number, code_possibilities):
    tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS1)
    target_choices = [1, 2, 3, 4, 5,
                      6]  # ATTENTION, if I modify this, I also need to change >target_choices< below in option 1
    rnd = utils.get_random_entry(target_choices)
    rhs = ""
    if rnd == 1:
        # Set it to a variable
        available_variables = get_all_available_variables(state, line_number)
        if len(available_variables) == 0:
            # Try one of the other possibilities
            tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS2)
            target_choices = [2, 3, 4, 5, 6]  # without 1
            rnd = utils.get_random_entry(target_choices)
        else:
            tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS3)
            rhs = utils.get_random_entry(available_variables)
    if rnd == 2:  # if instead of elif because in option1 I can reset rnd to 2
        # Set it to a .prototype
        tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS4)
        rhs = "%s.prototype" % utils.get_random_entry(code_possibilities)
    elif rnd == 1:
        pass  # already handled above
    elif rnd == 3:
        # set it to a .__proto__
        tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS5)
        tmp = set()
        tmp.update(code_possibilities)  # already contains: js.get_instanceable_builtin_objects_full_list()
        tmp.update(js.get_all_globals())
        rhs = "%s.__proto__" % utils.get_random_entry(list(tmp))
    elif rnd == 4:
        # set it to a global
        tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS6)
        rhs = utils.get_random_entry(js.get_all_globals())
    elif rnd == 5:
        # set it to a full random thing:
        tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS7)
        available_variables = get_all_available_variables(state, line_number)
        rhs = js.get_random_js_thing(available_variables, state, line_number)
    elif rnd == 6:
        # set it to something special
        tagging.add_tag(Tag.GET_PROTO_CHANGE_RHS8)
        special_possibilities = ["{}", "[]", "-0", "null", "undefined", "Object.assign.__proto__"]
        rhs = utils.get_random_entry(special_possibilities)
    else:
        utils.perror("Internal error in mutation_change_prototype()")

    return rhs


# This function returns available variables, array items and properties
def get_all_available_variables_with_datatypes(state, line_number, exclude_undefined=True):
    tagging.add_tag(Tag.GET_AVAILABLE_VARIABLES_WITH_DATATYPES1)
    ignore_undefined_variables = True

    if exclude_undefined is False:
        if utils.likely(0.001):
            # Make it very unlikely to also consider undefined variables
            tagging.add_tag(Tag.GET_AVAILABLE_VARIABLES_WITH_DATATYPES2)
            ignore_undefined_variables = False

    variables_with_datatype = state.get_available_variables_in_line_with_datatypes(line_number, exclude_undefined=ignore_undefined_variables)
    items_or_properties_with_datatype = state.get_available_array_items_or_properties_in_line_with_datatypes(line_number, exclude_undefined=ignore_undefined_variables)

    # Important: Don't merge both lists and randomly select a variable
    # => since I will very likely have a lot more array items that would
    # lead to many operations performed on array items and not on "variables"
    # => the same problem currently occurs with the "properties"
    # because I typically have 1 entry for a property but often arrays with ~10 items
    # so it's 10 times more likely to perform the operation on an array item instead of the property
    # for the moment that's the situation, maybe I will fix it later
    if len(items_or_properties_with_datatype) == 0 or utils.likely(0.5):
        tagging.add_tag(Tag.GET_AVAILABLE_VARIABLES_WITH_DATATYPES3)
        possible_variables = variables_with_datatype

        if utils.likely(0.95):
            tagging.add_tag(Tag.GET_AVAILABLE_VARIABLES_WITH_DATATYPES4)
            # In most cases (but not always) remove the following variables
            # Reason: They are available in every testcase and I don't want to perform too many operations on them
            if "this" in possible_variables:
                del possible_variables['this']
            if "globalThis" in possible_variables:  # this should not be required because globalThis is the data type and not the variable name?
                del possible_variables['globalThis']
            if "arguments" in possible_variables:
                del possible_variables['arguments']
    else:
        tagging.add_tag(Tag.GET_AVAILABLE_VARIABLES_WITH_DATATYPES5)
        # TODO: The exception rate with this branch is very high (27% instead of 15%)
        possible_variables = items_or_properties_with_datatype
    return possible_variables


# TODO move this function and get_all_available_variables_with_datatypes
# into the state
def get_all_available_variables(state, line_number, exclude_undefined=True):
    available_variables_with_datatype = get_all_available_variables_with_datatypes(state, line_number, exclude_undefined)
    tmp = set()
    for variable_name in available_variables_with_datatype:
        tmp.add(variable_name)
    return list(tmp)


# This function is just used for debugging js.get_random_js_thing()
# e.g. to check if it returns valid code
# I'm manually calling this function via developer_mode.py
def debugging_call_get_random_js_thing(content, state, line_number):
    possible_other_variables = get_all_available_variables(state, line_number)
    return js.get_random_js_thing(possible_other_variables, state, line_number)


def get_random_array_operation(content, state, line_number, array_name, array_lengths):
    tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION1)

    possible_other_variables = get_all_available_variables(state, line_number)
    (start_line_with, end_line_with) = get_start_and_end_line_symbols(state, line_number, content)

    variation = utils.get_random_int(1, 18)
    if variation == 1:
        # Set array length to zero
        if utils.likely(0.5):
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION2)
            line_to_add = "%s.length=0;gc();" % array_name
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION3)
            line_to_add = "%s.length=0;gc();gc();" % array_name
    elif variation == 2:
        # Set array length to zero and back to the original length
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION4)
        line_to_add = "let tmp=%s.length; %s.length=0; gc(); gc(); %s.length=tmp;" % (array_name, array_name, array_name)
    elif variation == 3:
        # Store a double value in the array
        random_index = utils.get_random_int(0, 5)
        if utils.likely(0.5):
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION5)
            line_to_add = "%s[%d] = 1.1;" % (array_name, random_index)
        else:
            # 6.176516726456e-312 => 0x12312345671 (internally)
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION6)
            line_to_add = "%s[%d] = 6.176516726456e-312;" % (array_name, random_index)
    elif variation == 4:
        # Store an object in the array
        random_index = utils.get_random_int(0, 5)
        if utils.likely(0.5):
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION7)
            line_to_add = "%s[%d] = {};" % (array_name, random_index)
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION8)
            line_to_add = "%s[%d] = Math;" % (array_name, random_index)
    elif variation == 5:
        # Store an integer in the array
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION9)
        random_index = utils.get_random_int(0, 5)
        line_to_add = "%s[%d] = 1337;" % (array_name, random_index)
    elif variation == 6:
        # neuter the array buffer + trigger gc()
        # TODO:
        # This is no longer called "ArrayBufferNeuter", but instead "ArrayBufferDetach" now
        # And it only works on typed arrays like Uint8Array!
        # var buffer1 = new ArrayBuffer(100 * 1024);
        # var array1 = new Uint8Array(buffer1);
        # %ArrayBufferDetach(buffer1);

        # Note: in typed arrays we can also do "array1.buffer" like:
        # var buffer1 = new ArrayBuffer(100 * 1024);
        # var array1 = new Uint8Array(buffer1);
        # %ArrayBufferDetach(array1.buffer);

        # => This only works with typed arrays! (e.g. not with Array() but just for something like Uint8Array)
        array_datatypes = state.get_variable_types_in_line(array_name, line_number)
        array_datatype_correct = None
        if array_datatypes is not None:
            for array_datatype_entry in array_datatypes:
                if "array" in array_datatype_entry:
                    array_datatype_correct = array_datatype_entry
                    break  # break and just take the first array data type... I think it's not too common that I have multiple array datatypes
        if array_datatype_correct is None or array_datatype_correct == "array":
            # use another operation for an array which should work
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION31)
            line_to_add = "%s.length=0;gc();" % array_name
        else:
            # In this case it's a typed array like Uint8Array and it's therefore possible to access ".buffer"
            if utils.likely(0.5):
                tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION10)
                line_to_add = "%%ArrayBufferDetach(%s.buffer);gc();" % array_name
            else:
                tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION11)
                line_to_add = "%%ArrayBufferDetach(%s.buffer);gc();let tmp = 71748523475265n - 16n;" % array_name
    elif variation == 7:
        # Store a random thing in the array
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION12)
        random_index = utils.get_random_int(0, 5)
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "%s[%d] = %s;" % (array_name, random_index, random_value)
    elif variation == 8:
        # access very high index to make array a dict
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION13)
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "%s[0x2000001] = %s;" % (array_name, random_value)
    elif variation == 9:
        # Just access the entry
        max_len = get_random_array_length(array_lengths)
        if utils.likely(0.3) and max_len != 0:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION14)
            random_accessible_idx = max_len - 1
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION15)
            random_accessible_idx = utils.get_random_int(0, max_len)
        line_to_add = "%s[%d];" % (array_name, random_accessible_idx)
    elif variation == 10:
        # set accessible entry to random thing
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        max_len = get_random_array_length(array_lengths)
        if utils.likely(0.3) and max_len != 0:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION16)
            random_accessible_idx = max_len - 1
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION17)
            random_accessible_idx = utils.get_random_int(0, max_len)
        line_to_add = "%s[%d]=%s;" % (array_name, random_accessible_idx, random_value)
    elif variation == 11:
        # delete accessible entry
        max_len = get_random_array_length(array_lengths)
        if utils.likely(0.3) and max_len != 0:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION18)
            random_accessible_idx = max_len - 1
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION19)
            random_accessible_idx = utils.get_random_int(0, max_len)
        line_to_add = "delete %s[%d];" % (array_name, random_accessible_idx)
    elif variation == 12:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION20)
        # This code results very often in an exception, so just try-catch wrap it
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "try { %s.length += %s; } catch {};" % (array_name, random_value)
    elif variation == 13:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION21)
        random_value1 = js.get_random_js_thing(possible_other_variables, state, line_number)
        random_value2 = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "%s[%s] = %s;" % (array_name, random_value1, random_value2)
    elif variation == 14:
        # neuter an array and set the array back to a normal array

        array_datatypes = state.get_variable_types_in_line(array_name, line_number)
        array_datatype_correct = None
        if array_datatypes is not None:
            for array_datatype_entry in array_datatypes:
                if "array" in array_datatype_entry:
                    array_datatype_correct = array_datatype_entry
                    break  # break and just take the first array data type... I think it's not too common that I have multiple array datatypes
        if array_datatype_correct is None or array_datatype_correct == "array":
            # use another operation for an array which should work
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION32)
            line_to_add = "%s.length=0;gc();" % array_name
        else:
            array_datatype_correct_real = js_helpers.convert_datatype_str_to_real_JS_datatype(array_datatype_correct)
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION22)
            random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
            line_to_add = "let tmp=%s.length;%%ArrayBufferDetach(%s.buffer);gc();gc();%s=new %s();%s.length=tmp;%s.fill(%s,0,tmp-1);" % (
                array_name, array_name, array_name, array_datatype_correct_real, array_name, array_name, random_value)

    elif variation == 15:
        # Just access an array value
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION33)
        array_index = get_random_array_index(state, line_number, array_name)
        line_to_add = "%s[%s];" % (array_name, array_index)
    elif variation == 16:
        # Set a specific array entry to a value
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION34)
        array_index = get_random_array_index(state, line_number, array_name)
        array_value = get_random_array_entry_value(state, line_number)
        line_to_add = "%s[%s] = %s;" % (array_name, array_index, array_value)
    elif variation == 17:
        # Perform a mathematical assign operation on a specific array entry
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION35)
        array_index = get_random_array_index(state, line_number, array_name)
        array_value = get_random_array_entry_value(state, line_number)
        math_assignment_operation = js.get_random_js_math_assignment_operation()  # something like "+=" or "*="
        line_to_add = "%s[%s] %s %s;" % (array_name, array_index, math_assignment_operation, array_value)
    elif variation == 18:
        # Perform a mathematical operation on a specific array entry
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION36)
        array_index = get_random_array_index(state, line_number, array_name)
        array_value = get_random_array_entry_value(state, line_number)
        math_operation = js.get_random_js_math_operation()  # something like "+" or "<<"
        line_to_add = "%s[%s] %s %s;" % (array_name, array_index, math_operation, array_value)
        # TODO also "++" or "--" ?
    else:
        utils.perror("Internal error: get_random_array_operation()")

    if end_line_with != ";":
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION23)
        # if line starts with ";" nothing would be to do because it's already in correct format
        should_wrap_in_immediately_invoked_function_expression = True

        if line_to_add.count(";") == 1:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION24)
            # just one ";" at the end (because one ";" is always at the end)
            if utils.likely(0.5):
                # Let's try sometimes to not use a iife
                tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION25)
                should_wrap_in_immediately_invoked_function_expression = False

        if should_wrap_in_immediately_invoked_function_expression is False:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION26)
            line_to_add = line_to_add.rstrip(";")
            if line_to_add.count(";") != 0:
                utils.perror("Logic flaw in get_random_array_operation(): %s" % line_to_add)
            line_to_add = start_line_with + line_to_add + end_line_with
        else:
            # use an iife
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION27)
            # TODO: Maybe the iife should return something? That would easily be possible of line_to_add just contains 1 instruction
            # but it's more complex if there are multiple instructions
            # Semantically it should also returns something...
            # e.g. if line_to_add is "var_5_[2];" and if it's inserted here:
            # func_1_(1,2,
            # *INSERTION*
            # 3);
            #
            # => Then I would create without iife this code:
            # func_1_(1,2,
            # var_5_[2],
            # 3);
            #
            # But with iife I would create this code:
            # func_1_(1,2,
            # var_5_[2],
            # 3);
            #
            # which is semantically different

            # Let's try to fix it at least for single-instructions:
            if line_to_add.count(";") == 1:
                if utils.likely(0.5):
                    tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION28)
                    line_to_add = "return %s" % line_to_add
                else:
                    tagging.add_tag(
                        Tag.GET_RANDOM_ARRAY_OPERATION29)  # log it so that I can compare the executions results in both cases
                    pass  # do nothing
            line_to_add = start_line_with + iife_wrap(line_to_add) + end_line_with
    else:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_OPERATION30)

    return line_to_add






def get_random_array_index(state, line_number, array_name):
    tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX1)
    variation = utils.get_random_int(1, 5)
    if variation == 1:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX2)
        return js.get_int()
    elif variation == 2:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX3)
        random_int = js.get_int()
        random_int = decompose_number(random_int)
        return random_int
    elif variation == 3:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX4)
        return js.get_special_value()
    elif variation == 4:
        # using the array name I can check which array indexes are in use (from state) and then use a random one of them:
        used_indexes = state.get_used_array_indexes_in_line(array_name, line_number)
        if len(used_indexes) == 0:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX5)
            return js.get_int()    # return random int
        else:
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX6)
            random_index_entry_as_str = utils.get_random_entry(used_indexes)
            return random_index_entry_as_str
    elif variation == 5:
        # TODO get the variable names => some available variable names?
        # or create a new variable
        # => call math operation ?
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_INDEX7)
        random_math_operation = get_random_math_operation_for_array_index(state, line_number)
        return random_math_operation
    else:
        utils.perror("Internal error: get_random_array_index()")



def get_random_array_entry_value(state, line_number):
    tagging.add_tag(Tag.GET_RANDOM_ARRAY_ENTRY_VALUE1)
    variation = utils.get_random_int(1, 4)
    if variation == 1:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_ENTRY_VALUE2)
        return "1.39064994160909e-309"
    elif variation == 2:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_ENTRY_VALUE3)
        return "{}"
    elif variation == 3:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_ENTRY_VALUE4)
        return "0xabcdefaa"
    elif variation == 4:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_ENTRY_VALUE5)
        possible_other_variables = get_all_available_variables(state, line_number)
        return js.get_random_js_thing(possible_other_variables, state, line_number)
    else:
        utils.perror("Internal error: get_random_array_entry_value()")


def get_random_array_length(array_lengths):
    tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH1)
    if len(array_lengths) == 0:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH2_RARE)
        random_entry = "undefined"
    else:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH3)
        random_entry = utils.get_random_entry(array_lengths)
    if random_entry == "undefined" or random_entry == '':
        if utils.likely(0.1):
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH4_RARE)
            tmp = js.get_int()
            if "." in tmp:  # because of the database of Integers, get_int() can return values such as '-18.0' which would lead to an exception in int()
                tmp = tmp.split(".")[0]
            if tmp.startswith("0x"):
                try:
                    return int(tmp, 16)
                except:
                    return 0
            try:
                return int(tmp, 10)
            except:
                return 0    # could happen because it seems "tmp" can be empty..?
        return 0

    try:
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH5)
        if isinstance(random_entry, str):
            # Should not occur anymore because the length values are now stored as numbers and not as strings..
            if random_entry.startswith("0x"):
                try:
                    return int(random_entry, 16)
                except:
                    return 0
            tmp_ret = int(random_entry, 10)
        else:
            return random_entry
    except:
        # EDIT: I think this can no longer occur, an exception was thrown because
        # I had a typo in the above code. I still keep this code just to get sure.

        # Old comment:
        # With 3 testcases it can occur that an exception is thrown here:
        # tc9443.js, tc9926.js, tc9980.js
        # These testcases have entries like '13.37,13.37,13.37' in the array length
        # These testcases where created with fuzzilli and imported to the corpus
        # The testcases execute simplified code like:
        # const var_6_ = [13.37,13.37,13.37];
        # const var_4_ = [var_6_];
        # const var_2_ = {__proto__:var_4_,length:var_6_, /**/}
        # The proto is set to var_4_ which means var_2_ returns in my state calculation as data type array.
        # And the length was set to var_6_ which then becomes the string '13.37,13.37,13.37'
        # edit:
        # I'm now storing length values as "numbers" in the state and no longer as string (to save space)
        # => This case here should no longer occur
        tmp_ret = 0
        tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH6_RARE)
        if utils.likely(0.1):
            tagging.add_tag(Tag.GET_RANDOM_ARRAY_LENGTH7_RARE)
            tmp = js.get_int()
            try:
                return int(tmp, 10)
            except:
                return 0
        return 0
    return tmp_ret


# TODO: Move this into "js.py"
def get_random_math_operation_for_array_index(state, line_number):
    # This function should create something like the following:
    # array[base + 0x7FFFFFE1]
    # from Chromium issue 469058, CVE-2015-1233

    # a1[(x >> 16) * 0xf00000] =
    # from https://github.com/tunz/js-vuln-db/blob/master/v8/CVE-2015-1233.md

    # MEM[x | 0] =

    # Int32ArrayView[i1>>10] =
    # from https://github.com/tunz/js-vuln-db/blob/master/v8/CVE-2016-1653.md

    # m32[((1-Math.sign(NaN) >>> 0) % 0xdc4e153) & v]
    # https://github.com/tunz/js-vuln-db/blob/master/v8/CVE-2016-5200.md

    # TODO: Also introduce calls like: Math.sign()
    # => I can just call such a function below on the operands but I need to know which functions

    number_of_operations = utils.get_random_int(1, 5)
    number_of_variables = utils.get_random_int(1,
                                               2)  # 1 operation => max 2 variables; if I modify the above, I also need to modify this one here

    numeric_variables = state.get_available_numeric_tokens_in_line(line_number)

    operands = [None] * (number_of_operations + 1)  # if I have 1 operation I need 1+1=2 operands
    operators = [None] * number_of_operations

    if len(numeric_variables) != 0:
        for i in range(0, number_of_variables):
            random_index = utils.get_random_int(0, number_of_operations)
            operands[random_index] = utils.get_random_entry(numeric_variables)

    for i in range(0, number_of_operations + 1):
        if i != number_of_operations:
            operators[i] = js.get_random_js_math_operation()
        if operands[i] is None:
            if utils.likely(0.9):
                operands[i] = js.get_int()
            else:
                operands[i] = js.get_special_value()

    # TODO: also introduce somewhere "(" and ")"?
    tmp_result = ""
    tmp_result += operands[0]
    for i in range(0, number_of_operations):
        tmp_result += operators[i]
        tmp_result += operands[i + 1]

    return tmp_result


def decompose_number(previous_number):
    tagging.add_tag(Tag.DECOMPOSE_NUMBER1)

    prefix = ""
    # Modify the number by decomposing the number
    # e.g. if the number is "3" then replace it for example with "1+1+1"
    # or if the number was "-0" replace it by "-0-0"
    # or if the number was "83" replace it by "(84*2+83) % 84"
    # or if it was "83" replace it by "100000083 & 0x00ff"
    # utils.dbg_msg("Decomposing number: %s" % previous_number)

    handled = False

    if previous_number == "-0":
        tagging.add_tag(Tag.DECOMPOSE_NUMBER2)
        # handle -0 specially
        if utils.likely(0.1):  # 0.05
            tagging.add_tag(Tag.DECOMPOSE_NUMBER3)
            # Use a -0 version with a prefix-string
            possibilities = [1, 2, 3, 4, 5, 6, 7, 8, 9]
            random_choice = utils.get_random_entry(possibilities)
            if random_choice == 1:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER4)
                prefix = "Object.defineProperty(Math.pow, \"length\", {value: -0,writable: true});\n"
                new_number = "Math.pow.length"
                return new_number, prefix
            elif random_choice == 2:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER5)
                prefix = "let minus_zero = new Map();Object.defineProperty(minus_zero, \"size\", {value: -0,writable: true});\n"
                new_number = "minus_zero.size"
                return new_number, prefix
            elif random_choice == 3:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER6)
                prefix = "let minus_zero2 = [-0];Array.prototype.__defineGetter__('minus_zero_prop', Object.prototype.valueOf);\n"
                new_number = "minus_zero2['minus_zero_prop'][0]"
                return new_number, prefix
            elif random_choice == 4:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER7)
                prefix = "this.__defineGetter__(\"null\", function() {return -0});\n"
                new_number = "this.null"
                return new_number, prefix
            elif random_choice == 5:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER8)
                prefix = "var Math = Object.create(Math);Object.defineProperty(Math, \"PI\", {value: -0,writable: true});\n"
                new_number = "Math.PI"
                return new_number, prefix
            elif random_choice == 6:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER9)
                prefix = "Math.acos = function (...args) {return -0};\n"
                new_number = "Math.acos(0)"
                return new_number, prefix
            elif random_choice == 7:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER10)
                prefix = "let _ = new ArrayBuffer(1); let minus_zero_view = new DataView(_); minus_zero_view[0] = -0;\n"
                new_number = "minus_zero_view[0]"
                return new_number, prefix
            elif random_choice == 8:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER11)
                # -9223372036854775808n is a -0 as Float64
                prefix = "let _ = new ArrayBuffer(16); let minus_zero_view = new DataView(_); minus_zero_view.setBigInt64(0,-9223372036854775808n);\n"
                new_number = "minus_zero_view.getFloat64(0)"
                return new_number, prefix
            elif random_choice == 9:
                tagging.add_tag(Tag.DECOMPOSE_NUMBER12)
                prefix = "let minus_zero_weakmap_key = {}; let minus_zero_weakmap = new WeakMap();minus_zero_weakmap.set(minus_zero_weakmap_key, -0);\n"
                new_number = "minus_zero_weakmap.get(minus_zero_weakmap_key)"
                return new_number, prefix
            else:
                utils.perror("Internal logic error, wrong value")
        else:
            tagging.add_tag(Tag.DECOMPOSE_NUMBER13)
            new_number = utils.get_random_entry(js.possibilities_to_write_minus_zero)
            # print("new_number: %s" % new_number)
            return new_number, prefix

    # Handle negative values
    if previous_number[0] == "-":
        tagging.add_tag(Tag.DECOMPOSE_NUMBER14)
        tmp = previous_number[1:]
        (x1, x2) = decompose_number(tmp)
        return "-(%s)" % x1, x2

    new_number = previous_number

    if "." in previous_number:
        tagging.add_tag(Tag.DECOMPOSE_NUMBER15)
        previous_number_without_dot = previous_number.replace(".", "")
        if previous_number_without_dot.isdigit():  # really just a float and not something special like 1.2e5
            # handle floating point numbers
            tagging.add_tag(Tag.DECOMPOSE_NUMBER16)
            value = float(previous_number)
            possibilities = [1, 2, 3, 4, 5]
            random_choice = utils.get_random_entry(possibilities)
            if random_choice == 1:
                # just split the value
                tagging.add_tag(Tag.DECOMPOSE_NUMBER17)
                if value > 10 ** 308:
                    # don't modify the value, because otherwise a python exception would be thrown.
                    # e.g.:
                    # (10**309) / 2.0
                    # =>
                    # OverflowError: int too large to convert to float
                    new_number = "%d" % value
                else:
                    # default code
                    value_half = value / 2.0
                    new_number = "%f + %f" % (value_half, value_half)
            elif random_choice == 2:
                # add 1 and at runtime subtract 1
                tagging.add_tag(Tag.DECOMPOSE_NUMBER18)
                random_value = js.get_int_as_number()
                value_plus = value + random_value
                new_number = "%f - %d" % (value_plus, random_value)
            elif random_choice == 3:
                # sub 1 and at runtime add 1
                tagging.add_tag(Tag.DECOMPOSE_NUMBER19)
                random_value = js.get_int_as_number()
                value_sub = value - random_value
                new_number = "%f + %d" % (value_sub, random_value)
            elif random_choice == 4:
                # same as before but just with float
                tagging.add_tag(Tag.DECOMPOSE_NUMBER20)
                random_value_str = js.get_double()
                try:
                    random_value = float(random_value_str)
                except:
                    random_value = 0  # can happen if it's a special JavaScript float which python can't understand
                value_plus = value + random_value
                new_number = "%f - %s" % (value_plus, random_value_str)
            elif random_choice == 5:
                # same as before but just with float
                tagging.add_tag(Tag.DECOMPOSE_NUMBER21)
                random_value_str = js.get_double()
                try:
                    random_value = float(random_value_str)
                except:
                    random_value = 0  # can happen if it's a special JavaScript float which python can't understand
                value_plus = value - random_value
                new_number = "%f + %s" % (value_plus, random_value_str)
            handled = True
    elif previous_number.isdigit():
        # just an integer
        tagging.add_tag(Tag.DECOMPOSE_NUMBER22)
        value = int(previous_number, 10)
        possibilities = [1, 2, 3, 4, 5]
        random_choice = utils.get_random_entry(possibilities)
        if random_choice == 1:
            # can result in wrong numbers like 3 => 1.5+1.5 but I just print 1+1, but that's ok, we are fuzzing...
            tagging.add_tag(Tag.DECOMPOSE_NUMBER23)

            if value > 10 ** 308:
                # don't modify the value, because otherwise a python exception would be thrown.
                # e.g.:
                # (10**309) / 2.0
                # =>
                # OverflowError: int too large to convert to float
                new_number = "%d" % value
            else:
                # default code
                value_half = value / 2.0
                new_number = "%d + %d" % (value_half, value_half)
        elif random_choice == 2:
            # Replace something like 306 with "306 & 510" which should be still the same
            # Round up to multiple of 0xff
            tagging.add_tag(Tag.DECOMPOSE_NUMBER24)
            k = 0xff
            m = value % k
            tmp = value
            if m > 0:
                tmp = value + k - m
            new_number = "%d %% %d" % (value, tmp)
        elif random_choice == 3:
            # double value and divide at runtime
            tagging.add_tag(Tag.DECOMPOSE_NUMBER25)
            try:
                value_double = value * 2.0
            except:
                # The following exception can occur in the above line:
                # OverflowError: int too large to convert to float
                # This is a very rare event and this code just fixes this case to not throw an exception
                value_double = value
            new_number = "(%d /2)" % value_double
        elif random_choice == 4:
            tagging.add_tag(Tag.DECOMPOSE_NUMBER26)
            random_value = js.get_int_as_number()
            value_plus = value + random_value
            new_number = "%d - %d" % (value_plus, random_value)
        elif random_choice == 5:
            tagging.add_tag(Tag.DECOMPOSE_NUMBER27)
            random_value = js.get_int_as_number()
            value_minus = value - random_value
            new_number = "%d + %d" % (value_minus, random_value)

        handled = True
    else:
        # something else like "NaN", "0x10", "0b110", ...
        tagging.add_tag(Tag.DECOMPOSE_NUMBER28)
        handled = False  # Currently I don't support this, only with the append/replace possibilities...
        new_number = previous_number

    if handled is False or utils.likely(0.3):
        tagging.add_tag(Tag.DECOMPOSE_NUMBER29)
        if utils.likely(0.5):
            # Perform append
            # Code which can be appended and which should not change anything
            # it's not 100% correct always but that's OK for fuzzing
            # E.g.: "NaN" replaced by "NaN & 0xfffffffffffff" is zero and not NaN
            tagging.add_tag(Tag.DECOMPOSE_NUMBER30)
            append_possibilities = ["|| NaN", "|| -0", "& 0xfffffffffffff", "+0.0", "-0.0", "+0", "+(-0)", "-(-0)",
                                    "+null", "-null"]

            append_value = utils.get_random_entry(append_possibilities)
            new_number = new_number + append_value
        else:
            # perform replace
            tagging.add_tag(Tag.DECOMPOSE_NUMBER31)
            replace_possibilities = ["(%s ? %s : -0)" % (new_number, new_number),
                                     "(%s ? -0 : %s)" % (new_number, new_number),
                                     # This is not a correct replacement, but it's OK, we are fuzzing..
                                     "(true ? %s : -0)" % new_number,
                                     "(false ? %s : -0)" % new_number,
                                     "(%s - %s + %s)" % (new_number, new_number, new_number),  # e.g.: "5-5+5" = "5"
                                     "(%s + %s - %s)" % (new_number, new_number, new_number)]  # e.g.: "5+5-5" = "5"

            new_number = utils.get_random_entry(replace_possibilities)

    return new_number, prefix


def add_variable_with_specific_data_type_in_line(content, state, data_type, line_number):
    # TODO:
    # Possible methods to copy objects?
    # var newInstance = JSON.parse(JSON.stringify(firstInstance));  => attention: this doesn'T work for every data type, e.g. firstInstance be a Symbol...
    # b = Object.assign({},a);
    # Reflect.construct() ?

    new_codeline = js_helpers.get_code_to_create_random_variable_with_datatype(data_type, state, line_number)

    # Adapt the data types to also use the other data types
    if data_type == "object1":
        other_datatypes_with_same_code = ["unkown_object", "object1", "object2"]
        data_type = utils.get_random_entry(other_datatypes_with_same_code)
    if data_type == "real_number":
        other_datatypes_with_same_code = ["special_number", "real_number"]
        data_type = utils.get_random_entry(other_datatypes_with_same_code)

    # Create the variable assignment
    state.number_variables = state.number_variables + 1
    next_free_variable_id = state.number_variables
    new_variable_name = "var_%d_" % next_free_variable_id
    new_codeline = "var %s = %s" % (new_variable_name, new_codeline)

    # 'Funny' side note:
    # According to: https://stackoverflow.com/questions/6881415/when-is-var-needed-in-js#:~:text=2%20Answers&text=The%20var%20keyword%20is%20never,property%20on%20the%20window%20object).&text=Usually%20you%20only%20want%20your,what%20var%20does%20for%20you.
    # It's not really required to use "var " in front, however, that's not true:
    # Example:
    #
    # var_12_ = new ArrayBuffer(2);
    # const var_7_ = class cl_1_ extends Array {
    # constructor() {
    #       super();
    # 	}
    # }
    # new var_7_();
    #
    # => Works fine
    # However, moving the first line into the constructor results in an exception because of the missing var keyword
    #
    # const var_7_ = class cl_1_ extends Array {
    # constructor() {
    #       super();
    #       var_12_ = new ArrayBuffer(2);
    #   }
    # }
    # new var_7_();
    #
    # => so it's required to add var at the start, otherwise I will get more exceptions

    # End the line correctly
    (start_line_with, end_line_with) = get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.MUTATION_ADD_VARIABLE2)
        new_codeline = new_codeline + ";"
    else:
        tagging.add_tag(Tag.MUTATION_ADD_VARIABLE3)
        new_codeline = start_line_with + iife_wrap(new_codeline) + end_line_with

    # And insert the code line in the content:
    lines = content.split("\n")
    lines.insert(line_number, new_codeline)
    new_content = "\n".join(lines)

    # Update the state
    state.state_insert_line(line_number, new_content, new_codeline)

    # And now make the new variable available to the state:
    state = state_make_variable_available_defined_in_line(new_content, state, new_variable_name, data_type, line_number)

    return new_content, state, new_variable_name


# TODO: Move this function into the state?
# TODO: This function doesn't work 100% correct for "arrays"
# => For arrays I must also store the length of the array + the data type of all fields
# => I should therefore handle arrays differently in the calling code to implement all of this...
def state_make_variable_available_defined_in_line(content, state, variable_name, variable_type, line_number):
    # First calculate in which lines the variable will very likely be available (the scope of the variable)
    # => that's basically all subsequent lines in the current {} block
    # Theoretically it should also be previous lines via variable hoisting, but since I can't mark variables as read-only
    # I'm currently skipping this (and I'm not sure if this really works in all contexts, e.g. inside a constructor?)
    # Moreover, I currently don't know the "flow" of the testcase and therefore I don't know when a function invocation occurs
    # Therefore I'm currently not marking it in lines which belong to an invoked function
    # TODO: After updating create_state_file.py by introducing a "flow" field, I should implement this here

    lines_in_which_variable_should_be_available = set()
    all_lines_which_are_executed = state.lines_where_code_can_be_inserted + state.lines_where_code_with_coma_can_be_inserted + state.lines_where_code_with_start_coma_can_be_inserted
    end_line = get_end_line_of_current_block(content, state, line_number)

    for tmp_line_number in all_lines_which_are_executed:
        # I'm checking "<" and not "<=" because the variable is just available in the next line after the definition
        if line_number < tmp_line_number <= end_line:
            # It's a line in the scope
            lines_in_which_variable_should_be_available.add(tmp_line_number)

    # TODO: Maybe it's better to make it in all lines afterwards available, not just in the current context?
    # e.g:
    # for(...) {
    #  *INSERTION HERE*
    # }
    # *SOME OTHER CODE LINES*
    #
    # If I add inside the for loop a "var" variable, then the variable is also available in the *SOME OTHER CODE LINES*
    # With the current implementation it's not available there...
    for tmp_line_number in lines_in_which_variable_should_be_available:
        state.add_variable_type(variable_name, tmp_line_number, variable_type)

    return state


# immediately invoked function expression wrap
def iife_wrap(code):
    # Import: Don't add newlines to this code!
    # I'm using it together with operations and a newline would change the state of an operation!

    # TODO maybe add a return there if code is single line? And maybe avoid the return iof code starts with "var " or "let " or "const " ?
    return "(() => { %s })()" % code


def get_end_line_of_current_block(content, state, current_line):
    blocks = get_curley_bracket_blocks_as_line_numbers(content, state)

    blocks_with_number_of_lines = []
    for entry in blocks:
        (start_line, end_line) = entry
        number_of_lines = end_line - start_line + 1
        blocks_with_number_of_lines.append((entry, number_of_lines))

    # Sort to ensure the smallest blocks are first in the list => that are the ones which fit "the best" for the current scope
    blocks_with_number_of_lines.sort(key=lambda x: x[1])
    for entry_with_number_of_lines in blocks_with_number_of_lines:
        (entry, number_of_lines) = entry_with_number_of_lines
        (start_line, end_line) = entry
        if start_line <= current_line <= end_line:
            return end_line

    # If this point is reached then there is no {} block / context / scope
    # => in this case I must return the last line number +1
    # Since I start counting with 0, I can skip the +1 and just return the number of code lines
    # (I'm calling this function to determine in which lines a variable should be available
    # and in an append operation to the testcase the variable would also be available)
    return state.testcase_number_of_lines




def get_special_random_operation(content, state, line_number):
    tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION1)

    possibilities = ["Array(2**30);", "parseInt();", 'eval("");', "try {} catch(e) {};", "with ({});",
                     "{ function x() { } };", "new (function() {});", "var useless = function () {};",
                     "this.constructor = () => {};", "SUBCLASS_GLOBAL"]

    if state.number_functions > 0:
        possibilities.append("TRIGGER_FUNCTION_OPTIMIZATION")
        possibilities.append("CALL_FUNCTION")
        possibilities.append("SUBCLASS_FUNCTION")
        possibilities.append("NEVER_OPTIMIZE_FUNCTION")
        possibilities.append("DEOPTIMIZE_FUNCTION")

        random_func = "func_%d_" % utils.get_random_int(1, state.number_functions)

    possible_other_variables = get_all_available_variables(state, line_number)
    line_to_return = ""

    entry = utils.get_random_entry(possibilities)
    if entry == "TRIGGER_FUNCTION_OPTIMIZATION":
        if utils.likely(0.3):
            tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION2)
            line_to_return = "%%PrepareFunctionForOptimization(%s);%%OptimizeFunctionOnNextCall(%s);" % (random_func, random_func)
        else:
            tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION3)
            line_to_return = "%%OptimizeFunctionOnNextCall(%s);" % random_func
    elif entry == "NEVER_OPTIMIZE_FUNCTION":
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION7)
        line_to_return = "%%NeverOptimizeFunction(%s);" % random_func
    elif entry == "DEOPTIMIZE_FUNCTION":
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION8)
        line_to_return = "%%DeoptimizeFunction(%s);" % random_func
    elif entry == "CALL_FUNCTION":
        # TODO: leads in 33% of cases in an exception
        # and in 12,25% in hangs!!!
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION4)
        number_args = utils.get_random_int(1, 5)
        args = ""
        for i in range(number_args):
            args += js.get_random_js_thing(possible_other_variables, state, line_number) + ","
        args = args[:-1]    # remove last ","
        line_to_return = "%s(%s);" % (random_func, args)
    elif entry == "SUBCLASS_FUNCTION":
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION5)
        random_name = utils.get_random_token_string(8)
        # TODO i can also call the function by doing "new _random_func_()" then!
        line_to_return = "class %s extends %s { };" % (random_name, random_func)
    elif entry == "SUBCLASS_GLOBAL":
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION6)
        random_global = utils.get_random_entry(js.get_instanceable_builtin_objects_full_list())
        random_name = utils.get_random_token_string(8)
        line_to_return = "class %s extends %s { };" % (random_name, random_global)
    else:
        line_to_return = entry

    (start_line_with, end_line_with) = get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION9)
        pass    # nothing to change
    else:
        tagging.add_tag(Tag.GET_SPECIAL_RANDOM_OPERATION10)
        line_to_return = start_line_with + iife_wrap(line_to_return) + end_line_with

    return line_to_return


def get_random_operation(content, state, line_number):
    possible_variables = get_all_available_variables_with_datatypes(state, line_number, exclude_undefined=True)
    possible_arrays = state.get_available_arrays_in_line_with_lengths(line_number)

    possible_choices = []
    for variable_name in possible_variables:
        possible_choices.append(variable_name + "_variable")
    for variable_name in possible_arrays:
        possible_choices.append(variable_name + "_array")

    if len(possible_choices) == 0 or utils.likely(0.1):
        tagging.add_tag(Tag.GET_RANDOM_OPERATION3)
        return database_operations.get_random_operation_without_a_variable(content, state, line_number)

    random_variable_name = utils.get_random_entry(possible_choices)
    if random_variable_name.endswith("_variable"):
        tagging.add_tag(Tag.GET_RANDOM_OPERATION4)
        random_variable_name = random_variable_name[:len("_variable")*-1]
        random_variable_types = possible_variables[random_variable_name]
        line_to_add = database_operations.get_random_variable_operation(content, state, line_number, random_variable_name, random_variable_types)
    else:
        # ends with "_array" => Array operation
        tagging.add_tag(Tag.GET_RANDOM_OPERATION5)
        random_array_name = random_variable_name[:len("_array")*-1]
        random_array_lengths = possible_arrays[random_array_name]
        line_to_add = get_random_array_operation(content, state, line_number, random_array_name, random_array_lengths)
    return line_to_add
