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



# Simple mutation strategy to WHILE-loop wrap a line:
#
# Example:
# console.log("code")
#
# =>
#
# while (true) { console.log("code");break }

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers


def mutation_while_wrap_line(content, state):
    # utils.dbg_msg("Mutation operation: WHILE-wrap code line")
    tagging.add_tag(Tag.MUTATION_WHILE_WRAP_LINE1)

    lines = content.split("\n")
    possibilities_top_insert_for = testcase_mutators_helpers.get_code_lines_without_forbidden_words(lines)
    if len(possibilities_top_insert_for) == 0:
        tagging.add_tag(Tag.MUTATION_WHILE_WRAP_LINE2_DO_NOTHING)
        return content, state       # nothing to modify

    random_line_number = utils.get_random_entry(possibilities_top_insert_for)
    old_line = lines[random_line_number]

    code_to_append = "while (true) { "
    code_to_append_end = ";break }"

    new_line = code_to_append + old_line + code_to_append_end
    lines[random_line_number] = new_line

    new_content = "\n".join(lines)
    added_length = len(code_to_append + code_to_append_end)
    state.state_update_content_length(added_length, new_content)

    return new_content, state
