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
from testcase_mergers.implementations.merge_testcase_append import merge_testcase_append
import testcase_mergers.testcase_merger as testcase_merger


def merge_testcase_insert(testcase1_content, testcase1_state, testcase2_content, testcase2_state):
    # utils.dbg_msg("Merging operation: Testcase insert")
    tagging.add_tag(Tag.MERGE_TESTCASE_INSERT1)

    if len(testcase1_state.lines_where_code_can_be_inserted) == 0:
        # This should never occur because the "append" code line should always be available...
        tagging.add_tag(Tag.MERGE_TESTCASE_INSERT2_SHOULD_NOT_OCCUR)
        # utils.dbg_msg("Code can't be inserted at any line, so make a fallback to append")
        return merge_testcase_append(testcase1_content, testcase1_state, testcase2_content, testcase2_state)

    # utils.dbg_msg("Possible lines where testcase2 can be inserted: %s" % str(testcase1_state.lines_where_code_can_be_inserted))

    # TODO: Later maybe also consider coma separated lines?
    possible_lines_to_insert = list(set(testcase1_state.lines_where_code_can_be_inserted) - set(testcase1_state.lines_which_are_not_executed))
    if len(possible_lines_to_insert) == 0:
        tagging.add_tag(Tag.MERGE_TESTCASE_INSERT3_SHOULD_NOT_OCCUR)
        return merge_testcase_append(testcase1_content, testcase1_state, testcase2_content, testcase2_state)

    random_line_number = utils.get_random_entry(possible_lines_to_insert)
    # utils.dbg_msg("Going to insert testcase2 at line %d in testcase1" % random_line_number)
    return testcase_merger.merge_testcase2_into_testcase1_at_line(testcase1_content,
                                                                  testcase1_state,
                                                                  testcase2_content,
                                                                  testcase2_state,
                                                                  random_line_number)
