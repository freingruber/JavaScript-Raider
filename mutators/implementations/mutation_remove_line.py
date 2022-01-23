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



# This mutation strategy tries to remove a code line from the testcase
# The fuzzer tries to remove only lines which don't break the control flow
# E.g.: lines which contain "{", but not "}" will not be removed because they
# would likely lead to exceptions.

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


def mutation_remove_line(content, state):
    # utils.dbg_msg("Mutation operation: Remove line")
    tagging.add_tag(Tag.MUTATION_REMOVE_LINE1)

    lines = content.split("\n")
    possible_lines_to_remove = set(range(len(lines)))
    lines_with_curly_brackets = testcase_mutators_helpers.get_lines_with_curly_brackets(content, state)
    possible_lines_to_remove -= lines_with_curly_brackets
    # TODO the above code is not 100% correct. If the "{" and "}" symbols are in the same line
    # and the number of opening and closing brackets is the same, the line can be moved/removed
    # e.g. try { xxx} catch {xxx} can be removed or moved around! Fix this
    # but that should not happen too often because I think I add newlines after { symbols when handling new files

    if utils.likely(0.6):
        tagging.add_tag(Tag.MUTATION_REMOVE_LINE2)
        entries_to_remove = set()
        for possible_codeline_number in possible_lines_to_remove:
            line = lines[possible_codeline_number]
            tmp = line.lower().lstrip()
            if "{" in tmp or "}" in tmp:
                entries_to_remove.add(possible_codeline_number)
        possible_lines_to_remove -= entries_to_remove

    if utils.likely(0.9):
        tagging.add_tag(Tag.MUTATION_REMOVE_LINE3)
        # In most cases (90%) additional protections are used to ensure that the resulting testcase is valid
        # E.g.: the start of a function or a class should not be removed, as well as if-conditions, loops, ...
        tmp_set = set()
        # In 10% of cases the line is then just removed
        # This can be important lines, but the 10% ensure that really every line can be removed
        for possible_codeline_number in possible_lines_to_remove:
            line = lines[possible_codeline_number]
            tmp = line.lower().lstrip()
            if tmp.startswith("function ") or tmp.startswith("function*") or tmp.startswith("class ") or tmp.startswith("if(") or tmp.startswith("if ") or tmp.startswith("else") or tmp.startswith("switch ") or tmp.startswith("for ") or tmp.startswith("for(") or tmp.startswith("while ") or tmp.startswith("while("):
                # don't modify these lines
                tmp_set.add(possible_codeline_number)
        possible_lines_to_remove -= tmp_set
        tmp_set.clear()

        if utils.likely(0.7):
            tagging.add_tag(Tag.MUTATION_REMOVE_LINE4)
            # also prevent in 70% of cases line removal where variables are created like "var "
            for possible_codeline_number in possible_lines_to_remove:
                line = lines[possible_codeline_number]
                tmp = line.lower().lstrip()
                if tmp.startswith("var ") or tmp.startswith("const ") or tmp.startswith("let "):
                    tmp_set.add(possible_codeline_number)
            possible_lines_to_remove -= tmp_set

    if len(possible_lines_to_remove) == 0:
        # No lines can be removed, so just return the original data
        tagging.add_tag(Tag.MUTATION_REMOVE_LINE5_DO_NOTHING)
        return content, state

    # utils.dbg_msg("Possible lines to remove: " + str(list(possible_lines_to_remove)))
    random_line_number = utils.get_random_entry(list(possible_lines_to_remove))
    # utils.dbg_msg("Going to remove: %d" % random_line_number)

    return _remove_specific_line(content, state, random_line_number)


def _remove_specific_line(content, state, line_number):
    tagging.add_tag(Tag.MUTATION_REMOVE_SPECIFIC_LINE1)

    content_lines = content.split("\n")

    # Update the content
    removed_line = content_lines[line_number]
    del content_lines[line_number]
    new_content = "\n".join(content_lines)

    # Update the state
    state.state_remove_lines(line_number, new_content, removed_line, number_of_lines_to_remove=1)
    return new_content, state
