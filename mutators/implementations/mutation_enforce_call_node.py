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



# This code tries to generate a call node in the sea-of-nodes which can be required to trigger specific bugs.
#
# 1st example (variable):
# If I have var_1_.indexOf(0x00, var_2_)
# rewrite it to:
# Array.prototype.indexOf.call(var_1_, 0x00, var_2_)
# => this creates a call node in sea-of-nodes

# 2nd example (global):
# Math.expm1(-0)
# => rewrite to:
# Math.expm1.call(Math.expm1,-0)
# This example is from "Chromium issue 880207 (2018) - Incorrect type information on Math.expm1"
# From an alternative exploit from "sakura sakura":
# https://docs.google.com/presentation/d/1DJcWByz11jLoQyNhmOvkZSrkgcVhllIlCHmal1tGzaw/edit#slide=id.g52a72d9904_2_105

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag

import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import testcase_helpers
import javascript.js_helpers as js_helpers


def mutation_enforce_call_node(content, state):
    # utils.dbg_msg("Mutation operation: Enforce call node")
    tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE1)

    # TODO:
    # Currently my state doesn't extract properties
    # E.g.:
    # let var_1_ = []
    # let var_1_.someOtherProperty = []
    # => Then my state currently don't store that "var_1_.someOtherProperty" is an array
    # and therefore this code here can also not handle something like "var_1_.someOtherProperty.shift()"

    # Query all function calls
    # According regex: The first part before the "." can contain [], e.g. var_1_[0] to access array elements

    positions_tmp = testcase_mutators_helpers.get_positions_of_regex_pattern(r"[a-zA-Z_\d\]\[]+[.][a-zA-Z_\d]+[ \t\n]*[(]", content, ignore_additional_check=True)
    positions = []
    for entry in positions_tmp:
        (entry_start_idx, entry_end_idx) = entry
        if entry_start_idx != 0:
            if content[entry_start_idx - 1] == ".":
                continue
        positions.append(entry)

    if len(positions) == 0:
        tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE2_DO_NOTHING)
        return content, state   # nothing to replace

    (start_idx, end_idx) = utils.get_random_entry(positions)
    original_code = content[start_idx:end_idx + 1]
    # print("original_code: >%s<" % original_code)
    line_number = testcase_helpers.content_offset_to_line_number(content.split("\n"), start_idx)
    # print("line_number: %d for offset: 0x%x " % (line_number, start_idx))
    original_code_splitted = original_code.split(".")       # TODO maybe rsplit with max 2 ? like var_1_.property.functionCall()
    possible_variable_name = original_code_splitted[0]

    # print("DEBUG: possible_variable_name: %s" % possible_variable_name)
    # print("DEBUG: original_code: %s" % original_code)
    variable_types = state.get_variable_types_in_line(possible_variable_name, line_number)
    # print(variable_types)

    if variable_types is not None:
        # 1st case
        if len(variable_types) == 0:
            # should not occur, just return the unmodified code
            tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE3_DO_NOTHING_SHOULD_NOT_OCCUR)
            return content, state

        variable_type = utils.get_random_entry(variable_types)  # in 99% it will just contain one entry
        variable_type = js_helpers.convert_datatype_str_to_real_JS_datatype(variable_type)
        if variable_type is None:
            # Should not occur, but just return the unmodified content
            tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE4_DO_NOTHING_SHOULD_NOT_OCCUR)
            return content, state

        tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE5)
        function_name = original_code_splitted[1][:-1]      # :-1 to remove the "(" from the function call
        # print("variable_type: %s" % variable_type)
        # print("function_name: %s" % function_name)
        # print("possible_variable_name: %s" % possible_variable_name)
        new_code = "%s.prototype.%s.call(%s," % (variable_type, function_name, possible_variable_name)
    else:
        # 2nd case => it's not a variable but a global instead like: "Math.expm1("
        # original_code is now something like: "Object.defineProperty(" or Math.expm1(
        tagging.add_tag(Tag.MUTATION_ENFORCE_CALL_NODE6)
        original_code_without_bracket = original_code[:-1]

        # Rewrite to: Math.expm1.call(Math.expm1,
        new_code = "%s.call(%s," % (original_code_without_bracket, original_code_without_bracket)

    new_content = content[:start_idx] + new_code + content[end_idx + 1:]
    added_length = len(new_code) - len(original_code)
    state.state_update_content_length(added_length, new_content)
    return new_content, state
