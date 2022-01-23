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



# This mode can be started by passing the "--fix_corpus_mode" flag to the fuzzer.
#
# This mode is mainly used to re-calculate state files for testcases where a state file is missing.
# This occurs when I mainly remove a state file.
# E.g.: If I find a flaw in a testcase and I manually fix the testcase like variable renaming
# then I remove the state file and call this function to recalculate the state files for these files


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import state_creation.create_state_file as create_state_file
import testcase_state
import utils
import config as cfg



def fix_corpus():
    corpus_filepath = cfg.output_dir_current_corpus

    utils.msg("[i] Starting to fix corpus...")
    for filename in os.listdir(corpus_filepath):
        if filename.endswith(".js") is False:
            continue

        filepath = os.path.join(corpus_filepath, filename)
        if os.path.isfile(filepath) is False:
            continue
        
        state_filepath = filepath + ".pickle"
        if os.path.isfile(state_filepath):
            continue    # state file already exists, so it must not be created

        utils.msg("[i] Going to fix testcase: %s" % filename)
        # sys.exit(-1)

        with open(filepath, "r") as fobj:
            content = fobj.read()

        state = create_state_file.create_state_file_safe(content)
        testcase_state.save_state(state, state_filepath)

    utils.msg("[i] Finished fixing corpus")
