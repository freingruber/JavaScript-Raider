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
import testcase_mergers.testcase_merger as testcase_merger



def merge_testcase_append(testcase1_content, testcase1_state, testcase2_content, testcase2_state):
    # utils.dbg_msg("Merging operation: Testcase append")
    tagging.add_tag(Tag.MERGE_TESTCASE_APPEND1)
    return testcase_merger.merge_testcase2_into_testcase1_at_line(testcase1_content,
                                                                  testcase1_state,
                                                                  testcase2_content,
                                                                  testcase2_state,
                                                                  testcase1_state.testcase_number_of_lines)
