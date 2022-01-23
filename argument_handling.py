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



# This script contains the code to handle / check the arguments
# passed to the fuzzer.

import utils
import argparse
import config as cfg
import os


def parse_arguments():
    parser = argparse.ArgumentParser(description='JavaScript Fuzzer Arguments')
    parser.add_argument("--seed", help="Set a fixed seed", default=0, type=int)
    parser.add_argument("--verbose", help="Set verbosity level", default=0, type=int)
    parser.add_argument("--corpus_js_files_dir", help="Set the corpus directory of JavaScript files (code snippets)", type=str, required=False)
    parser.add_argument("--corpus_template_files_dir", help="Set a corpus directory of template files (which specify JS callback locations)", type=str, required=False)
    parser.add_argument("--coverage_map", help="Set the current coverage map of the code snippet corpus.", type=str, required=False)
    parser.add_argument("--output_dir", help="Set the output directory", type=str, required=True)
    parser.add_argument("--measure_mode", help="Measures the performance and stops after some executions", action='store_true')
    parser.add_argument("--test_mode", help="Enables test mode which compares different mutation and merging implementations", action='store_true')
    parser.add_argument("--developer_mode", help="Enables developer mode to implement new mutations", action='store_true')
    parser.add_argument("--recalculate_globals", help="Forces to calculate globals at runtime instead of using cached entries", action='store_true')
    parser.add_argument("--resume", help="Resumes a previous fuzzing session", action='store_true')
    parser.add_argument("--import_corpus_mode", help="Set the import corpus dir", type=str, required=False)
    parser.add_argument("--deterministic_preprocessing_mode_start_tc_id", help="Set a testcase ID from input corpus to start preprocessing.", required=False, default=None, type=int)
    parser.add_argument("--deterministic_preprocessing_mode_stop_tc_id", help="Set a testcase ID from input corpus to stop preprocessing.", required=False, default=None, type=int)
    parser.add_argument("--import_corpus_precalculated_files_mode", help="Set the import corpus dir (for files which already contain a .pickle state file", type=str, required=False)
    parser.add_argument("--minimize_corpus_mode", help="Minimizes the number of files in the corpus and reduces the file sizes and attempts to rename variables. Runtime of several days. Requires 3-4 GB of RAM!", action='store_true')
    parser.add_argument("--find_problematic_corpus_files_mode", help="Tries to find testcases with problems which must manually be fixed (e.g. incorrect state, variables were not renamed, ...)", action='store_true')
    parser.add_argument("--fix_corpus_mode", help="Fixes the corpus (e.g. creates missing state files for corpus entries)", action='store_true')
    parser.add_argument("--recalculate_testcase_runtimes_mode", help="Executes every testcase from the corpus and updates the runtime in the corresponding state file", action='store_true')
    parser.add_argument("--recalculate_state", help="Recalculate a state of a specific testcase: Argument must be something like tc123.js or all", type=str, required=False)
    parser.add_argument("--check_corpus_mode", help="Checks all testcases in the corpus and removes testcases which don't trigger their required coverage anymore", action='store_true')
    parser.add_argument("--recalculate_coverage_map_mode", help="Recalculates the coverage map. Can be useful when starting to fuzz a newer version of the JS engine.", action='store_true')
    parser.add_argument("--create_template_corpus_via_injection_mode", help="Creates template files from the input corpus dir.", action='store_true')
    parser.add_argument("--skip_executions", help="Just create testcases but don't execute them via JS engine. This mode is mainly used to measure how many testcases / sec the fuzzer can generate.", action='store_true')
    parser.add_argument("--max_executions", help="Set the maximum number of executions. After these executions the fuzzer stops. Mainly used to measure performance", default=0, type=int)
    parser.add_argument("--disable_coverage", help="Disables coverage feedback (faster fuzzing speed). This can be useful for final fuzzing runs when a good input corpus is already available and fuzzing should be faster.", action='store_true')
    parser.add_argument("--testsuite",
                        help="Start the testsuite. Possible arguments: all, exec_engine, coverage_feedback, speed_optimized_functions, corpus, operations_database, state_operations, mutations",
                        type=str, required=False)

    parser.add_argument("--upgrade_corpus_to_new_js_engine", help="To upgrade a corpus from an old JS engine to a newer/different JS engine, pass the path to the old output/working directory with this flag.", type=str, required=False)
    parser.add_argument("--extract_data", help="Extracts data from the corpus into databases. Valid arguments are: numbers_and_strings and operations", type=str, required=False)

    cfg.fuzzer_arguments = parser.parse_args()
    cfg.skip_executions = cfg.fuzzer_arguments.skip_executions
    if cfg.fuzzer_arguments.seed == 0:
        cfg.fuzzer_arguments.seed = utils.get_random_seed()


def check_if_arguments_are_correct():
    how_many_modes_are_enabled = 0
    if cfg.fuzzer_arguments.measure_mode:
        utils.msg("[i] Enabling measure mode")
        # I'm using the measure mode to check new mutation or merge operations
        # It can be enabled by passing the "--measure_mode" flag
        # E.g.: when I add a "remove line" mutation, it leads to more invalid testcases
        # To count how many exceptions the fuzzer creates and how the mutation affects the
        # execution speed I measure it.
        # Important: When this is done the input corpus should be small!
        # Measure mode: It prints additional statistics, but fuzzing is normal
        # and fuzzing will stop after a predefined number of iterations
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.developer_mode:
        utils.msg("[i] Enabling developer mode")
        # Developer mode is to develop new mutations
        # In this mode I don't load the full corpus (which would take a long time)
        # instead, I manually pass some interesting testcases to the newly developed
        # mutation operation and check if the mutation and the state update are correct
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.test_mode:
        utils.msg("[i] Enabling test mode")
        # Test mode does not perform real fuzzing (as done in measure mode)
        # Instead, in test mode I perform only 1 mutation per testcase
        # and I do the same mutation for several testcases and then print
        # the success rate and exec/speed.
        # This allows to compare mutation strategies (e.g.: to identify mutation strategies
        # which often result in an exception. Or mutations which often result in testcases which
        # timeout. It helps to identify flaws in the mutation implementation.
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.minimize_corpus_mode:
        utils.msg("[i] Enabling minimize corpus mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.find_problematic_corpus_files_mode:
        utils.msg("[i] Enabling find problematic corpus files mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.check_corpus_mode:
        utils.msg("[i] Enabling check corpus mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.create_template_corpus_via_injection_mode:
        utils.msg("[i] Enabling create template corpus via injection mode")
        if cfg.fuzzer_arguments.corpus_template_files_dir is None:
            utils.perror("[-] You can just use the --create_template_corpus_via_injection_mode together with the --corpus_template_files_dir option!")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.fix_corpus_mode:
        utils.msg("[i] Enabling fix corpus mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.recalculate_coverage_map_mode:
        utils.msg("[i] Enabling recalculate coverage map mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.recalculate_testcase_runtimes_mode:
        utils.msg("[i] Enabling recalculate testcase runtimes mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.skip_executions:
        utils.msg("[i] Enabling skip executions mode")
        how_many_modes_are_enabled += 1
    if cfg.fuzzer_arguments.testsuite:
        utils.msg("[i] Enabling testsuite mode")
        how_many_modes_are_enabled += 1
        testsuite_arg = cfg.fuzzer_arguments.testsuite.lower()
        allowed_args = ["all", "exec_engine", "coverage_feedback", "speed_optimized_functions", "corpus", "operations_database", "state_operations", "mutations"]
        if testsuite_arg not in allowed_args:
            utils.perror("Unkown --testsuite argument: %s" % cfg.fuzzer_arguments.testsuite)
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --testsuite options together with --resume !")
    if cfg.fuzzer_arguments.max_executions != 0:
        utils.msg("[i] Max number of executions: %d" % cfg.fuzzer_arguments.max_executions)
    if cfg.fuzzer_arguments.recalculate_state is not None:
        utils.msg("[i] Enabling recalculate state mode")
        how_many_modes_are_enabled += 1
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --recalculate_state option together with --resume!")
    if cfg.fuzzer_arguments.import_corpus_mode is not None:
        utils.msg("[i] Import corpus mode")
        how_many_modes_are_enabled += 1
        # Ensure the user knows how to correctly call this option and what the input files are for this mode
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --import_corpus_mode option together with --resume!")
        if cfg.fuzzer_arguments.import_corpus_precalculated_files_mode is not None:
            utils.perror("[-] Arguments --import_corpus_mode and --import_corpus_precalculated_files_mode can't be combined!")
    if cfg.fuzzer_arguments.import_corpus_precalculated_files_mode is not None:
        utils.msg("[i] Import corpus mode (with precalculated state files)")
        how_many_modes_are_enabled += 1
        # Ensure the user knows how to correctly call this option and what the input files are for this mode
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --import_corpus mode option together with --resume!")

    if cfg.fuzzer_arguments.extract_data is not None:
        utils.msg("[i] Extract data mode enabled")
        how_many_modes_are_enabled += 1

        if cfg.fuzzer_arguments.extract_data != "numbers_and_strings" and cfg.fuzzer_arguments.extract_data != "operations":
            utils.perror("[-] Wrong argument to --extract_data. Valid arguments are: numbers_and_strings or operations")

        # Ensure the user knows how to correctly call this option and what the input files are for this mode
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --extract_data mode option together with --resume!")

    if cfg.fuzzer_arguments.resume is False:
        # First invocation of the fuzzer
        if cfg.fuzzer_arguments.corpus_js_files_dir is None and cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine is None:
            utils.perror("[-] --corpus_js_files_dir or --upgrade_corpus_to_new_js_engine option is missing! You need to specify an input corpus via one of the two options! Or you must start the fuzzer with the --resume option.")
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None and cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine is not None:
            utils.perror("[-] You can't pass --corpus_js_files_dir together with --upgrade_corpus_to_new_js_engine")
    else:
        # In Resume mode you can't pass these two flags:
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None:
            utils.perror("[-] --corpus_js_files_dir can't be passed together with the --resume option!")
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None:
            utils.perror("[-] --upgrade_corpus_to_new_js_engine can't be passed together with the --resume option!")


    if cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id is not None:
        utils.msg("[i] Deterministic preprocessing mode - start testcase ID is: %d" % cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id)
        how_many_modes_are_enabled += 1
        if cfg.fuzzer_arguments.resume is False:
            utils.perror("[-] You can just use the --deterministic_preprocessing_mode_start_tc_id argument together with the --resume option!")
        if cfg.fuzzer_arguments.deterministic_preprocessing_mode_stop_tc_id is None:
            # set it to a high number so that all testcases will be preprocessed
            cfg.fuzzer_arguments.deterministic_preprocessing_mode_stop_tc_id = 99999999999  # TODO: Maybe just set this as default value in arg parser?
    else:
        # start ID is none
        if cfg.fuzzer_arguments.deterministic_preprocessing_mode_stop_tc_id is not None:
            utils.perror("[-] You can just use the --deterministic_preprocessing_mode_stop_tc_id argument together with the --deterministic_preprocessing_mode_start_tc_id argument!")

    if how_many_modes_are_enabled > 1:
        utils.perror("[-] You can only enable one mode at a time!")

    if cfg.fuzzer_arguments.resume:
        utils.msg("[+] Resuming previous fuzzing session...")
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None:
            utils.perror("[-] Resume mode doesn't allow the --corpus_js_files_dir argument. Please remove the argument.")
        if os.path.exists(cfg.fuzzer_arguments.output_dir) is False or os.path.isdir(cfg.fuzzer_arguments.output_dir) is False:
            utils.perror("[-] Error with the specified output directory (The directory must exist in --resume mode). Stopping...")

        coverage_map_path_from_previous_session = os.path.join(cfg.fuzzer_arguments.output_dir, cfg.final_coverage_map_file)
        if os.path.exists(coverage_map_path_from_previous_session) is False:
            utils.perror("[-] Coverage map from previous session does not exist. Is this a correct output directory? Stopping...")
    else:
        # Not resuming - so it's the first execution
        # Check if the output directory is correct
        if utils.check_outdir(cfg.fuzzer_arguments.output_dir) is False:
            utils.perror("[-] Error with the specified output directory (does it exist? is it empty?). Stopping...")
    utils.msg("[+] Output directory seems to be correct: %s" % cfg.fuzzer_arguments.output_dir)

    js_template_path = cfg.fuzzer_arguments.corpus_template_files_dir
    if js_template_path is not None:
        if os.path.isdir(js_template_path) is False:
            utils.perror("[-] Specified Template corpus directory (>%s<) seems to be wrong. Does it exist?" % js_template_path)

    if cfg.fuzzer_arguments.resume is False:
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None and os.path.isdir(cfg.fuzzer_arguments.corpus_js_files_dir) is False:
            utils.perror("[-] Specified JavaScript corpus directory (>%s<) seems to be wrong. Does it exist?" % cfg.fuzzer_arguments.corpus_js_files_dir)
        if cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine is not None and os.path.isdir(cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine) is False:
            utils.perror("[-] Specified upgrade output directory (>%s<) seems to be wrong. Does it exist?" % cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine)

    # If this point is reached, the fuzzer arguments seem to be correct
