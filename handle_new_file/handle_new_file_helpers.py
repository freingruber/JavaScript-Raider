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


# This script contains some helper functions to handle new files
# E.g.: functions to extract the unique new behavior of a file.
# Important: To extract unique coverage the code resets the global coverage map with
# the previous coverage. When a new testcase is added to the corpus, the two files
# "final coverage map" and "previous coverage map" would be saved (with the same content).
# When new coverage is found, the "final coverage map" will be updated on disk. Then
# The code resets in extract_unique_coverage_of_testcase() the in-memory global coverage map
# with the "previous coverage map" (which doesn't triggered the new coverage yet). So it's
# possible to trigger the new coverage again. This is important to verify that coverage can
# reliable be triggered. And it's very important for standardization and minimization
# because in these steps I need to check if I can still trigger the new coverage after a modification.
# However, bear in mind that it's important to save the in-memory global coverage map to
# the "final coverage map" file before executing extract_unique_coverage_of_testcase()
# Otherwise you would lose the original content of the global coverage map.


# TODO: I'm loading here everytime the coverage map from a file
# It would be better to later make in-memory snapshots (the exec engine supports this already)
# => I think I'm doing this already to remove unreliable results, I think I do this twice (?!)
# => But for minimization and standardization I would also need to use the snapshots to make it faster.


import config as cfg
import shutil
import native_code.coverage_helpers as coverage_helpers


# IMPORTANT: Make sure to call save the global coverage map AT SOME POINT before executing this function, e.g.:
# cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
# This function loads the previous coverage into memory which means the current coverage map will be overwritten
# To restore it later (via reload_final_coverage_map_and_overwrite_previous_coverage_map() ).
def extract_unique_coverage_of_testcase(testcase_content):
    previous_coverage = coverage_helpers.extract_coverage_from_coverage_map_file(cfg.output_path_previous_coverage_map_file)

    cfg.exec_engine.restart_engine()    # Restart to ensure that the testcase is executed in a fresh process
    new_coverage = coverage_helpers.extract_coverage_of_testcase(testcase_content, cfg.output_path_previous_coverage_map_file)
    new_coverage = coverage_helpers.remove_already_known_coverage(new_coverage, previous_coverage)
    if len(new_coverage) == 0:
        # Try it one more time to really be 100% sure that the testcase doesn't trigger new behavior (deterministically)
        cfg.exec_engine.restart_engine()
        new_coverage = coverage_helpers.extract_coverage_of_testcase(testcase_content, cfg.output_path_previous_coverage_map_file)
        new_coverage = coverage_helpers.remove_already_known_coverage(new_coverage, previous_coverage)
        if len(new_coverage) == 0:
            return None

    # If this point is reached, there is new coverage
    # Now check if all of this new coverage can reliable be triggered
    first_problem = True
    for i in range(0, 4):
        triggered_coverage = coverage_helpers.extract_coverage_of_testcase(testcase_content, cfg.output_path_previous_coverage_map_file)
        if len(triggered_coverage) == 0:
            if first_problem:
                first_problem = False
                # Try it again:
                triggered_coverage = coverage_helpers.extract_coverage_of_testcase(testcase_content, cfg.output_path_previous_coverage_map_file)
                if len(triggered_coverage) == 0:
                    return None     # triggered 2 times after each other no new coverage!
            else:
                return None     # Problem triggered again
        problem_entries = []
        for coverage_entry in new_coverage:
            if coverage_entry not in triggered_coverage:
                # utils.msg("[-] Problem finding coverage %d again in file" % coverage_entry)
                problem_entries.append(coverage_entry)

        for coverage_entry in problem_entries:
            new_coverage.remove(coverage_entry)

    if len(new_coverage) == 0:
        return None
    return new_coverage


# IMPORTANT: Make sure to call save the global coverage map AT SOME POINT before executing this function, e.g.:
# cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
def reload_final_coverage_map_and_overwrite_previous_coverage_map():
    # Restore the original coverage map and overwrite the "previous coverage map" with the current one
    # => this is required when importing the next files (which could already be triggered during the deterministic preprocessing!)
    cfg.exec_engine.load_global_coverage_map_from_file(cfg.output_path_final_coverage_map_file)

    source_file = cfg.output_path_final_coverage_map_file
    destination_file = cfg.output_path_previous_coverage_map_file
    shutil.copyfile(source_file, destination_file)
