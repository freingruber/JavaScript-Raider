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



# This script contains the logic to handle new discovered testcases (code which triggers new behavior)
# It checks if the new behavior can reliable be triggered, starts testcase minimization,
# testcase standardization and creation of a state file for the testcase.
# If enabled, it also starts synchronization to save the new file in a GCE bucket
# and also if enabled, it adds the testcase to the deterministic preprocessing queue

import config as cfg
import utils
import minimizer.testcase_minimizer as testcase_minimizer
import state_creation.create_state_file as create_state_file
import modes.deterministic_preprocessing as deterministic_preprocessing
import hashlib
import sync_engine.gce_bucket_sync as gce_bucket_sync
import standardizer.testcase_standardizer as testcase_standardizer
import handle_new_file.handle_new_file_helpers as handle_new_file_helpers


def handle_new_file(testcase_content):
    # To extract the "new coverage" from the testcase I could just use the >cfg.output_path_final_coverage_map_file<
    # content. However, this would not always be correct.
    # E.g. often not deterministic coverage would also be added to this coverage map during fuzzing and therefore
    # my "new coverage" would contain too many edges (edges which the current testcase doesn't trigger or just unreliably trigger)
    # I therefore re-extract the testcase to extract new behavior again.
    # Also notice: At the end I restore the original coverage map (which already contains the non-deterministic behavior)
    # This is important, otherwise the fuzzer would always find the non-deterministic behavior again and again, which
    # would slow down the fuzzing (because I perform multiple executions when I identify non-deterministic behavior)
    utils.msg("[i] Starting to handle new file...")

    new_coverage = handle_new_file_helpers.extract_unique_coverage_of_testcase(testcase_content)
    if new_coverage is None:
        utils.msg("[-] Could not trigger new behavior again. Maybe the behavior is not deterministic, skipping input...")
        # Here is a trade-off
        # I could just return without overwriting the previous coverage map.
        # => then I can find other testcases which maybe reliable trigger the behavior
        # => However, I think that's not common and therefore I store the previous coverage map (which already
        # encodes that the coverage was already found) => I can't find it again and I won't "waste time" analysing
        # "interministic behavior" again and again (this assumption is maybe wrong, but currently I restore the coverage map)
        # edit2: I'm pretty sure it's better that I reset the coverage map to ensure I'm not analysing new coverage again and again
        # => In tests I found a lot of indeterministic coverage which would mean I would waste a lot of time
        # So the decision to reset the coverage map here is good and I should not change this.
        # If you comment out the next line, fuzzing would become a lot slower and it would be really hard to debug why
        # fuzzing would suddenly be so slow; so don't do it
        handle_new_file_helpers.reload_final_coverage_map_and_overwrite_previous_coverage_map()
        return

    # fast minimization before I start to rename variables, functions, ...
    content_minimized = testcase_content
    content_minimized = testcase_minimizer.minimize_testcase_fast(content_minimized, new_coverage, cfg.output_path_previous_coverage_map_file)

    # Start testcase renaming / standardization:
    content_minimized = testcase_standardizer.standardize_testcase(content_minimized, new_coverage, cfg.output_path_previous_coverage_map_file)

    # minimize sample (full mode):
    content_minimized = testcase_minimizer.minimize_testcase(content_minimized, new_coverage, cfg.output_path_previous_coverage_map_file)
    content_minimized = content_minimized.rstrip()

    # Create .state file:
    state = create_state_file.create_state_file_safe(content_minimized)

    # Debugging code:
    # print("Minimized Code:")
    # print(content_minimized)
    # print("State:")
    # print(state)
    # input("Press enter to import next file")

    # Now all steps which must trigger the new behavior again are finished.
    # The previous coverage (in which the new behavior was not triggered yet),
    # is therefore no longer required to reset the in-memory coverage map. It can
    # Therefore be overwritten with the coverage map which already encodes the new behavior:
    handle_new_file_helpers.reload_final_coverage_map_and_overwrite_previous_coverage_map()

    # Also add the sample to the corpus! This requires the correct runtime factor!
    ret = cfg.corpus_js_snippets.add_new_testcase_to_corpus(content_minimized, state, new_coverage, cfg.adjustment_factor_code_snippet_corpus)

    if ret is not None:  # if file was loaded to the corpus:
        (new_filename, state_file_content, required_coverage_content) = ret
        # Sync it to the bucket
        m = hashlib.md5()
        m.update(content_minimized.encode("utf-8"))
        hash_filename = str(m.hexdigest()) + ".js"
        gce_bucket_sync.save_new_corpus_file_if_not_already_exists(hash_filename, content_minimized, state_file_content, required_coverage_content)

        if cfg.deterministic_preprocessing_enabled:
            # preprocessing will later be called separately to avoid recursive function calls
            deterministic_preprocessing.add_testcase_to_preprocessing_queue(content_minimized, state, new_filename)
    utils.msg("[i] Handling new file finished!")
