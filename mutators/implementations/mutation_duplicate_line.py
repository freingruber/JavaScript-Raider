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

import mutators.testcase_mutators_helpers as testcase_mutators_helpers


# TODO: What if the line is something like:
# var var_1_ = 1;
# If I duplicate this, I would need to change the variable name to "var_2_" => and then I would also  have to modify the state?
# => skip these lines for the moment... (?)

# TODO: shouldn't I implement also a "duplicate instruction"?
# => The code in >create_pickle_database_for_javascript_operations< can already detect multi-line operations
# => move this code into some helper script and then use it here to duplicate code lines such as:
# var_1_.someFunction(1,
# 2,
# 3)
def mutation_duplicate_line(content, state):
    # utils.dbg_msg("Mutation operation: Duplicate line")
    tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE1)

    # TODO: I'm using a random code line, but maybe I should also take lines into account which result in an exception
    # => these are lines where duplication will very likely not work!

    lines = content.split("\n")
    possible_lines_to_duplicate = set(range(len(lines)))
    lines_with_curly_brackets = testcase_mutators_helpers.get_lines_with_curly_brackets(content, state)
    possible_lines_to_duplicate -= lines_with_curly_brackets
    # TODO the above code is not 100% correct. If the "{" and "}" symbols are in the same line
    # and the number of opening and closing brackets is the same, the line can be moved/removed
    # e.g. try { xxx} catch {xxx} can be removed or moved around! Fix this

    # This is an "on-top" check, e.g. all "{" or "}" lines should already be removed because of the above code
    # Note: The "{" in the above code just affect the "{" symbols in the code, not e.g. in strings!
    # The above code is therefore more reliable! But it sometimes happens that these values are incorrect because of mutations
    # In this case I add a small likelihood that I also remove "{" or "}" lines (which may affect strings as well)
    # I'm adding this because I saw this problem occur in several testcases during fuzzing
    if utils.likely(0.6):
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE2)
        entries_to_remove = set()
        for possible_codeline_number in possible_lines_to_duplicate:
            line = lines[possible_codeline_number]
            tmp = line.lower().lstrip()
            if "{" in tmp or "}" in tmp:
                entries_to_remove.add(possible_codeline_number)
        possible_lines_to_duplicate -= entries_to_remove

    if utils.likely(0.9):
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE3)
        entries_to_remove = set()
        for possible_codeline_number in possible_lines_to_duplicate:
            line = lines[possible_codeline_number]
            tmp = line.lower().lstrip()
            if tmp.startswith("function ") or tmp.startswith("function*") or tmp.startswith("class ") or \
                    tmp.startswith("if(") or tmp.startswith("if ") or tmp.startswith("else") or \
                    tmp.startswith("switch ") or tmp.startswith("for ") or tmp.startswith("for(") or \
                    tmp.startswith("while ") or tmp.startswith("while(") or tmp.startswith("const "):
                # don't duplicate these lines
                entries_to_remove.add(possible_codeline_number)
        possible_lines_to_duplicate -= entries_to_remove

    if len(possible_lines_to_duplicate) == 0:
        # No lines can be duplicated, so just return the original data
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE4_DO_NOTHING)
        return content, state

    # utils.dbg_msg("Possible lines to duplicate: " + str(list(possible_lines_to_duplicate)))
    random_line_number = utils.get_random_entry(list(possible_lines_to_duplicate))
    # utils.dbg_msg("Going to duplicate line: %d" % random_line_number)

    # Update the content
    duplicated_code_line = lines[random_line_number]
    if len(duplicated_code_line) == 0:
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE5_DO_NOTHING_RARE)
        return content, state      # return unmodified content

    possible_lines_to_insert = list(set(state.lines_where_code_can_be_inserted) - set(state.lines_which_are_not_executed))
    if len(possible_lines_to_insert) == 0:
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE9_DO_NOTHING)
        return content, state   # return unmodified content
    random_line_number_where_code_gets_inserted = utils.get_random_entry(possible_lines_to_insert)
    # utils.dbg_msg("Duplicating line after line: %d" % random_line_number_where_code_gets_inserted)
    # TODO: I can make this code better, e.g.: if the duplicated code line contains "var_5_" then it must be duplicated
    # to a code line where var_5_ is available. Otherwise it will fail. So I should maybe filter out some lines here?

    if utils.likely(0.5):
        # In 50% of cases I protect the duplicated codeline with a try catch block because it may lead to an exception
        # see the comment above
        tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE6)
        suffix = ""
        if duplicated_code_line[-1] == ",":
            duplicated_code_line = duplicated_code_line[:-1]
            suffix = ","
        if utils.likely(0.95):
            tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE7)
            duplicated_code_line = "try { %s } catch {}%s" % (duplicated_code_line, suffix)
        else:
            tagging.add_tag(Tag.MUTATION_DUPLICATE_LINE8)
            duplicated_code_line = "try { %s } finally {}%s" % (duplicated_code_line, suffix)

    lines.insert(random_line_number_where_code_gets_inserted, duplicated_code_line)
    new_content = "\n".join(lines)
    state.state_insert_line(random_line_number_where_code_gets_inserted, new_content, duplicated_code_line)

    return new_content, state
