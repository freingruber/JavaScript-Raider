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



# This mode can be started by passing the "--upgrade_corpus_to_new_js_engine" flag
# together with the path to the old OUTPUT directory to the fuzzer.
#
# After upgrading to a newer JS engine (or a different one), the coverage map and the
# required coverage files must be recalculated. Moreover, it's possible that some testcases
# from the corpus now throw exceptions or lead to crashes. These files can't be imported, otherwise
# the resulting corpus would create a lot of exceptions (or crashes).
# If a file doesn't create new coverage, the file will also be skipped.
# The difference of this mode compared to the --import_corpus_mode is that this mode doesn't
# perform standardization, minimization and state creation.
# Please note: it can make sense to remove the state files afterwards and re-calculate the states
# (the state is maybe different in a different engine; but this should affect only a very few testcases).
# This mode is therefore a lot faster.
# The difference to the --import_corpus_precalculated_files_mode is that the upgrade mode is used
# for different JS engine whereas the first mentioned one is used for the same JS engine.
# E.g.: If you fuzzed on two different systems the system JS-engine binary and want to merge the files,
# you should use --import_corpus_precalculated_files_mode. If you want to update the JS engine,
# then you should use the --upgrade_corpus_to_new_js_engine mode.


# TODO: Remove the disabled testcases file
# TODO: Update the extracted operations file?

# TODO: Copy the databases but not the globals pickle file!  The globals should be re-extracted with every JS engine!
# Maybe also don't copy the strings/numbers file? => Extraction is fast!

# TODO: Flag to import also files which dont lead to new coverage?


# TODO: This script is currently pretty slow (because of the engine restarts? or because of
# multiple executions to remove in-deterministic behavior?)
# Current runtime: ~1 day to upgrade a corpus to a new engine (but I expected a runtime of 1 hour)

import os
import sys
import utils
import config as cfg
from native_code.executor import Execution_Status
import handle_new_file.handle_new_file_helpers as handle_new_file_helpers
from corpus import Corpus
from testcase_state import load_state


def upgrade_corpus_to_new_js_engine_mode():
    corpus_to_import = os.path.join(os.path.abspath(cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine), cfg.current_corpus_dir)
    cfg.corpus_js_snippets = Corpus(os.path.abspath(cfg.output_dir_current_corpus))

    utils.msg("[i] Going to import files from: %s" % corpus_to_import)

    # We are not importing file 1 to <lastID>, instead we import based on file size

    files_to_handle = []
    already_seen_file_hashes = set()

    for filename_to_import in os.listdir(corpus_to_import):
        if filename_to_import.endswith(".js"):
            input_file_to_import = os.path.join(corpus_to_import, filename_to_import)

            # Just get file size
            with open(input_file_to_import, 'r') as fobj:
                content = fobj.read().rstrip()
                sample_hash = utils.calc_hash(content)
                if sample_hash not in already_seen_file_hashes:
                    # new file
                    files_to_handle.append((input_file_to_import, len(content)))
                    already_seen_file_hashes.add(sample_hash)

    utils.msg("[i] Finished reading files. Going to sort files based on file size...")
    # Sort based on filesize => start with small files => this ensures that the minimizer is faster
    files_to_handle.sort(key=lambda x: x[1])

    utils.msg("[i] Finished sorting, going to import files to upgrade to new JS engine...")

    # Now start to import file by file
    cfg.my_status_screen.set_current_operation("Importing")
    total_number_files_to_import = len(files_to_handle)
    number_files_already_handled = 0
    number_files_really_imported = 0
    number_files_exception = 0
    number_files_crash = 0
    number_files_unreliable = 0
    number_files_timeout = 0
    for entry in files_to_handle:
        (testcase_path_to_import, filesize) = entry
        number_files_already_handled += 1

        # Calculate current coverage
        number_triggered_edges, total_number_possible_edges = cfg.exec_engine.get_number_triggered_edges()
        if total_number_possible_edges == 0:
            total_number_possible_edges = 1  # avoid division by zero
        triggered_edges_in_percent = (100 * number_triggered_edges) / float(total_number_possible_edges)

        utils.msg("[i] Importing file (%d/%d; Coverage: %.4f, %d files imported; %d unreliable, %d exception; %d timeout, %d crashes): %s" % (number_files_already_handled,
                                                                                                                                              total_number_files_to_import,
                                                                                                                                              triggered_edges_in_percent,
                                                                                                                                              number_files_really_imported,
                                                                                                                                              number_files_unreliable,
                                                                                                                                              number_files_exception,
                                                                                                                                              number_files_timeout,
                                                                                                                                              number_files_crash,
                                                                                                                                              testcase_path_to_import))
        result = try_to_import_testcase(testcase_path_to_import)
        if result == "imported":
            number_files_really_imported += 1
        elif result == "exception":
            number_files_exception += 1
        elif result == "crash":
            number_files_crash += 1
        elif result == "unreliable":
            number_files_unreliable += 1
        elif result == "timeout":
            number_files_timeout += 1



def try_to_import_testcase(testcase_filepath):
    with open(testcase_filepath, 'r') as fobj:
        content = fobj.read().rstrip()

    resulted_in_new_coverage = False

    # cfg.exec_engine.restart_engine()  # Restart the engine so that every testcase to import starts in a new v8 process; But this can take very long
    for i in range(0, 3):  # try 3 times to execute the new testcase and check if it leads to new coverage
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        if result.status == Execution_Status.CRASH:
            pass    # TODO: Save the Crash!
            print("FOUND A CRASH WHILE IMPORTING:")
            print("-----------")
            print(content)
            print("-------------")
            cfg.my_status_screen.inc_stats_crash()
            (new_filename, new_filepath) = utils.store_testcase_with_crash(content)
            utils.msg("[!] Crash filename: %s" % new_filename)

            return "crash"
        elif result.status == Execution_Status.EXCEPTION_CRASH or result.status == Execution_Status.EXCEPTION_THROWN:

            # Let's also store exceptions to see which testcases result in an exception in a newer JS engine
            exceptions_dir = os.path.join(cfg.output_dir, "exceptions")
            if os.path.exists(exceptions_dir) is False:
                os.mkdir(exceptions_dir)
            utils.store_testcase_in_directory(content, exceptions_dir)
            return "exception"    # skip the testcase because it now throws an exception
        elif result.status == Execution_Status.TIMEOUT:

            exceptions_dir = os.path.join(cfg.output_dir, "timeout")
            if os.path.exists(exceptions_dir) is False:
                os.mkdir(exceptions_dir)
            utils.store_testcase_in_directory(content, exceptions_dir)
            return "timeout"
        elif result.status == Execution_Status.SUCCESS and result.num_new_edges > 0:
            resulted_in_new_coverage = True
            break

    if resulted_in_new_coverage is False:
        # Found no new coverage, so going to skip it
        return "not imported"

    # The file resulted in new coverage and should therefore further be analysed:

    # it's important to save coverage before extract_unique_coverage_of_testcase()
    # or reload_final_coverage_map_and_overwrite_previous_coverage_map() are called
    # Otherwise we would not progress in coverage because we would always overwrite the
    # global coverage map below in reload_final_coverage_map_and_overwrite_previous_coverage_map() with the
    # initial coverage map (and then this script would suddenly be very slow)
    cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)

    new_coverage = handle_new_file_helpers.extract_unique_coverage_of_testcase(content)
    if new_coverage is None:
        return "unreliable"

    # If this point is reached, the coverage can reliably be triggered and the testcase should be stored in the corpus:
    state = load_state(testcase_filepath + ".pickle")

    cfg.corpus_js_snippets.add_new_testcase_to_corpus(content, state, new_coverage, cfg.adjustment_factor_code_snippet_corpus)

    handle_new_file_helpers.reload_final_coverage_map_and_overwrite_previous_coverage_map()
    return "imported"
