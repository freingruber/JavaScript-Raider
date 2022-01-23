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


# This mode can be started by passing the "--check_corpus_mode" flag to the fuzzer.
#
# It seems like the fuzzer sometimes adds not reliable testcases to the corpus which are very big.
# E.g.: during first execution the testcase returns the new coverage X.
# I then execute the testcase multiple times after that to verify if X is triggered reliable.
# However, it seems like some testcases still pass these tests and then end up in the corpus
# but which don't trigger the new coverage X reliable.
# This is a problem because later testcase minimization is started and when the testcase doesn't trigger
# the new behavior reliable during minimization, all minimization steps will fail and the testcase stays pretty big.
# A big testcase is bad for fuzzing because it contains a huge number of potential code insertion points
# and the testcase will be slow.
# The code in this script tries to identify these testcases and removes them from the corpus.
#
# TODO: Code must be refactored

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import testcase_state
import utils
import config as cfg
from pathlib import Path
import native_code.coverage_helpers as coverage_helpers
import pickle


# Imaging that a corpus is created using two different JavaScript engines
# e.g. v8 and JSC or an old v8 version and a new v8 version
# When calling "--check-corpus" using the 2nd engine, the testcases which were found
# in the first engine will not reproduce the coverage in the 2nd engine
# and therefore this script would not work as intended
# So solve this problem I use the following two variables to mark which testcases are "save"
# and therefore already checked. E.g.: I use my fuzzer to create a corpus of for example
# 15 000 testcases for v8. Then I change to JSC and find 3 more files, so the final corpus is
# 18 000 testcases. Then I want to check the corpus for bad testcases and call --check-corpus
# but I configure as >always_save_testcase_ids_start< 1 and as >always_save_testcase_ids_end<
# 15 000 because I just want to check the 3 000 new files.
# Moreover, I would also already have checked the 15 000 files before I would start fuzzing with a new 
# engine


# testcases 1-16071 were created with a full instrumented JS engine (different to the current one)
always_save_testcase_ids_start = 1
always_save_testcase_ids_end = 16071    


def check_corpus():
    global always_save_testcase_ids_start
    global always_save_testcase_ids_end

    corpus_dir = cfg.output_dir_current_corpus
    utils.msg("[i] Starting to check the corpus...")

    old_corpus_entries_dir = os.path.join(Path(corpus_dir).parent.absolute(), "old_corpus_entries")
    if not os.path.exists(old_corpus_entries_dir):
        os.makedirs(old_corpus_entries_dir)

    counter = 0
    for filename in os.listdir(corpus_dir):
        if filename.endswith(".js") is False:
            continue

        filepath = os.path.join(corpus_dir, filename)
        if os.path.isfile(filepath) is False:
            continue

        current_testcase_id = int(filename[len("tc"):len(".js")*-1], 10)
        if always_save_testcase_ids_start <= current_testcase_id <= always_save_testcase_ids_end:
            # skip it, because these corpus entries were created for a different JS engine
            # => the required coverage can't be reproduced in the current JS engine and it's therefore not possible
            # to perform these checks on these entries
            continue
            
        counter += 1
        with open(filepath, "r") as fobj:
            content = fobj.read()

        state_filepath = filepath + ".pickle"
        state = testcase_state.load_state(state_filepath)

        required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"
        with open(required_coverage_filepath, 'rb') as finput:
            required_coverage = pickle.load(finput)

        if len(content) < 100:
            # skip the small testcases because they were likely already minimized and therefore
            # coverage feedback was reliable
            continue

        if len(required_coverage) >= 5:
            # ignore these files
            # I created some entries in a different engine already and more than 5 coverage entries
            # typically means that it's a good entry
            # E.g.: when starting the fuzzer on a different CPU you also immediately find new testcases with new behavior
            # but I can't reproduce this behavior on another CPU. So I'm just checking testcases
            # which just have 1 or 2 new edges (which can be unreliable edges)
            continue

        # utils.msg("[i] Code:")
        # utils.msg("[i] " + content)
        # utils.msg("[i] Required coverage: %d" % len(required_coverage))
        # utils.msg("[i] " + required_coverage)

        should_move_file = False

        result = does_code_still_trigger_coverage(content, required_coverage)

        if result != "all":
            # Try it one more time
            result = does_code_still_trigger_coverage(content, required_coverage)

        if result == "all":
            utils.msg("[+] Testcase %s still triggers coverage" % filename)
        elif result == "partial":
            utils.msg("[i] Testcase %s triggers partial coverage" % filename)
            should_move_file = True
        else:
            utils.msg("[-] Testcase %s does not trigger coverage anymore" % filename)
            should_move_file = True

        if should_move_file:
            # Move the file to the old corpus files directory
            # => It's a good practice to recalculate the coverage map of the corpus afterwards and then
            # try to re-import the moved files
            # => maybe they will be imported again and get correctly standardized/minimized

            output_filepath = os.path.join(old_corpus_entries_dir, filename)
            output_state_filepath = output_filepath + ".pickle"

            output_required_coverage_filepath = output_filepath[:-3] + "_required_coverage.pickle"

            os.rename(filepath, output_filepath)
            os.rename(state_filepath, output_state_filepath)
            os.rename(required_coverage_filepath, output_required_coverage_filepath)

        # utils.msg("[i] Next file (counter: %d): %s" % (counter, filename))

    # Now some files were removed from the corpus dir
    # that means the testcase ID numbers are not consecutive
    # and contain some holes
    # So rename the files
    last_testcase_id = utils.get_last_testcase_number(corpus_dir)

    next_rename_id = 1
    for current_id in range(1, last_testcase_id+1):
        filename = "tc%d.js" % current_id
        filepath = os.path.join(corpus_dir, filename)
        if os.path.isfile(filepath) is False:
            # do not increase the >next_rename_id< because this slot is "free"
            continue

        utils.msg("[i] current_id: %d" % current_id)
        utils.msg("[i] next_rename_id: %d" % next_rename_id)
        if current_id == next_rename_id:
            utils.msg("[i] skip because they are the same")
            # no need to rename because the files already have the correct name
            next_rename_id += 1
            continue

        state_filepath = filepath + ".pickle"
        required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"

        new_filename = "tc%d.js" % next_rename_id
        new_filepath = os.path.join(corpus_dir, new_filename)
        new_state_filepath = new_filepath + ".pickle"
        new_required_coverage_filepath = new_filepath[:-3] + "_required_coverage.pickle"

        utils.msg("[i] Renaming from %s to %s" % (filepath, new_filepath))
        # Rename the files
        os.rename(filepath, new_filepath)
        os.rename(state_filepath, new_state_filepath)
        os.rename(required_coverage_filepath, new_required_coverage_filepath)

        next_rename_id += 1     # increase the rename ID for the next iteration because the current one is now in-use

    # TODO: Automate the adaption of "disabled_files.pickle"
    utils.msg("[i] TODO, you need to manually remove the disabled_files.pickle file because filenames changed!")
    input("TODO: Don't forget to do this manually!")




def does_code_still_trigger_coverage(new_code, required_coverage):
    # We can use the corpus minimizer coverage map here because it stores the initial coverage map
    # after dummy executions
    original_coverage_filepath = cfg.coverage_map_corpus_minimizer
    all_coverage = True
    at_least_one_coverage = False

    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(new_code, original_coverage_filepath)
    for coverage_entry in required_coverage:
        if coverage_entry not in triggered_coverage:
            all_coverage = False
            # return False
        else:
            at_least_one_coverage = True

    if all_coverage:
        return "all"
    elif at_least_one_coverage:
        return "partial"
    else:
        return "none"
