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



# This mutation strategy replaces a random string with another randomly generated string.

import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js
import testcase_helpers


# Note: this mutation often results in "do nothing"
# e.g. out of 120 000 executions nothing was done in 90 000 cases
# because there were no strings in the testcase or it would likely result in an exception
def mutation_replace_string(content, state):
    # utils.dbg_msg("Mutation operation: Replace string")
    tagging.add_tag(Tag.MUTATION_REPLACE_STRING1)

    positions_of_strings = testcase_mutators_helpers.get_positions_of_all_strings_in_testcase(content)
    if len(positions_of_strings) == 0:
        tagging.add_tag(Tag.MUTATION_REPLACE_STRING2_DO_NOTHING)
        return content, state       # nothing to replace

    if should_string_manipulations_be_skipped(content):
        tagging.add_tag(Tag.MUTATION_REPLACE_STRING3_DO_NOTHING)
        return content, state       # the mutation would likely result in an exception, so skip it

    (start_idx, end_idx) = utils.get_random_entry(positions_of_strings)
    # utils.dbg_msg("Replacing string which starts at 0x%x and ends at 0x%x" % (start_idx, end_idx))

    original_string = content[start_idx:end_idx + 1]
    number_of_newlines_in_original_string = original_string.count("\n")
    start_line_number_to_remove = 0
    if number_of_newlines_in_original_string != 0:
        # pre-calculation before updating the content for below code
        start_line_number_to_remove = testcase_helpers.content_offset_to_line_number(content.split("\n"), start_idx)
        start_line_number_to_remove += 1    # the current line is not removed (the new string is stored there), only the next line and following ones are removed

    # print("Original string is:>>>%s<<<\n\n\n" % original_string)
    # print("number_of_newlines_in_original_string: %d" % number_of_newlines_in_original_string)

    random_string = js.get_str()
    # utils.msg("[i] \n\n\nNew random string: %s" % (random_string))
    # random_string_hex = ":".join("{:02x}".format(ord(c)) for c in random_string)
    # utils.msg("[i] \n\n\nNew random string (hex): %s" % (random_string_hex))

    new_content = ''.join([content[:start_idx], random_string, content[end_idx + 1:]])

    added_length = len(random_string) - (end_idx - start_idx + 1)       # can also become negative, but that's ok
    state.state_update_content_length(added_length, new_content)
    new_testcase_size = state.testcase_size

    # My expectation is that the new string doesn't contain newlines
    # However, the old string can contain newlines
    # That means after replacing the string it's possible that line numbers don't match anymore
    # because some newlines were removed
    # That means the line numbers must also be updated in the state in such a case
    if number_of_newlines_in_original_string != 0:
        # line numbers changed, so a full state update must be performed
        state.state_remove_lines(start_line_number_to_remove, new_content, "", number_of_newlines_in_original_string)
        state.testcase_size = new_testcase_size     # reset the size because the remove line function adapted the size (but didn't take the new string into account)

    return new_content, state



def should_string_manipulations_be_skipped(content):
    # Eval is ignored because this leads too often in exceptions
    # Theoretically I could also check the "original_string" and if it contains code, however, this
    # doesn't work in all cases, e.g.:
    # eval(*some valid code* + "}")
    # => Then the fuzzer replaces "}" with a fuzzed string
    # => and "}" is not enough to identify valid code...
    # so I'm just skipping this mutation in case the testcase contains eval

    # Same applies for new Function

    # Normalize just accepts specific arguments
    if ("eval(" in content or " Function(" in content or ".normalize(" in content
            or "= eval;" in content
            or "new Intl.DateTimeFormat(" in content or "new Intl.RelativeTimeFormat(" in content
            or "new Intl.NumberFormat(" in content or "new WebAssembly.Table(" in content
            or "new Intl.Locale(" in content or ".toLocaleLowerCase(" in content
            or "new Intl.DisplayNames(" in content or "new WebAssembly.Global(" in content
            or "JSON.parse(" in content or "new Intl.v8BreakIterator(" in content
            or ".groups" in content or "new Intl.Collator(" in content
            or "new Intl.PluralRules(" in content
            or ".__defineGetter__(" in content or ".defineProperty(" in content):
        return True

    # => in this case maybe don't replace the strings? It's likely that a property will be created
    # which is later used in the code. => if the property isn't created because the string gets modified
    # it's likely that the testcase will result in an exception
    return False
