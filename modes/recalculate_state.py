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


import os
import utils
import state_creation.create_state_file as create_state_file
import testcase_state
import config as cfg


def recalculate_state(recalculate_state_for_file):
    output_dir_current_corpus = cfg.output_dir_current_corpus

    count = 0
    if recalculate_state_for_file == "all":
        for filename in os.listdir(output_dir_current_corpus):
            if filename.endswith(".js") is False:
                continue

            filepath = os.path.join(output_dir_current_corpus, filename)
            with open(filepath, "r") as fobj:
                content = fobj.read()

            count += 1
            state_filepath = filepath + ".pickle"
            # if os.path.exists(state_filepath):
            #    continue    # TODO remove later again
            try:
                os.remove(state_filepath)
            except:
                pass
            utils.msg("[i] Going to calculate file %s (file %d)" % (filename, count))

            state = create_state_file.create_state_file_safe(content)
            testcase_state.save_state(state, state_filepath)
            utils.msg("[i] Finished state calculation of %s (file %d)" % (filename, count))

        utils.exit_and_msg("[+] Finished, stopping...")

    if recalculate_state_for_file.startswith("tc") is False or recalculate_state_for_file.endswith(".js") is False:
        utils.perror("Error --recalculate_state state argument is wrong (%s)" % recalculate_state_for_file)

    # Handling a single file
    filepath = os.path.join(output_dir_current_corpus, recalculate_state_for_file)
    if os.path.isfile(filepath) is False:
        utils.perror("Error --recalculate_state file doesn't exist (%s)" % recalculate_state_for_file)
    with open(filepath, "r") as fobj:
        content = fobj.read()

    state_filepath = filepath + ".pickle"
    state = create_state_file.create_state_file_safe(content)
    # state = create_state_file.create_state_file(content, silently_catch_exception=False)
    # print("Testcase:")
    # print(content)
    # print("State:")
    # print(state)
    testcase_state.save_state(state, state_filepath)
