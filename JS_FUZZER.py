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



# This script starts the fuzzing. Before it can be started, v8 must be compiled,
# the correct v8/d8 path must be configured in config.py
# the system must be prepared for fuzzing (prepare_system_for_fuzzing.sh) and the 
# corpus files must already be calculated.
# Fuzzing can be configured via the variables in config.py
# For details check the README.md file

import os
import utils
import config as cfg
import datetime
import signal
import time
from corpus import Corpus
from template_corpus import Template_Corpus
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import hashlib 
from native_code.executor import Executor, Execution_Status
from handle_new_file.handle_new_file import handle_new_file
import sync_engine.gce_bucket_sync as gce_bucket_sync
import testcase_state
import modes.deterministic_preprocessing as deterministic_preprocessing
from modes.find_problematic_corpus_files import find_problematic_corpus_files
from modes.check_corpus import check_corpus
from modes.fix_corpus import fix_corpus
from modes.recalculate_testcase_runtimes import recalculate_testcase_runtimes
from modes.recalculate_state import recalculate_state
from modes.corpus_minimizer import minimize_corpus
from modes.developer_mode import start_developer_mode
from modes.import_corpus import import_corpus_mode
from modes.upgrade_corpus_to_new_js_engine_mode import upgrade_corpus_to_new_js_engine_mode
import pickle
import testcase_mergers.testcase_merger as testcase_merger
from testcase_mergers.implementations.merge_testcase_append import merge_testcase_append
import mutators.testcase_mutator as testcase_mutator
import mutators.database_operations as database_operations
from mutators.implementations.mutation_do_nothing import mutation_do_nothing
from mutators.implementations.mutation_insert_random_operation_from_database_at_specific_line import mutation_insert_random_operation_from_database_at_specific_line
from mutators.implementations.mutation_insert_random_operation_at_specific_line import mutation_insert_random_operation_at_specific_line
from status_screen import Status_Screen
import argument_handling as arg_handling
from testsuite.execute_testsuite import execute_testsuite
import data_extractors.extract_numbers_and_strings as extract_numbers_and_strings
import data_extractors.extract_operations.extract_operations as extract_operations

# from callback_injector.create_template_corpus_via_injection import create_template_corpus_via_injection


# TODO: Move the global variable (and associated code) into the sync-module
last_sync_time = 0


def main():
    utils.enable_color_support()
    cfg.my_status_screen = Status_Screen()  # Create a status screen which later prints fuzzer statistics

    utils.check_if_system_is_prepared_for_fuzzing()

    arg_handling.parse_arguments()
    arg_handling.check_if_arguments_are_correct()

    utils.set_fuzzer_seed()
    utils.set_verbose_level()

    configure_all_filesystem_paths()

    utils.create_and_open_logfile()  # Everything below this line will be logged/written to the fuzzer log
    utils.dump_fuzzer_arguments_and_configuration()

    # Initialize the JavaScript engine executor & load the coverage map
    initialize_exec_engine()

    load_databases()    # databases contain extracted JS operations, numbers, strings, global available variables in JS engines and so on

    # Make some required functions available to sub modules
    cfg.perform_execution_func = perform_execution
    cfg.deterministically_preprocess_queue_func = deterministically_preprocess_queue

    start_possible_early_modes()  # early modes don't require a loaded JS / template corpus

    cfg.corpus_js_snippets = load_js_snippets_corpus()

    import_testcases_if_first_fuzzer_invocation()

    check_if_templates_should_be_created_via_callback_injection()
    cfg.corpus_template_files = load_js_template_corpus()

    adjust_testcase_runtimes()  # if the corpus was created on a different system (slower or faster), the expected testcase runtimes are updated here
    gce_bucket_sync.initialize()

    tagging.clear_current_tags()
    cfg.my_status_screen.reset_stats()
    cfg.exec_engine.reset_total_testcases_execution_time()  # reset the counter so that exec time from dummy executions or runtime adjustment are not counted

    signal.signal(signal.SIGINT, cfg.my_status_screen.signal_handler)  # Dump results when ctrl+c is pressed

    start_possible_late_modes()  # late modes require a loaded JS / template corpus

    main_fuzzer_loop()


def main_fuzzer_loop():
    while True:
        # Start of the next fuzzer iteration:
        # input("Press enter to create next testcase")      # Debugging code

        if cfg.deterministic_preprocessing_enabled:
            deterministically_preprocess_queue()
        sync_import_new_files_from_other_fuzzers()

        tagging.add_tag(Tag.MAIN_FUZZER_LOOP)
        cfg.my_status_screen.set_current_operation("Fuzzing")

        if cfg.templates_enabled and utils.likely(cfg.likelihood_to_load_template_file):
            # Mutate a template file
            tagging.add_tag(Tag.MUTATE_TEMPLATE_FILE)
            (final_testcase, final_testcase_state) = get_random_testcase_with_template()

            # Calculate how many mutations should be applied
            number_mutations = utils.get_random_int(cfg.template_number_mutations_min,
                                                    cfg.template_number_mutations_max)
            number_late_mutations = utils.get_random_int(cfg.template_number_late_mutations_min,
                                                         cfg.template_number_late_mutations_max)
        else:
            # Mutate testcases only
            tagging.add_tag(Tag.MUTATE_TESTCASE_ONLY)
            number_testcases_to_combine = utils.get_random_int(cfg.testcases_to_combine_min,
                                                               cfg.testcases_to_combine_max)
            (final_testcase, final_testcase_state) = get_combined_testcase(number_testcases_to_combine)

            # Calculate how many mutations should be applied
            number_mutations = utils.get_random_int(cfg.number_mutations_min, cfg.number_mutations_max)
            number_late_mutations = utils.get_random_int(cfg.number_late_mutations_min, cfg.number_late_mutations_max)

        # And now perform random mutations on the final (merged) testcase
        # Early mutations:
        for i in range(number_mutations):
            (final_testcase, final_testcase_state) = testcase_mutator.randomly_mutate_js_sample(final_testcase,
                                                                                                final_testcase_state)

        # Late mutations:
        for i in range(number_late_mutations):
            (final_testcase, final_testcase_state) = testcase_mutator.randomly_mutate_late_js_sample(final_testcase,
                                                                                                     final_testcase_state)

        # utils.print_code_with_line_numbers(final_testcase)
        perform_execution(final_testcase, final_testcase_state)


def perform_execution(content, state):

    if "new Worker" in content:
        # Hotfix to prevent multiple v8 processes
        # Note: A Better Idea would be to do something like:
        # https://stackoverflow.com/questions/32222681/how-to-kill-a-process-group-using-python-subprocess/32222971
        # => Create a process group and kill the full process group
        # TODO: Test if this (killing a process group) takes noticeable longer than killing a single process
        return

    """
    # These are stupid fixes which fix very frequently occurring crashes
    # which the v8 devs are not going to fix (?)
    if ".repeat(" in content and ".split(" in content:
        return  # skip a current v8 bug which creates a lot of crashes
    if ".repeat(" in content and "0x201f" in content:
        return
    if "318909551" in content:
        return
    if "318909513" in content:
        return
    """

    if "const " in content:
        # Just debugging code, I think that a lot of executions result in an exception because of const variables
        # E.g.:
        # const var_1_ = ...
        # ...
        # and I later add as operation code such as:
        # var var_5_ = var_2_, var_1_, var_3_;
        # => this will lead to an exception and this occurs "very often"
        # This also means that I must remove such operations from the operations-database, TODO
        tagging.add_tag(Tag.TESTCASE_CONTAINS_CONST_VARIABLE)
    else:
        tagging.add_tag(Tag.TESTCASE_DOES_NOT_CONTAIN_CONST_VARIABLE)

    cfg.my_status_screen.inc_number_fuzzing_executions()
    if state is None:
        cfg.my_status_screen.add_expected_runtime_total_sum(cfg.v8_timeout_per_execution_in_ms_max)

        timeout_to_use = cfg.v8_timeout_per_execution_in_ms_max
    else:
        cfg.my_status_screen.add_expected_runtime_total_sum(state.runtime_length_in_ms)
        timeout_to_use = get_timeout_to_use(expected_runtime=state.runtime_length_in_ms)

    if cfg.skip_executions:
        # This mode is used to measure fuzzer performance without the JavaScript Engine (real executions are just skipped)
        # This can be used to calculate the maximum number of testcase the fuzzer can generate
        result = Execution_Status.SUCCESS
    else:
        # DEFAULT Mode: Perform the execution
        result = cfg.exec_engine.execute_safe(content, custom_timeout=timeout_to_use)

    # Debugging code to find flawed mutations:
    # if result.status == Execution_Status.EXCEPTION_THROWN and tagging.check_if_tag_is_in_current_tags(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_real_number):

    # Now set the correct tags based on the result
    # This must be done here before the call to tagging.execution_finished()
    if result.status == Execution_Status.SUCCESS:
        log_tagging_with_success(timeout_to_use)  # used to detect in which cases I get hangs (which reduce my execution speed!)
    elif result.status == Execution_Status.TIMEOUT:
        log_tagging_with_hang(timeout_to_use)  # used to detect in which cases I get hangs (which reduce my execution speed!)

    if result.status == Execution_Status.INTERNAL_ERROR:
        # This is a "stupid hack": The crash_exceptions just occur when a "new Worker" is created and therefore v8 forks
        # However, after fuzzing several days sometimes an "internal error occurs"
        # I just want to save these files to the local filesystem (as exception crashes)
        # Edit: I think this no longer occurs? Just to make sure that I save them in the future I store them for analysis
        result.status = Execution_Status.EXCEPTION_CRASH

    cfg.my_status_screen.add_real_runtime_total_sum(result.exec_time)
    tagging.execution_finished(result)

    # Here is the real check if the return status:
    if result.status == Execution_Status.SUCCESS:
        cfg.my_status_screen.inc_stats_success()
        if result.num_new_edges > 0:
            cfg.my_status_screen.inc_stats_new_behavior()
            utils.msg("[+] New coverage found with %d new edges" % result.num_new_edges)
            (new_filename, new_filepath) = utils.store_testcase_in_directory(content, cfg.output_dir_new_files)

            # Dump the new coverage statistics
            number_triggered_edges, total_number_possible_edges = cfg.exec_engine.get_number_triggered_edges()
            if total_number_possible_edges == 0:
                total_number_possible_edges = 1  # avoid division by zero
            triggered_edges_in_percent = (100 * number_triggered_edges) / float(total_number_possible_edges)

            utils.msg("[i] New coverage: %d (initial: %d) ; Percentage: %.4f %% (initial: %.4f %%): %s" % (
                number_triggered_edges,
                cfg.my_status_screen.get_initial_coverage_triggered_edges(),
                triggered_edges_in_percent,
                cfg.my_status_screen.get_initial_coverage_percent(),
                new_filename))

            # Save the coverage map
            cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
            tagging.dump_current_tags_to_file(new_filepath + cfg.tagging_filename_extension)
            cfg.my_status_screen.update_last_new_coverage_time()

            # I no longer store these files in the GCE bucket => this result in way too many bucket operations
            # and bucket operations are very slow / buggy
            # gce_bucket_sync.save_new_behavior_file_if_not_already_exists(new_filename, content)
            # => The below handle_new_file() checks if the coverage can reliably be triggered and just in this case
            # I'm then syncing to the GCE bucket.

            # Handle the new file (standardize, minimize & analyse it, perform deterministic processing and add everything to the current corpus)
            handle_new_file(content)

    elif result.status == Execution_Status.CRASH:
        cfg.my_status_screen.inc_stats_crash()
        utils.msg("[!] CRASH FOUND:")
        print(content)
        new_filename = None
        try:
            (new_filename, new_filepath) = utils.store_testcase_with_crash(content)
            utils.msg("[!] Crash filename: %s" % new_filename)
            crash_tagging_file_content = tagging.dump_current_tags_to_file(new_filepath + cfg.tagging_filename_extension)
        except:
            # happens when the crash dir was already created (e.g. same vuln was found again)
            crash_tagging_file_content = ""
        cfg.my_status_screen.update_last_crash_time()

        if new_filename is not None:
            gce_bucket_sync.save_new_crash_file_if_not_already_exists(new_filename, content, crash_tagging_file_content)

    elif result.status == Execution_Status.EXCEPTION_CRASH:
        cfg.my_status_screen.inc_stats_exception_crash()
        utils.msg("[!] FOUND a potential crash (likely just exception):")
        print(content)
        try:
            (new_filename, new_filepath) = utils.store_testcase_with_crash_exception(content)
            utils.msg("[!] Crash filename: %s" % new_filename)
            tagging.dump_current_tags_to_file(new_filepath + cfg.tagging_filename_extension)
        except:
            pass  # triggers when the crash dir was already triggered (e.g. same vuln was found again)

        cfg.my_status_screen.update_last_crash_exception_time()
        # Note: These files are not synchronized into a bucket because they are not real crashes

    elif result.status == Execution_Status.EXCEPTION_THROWN:
        cfg.my_status_screen.inc_stats_exception()
    elif result.status == Execution_Status.TIMEOUT:
        cfg.my_status_screen.inc_stats_timeout()

    tagging.clear_current_tags()  # Reset the tags for next iteration
    cfg.my_status_screen.update_stats()


def load_js_template_corpus():
    # Note: The template corpus is NOT stored in the output/working directory because every fuzzing instance
    # requires a separate OUTPUT directory. Since the template corpus is currently huge, I just want to store
    # it once for every fuzzing instance. It's therefore outside of the OUTPUT directory
    js_template_path = cfg.fuzzer_arguments.corpus_template_files_dir
    if js_template_path is None or cfg.fuzzer_arguments.import_corpus_mode or cfg.fuzzer_arguments.minimize_corpus_mode:
        # If no path was passed or one of the modes (import mode or minimize corpus mode) was selected,
        # then I don't need to load the template corpus because it's not required.
        return None

    corpus_template_files = Template_Corpus(os.path.abspath(js_template_path))
    corpus_template_files.load_corpus_from_directory()
    return corpus_template_files


def check_if_templates_should_be_created_via_callback_injection():
    if cfg.fuzzer_arguments.create_template_corpus_via_injection_mode:
        utils.exit_and_msg("[!] TODO: Code must be refactored")
    # if cfg.fuzzer_arguments.create_template_corpus_via_injection_mode:
    #    create_template_corpus_via_injection()
    #    utils.exit_and_msg("[+] Finished creation of template files via callback injection, stopping now...")


def load_js_snippets_corpus():
    corpus_js_snippets = Corpus(os.path.abspath(cfg.output_dir_current_corpus))
    corpus_js_snippets.load_corpus_from_directory()
    return corpus_js_snippets


def recalculate_coverage_map():
    utils.msg("[+] Going to recalculate coverage map...")
    utils.msg("[i] output_dir_current_corpus: %s" % cfg.output_dir_current_corpus)
    utils.msg("[i] output_path_final_coverage_map_file: %s" % cfg.output_path_final_coverage_map_file)

    last_testcase_id = utils.get_last_testcase_number(cfg.output_dir_current_corpus)

    for current_id in range(1, last_testcase_id+1):
        filename = "tc%d.js" % current_id
        filepath = os.path.join(cfg.output_dir_current_corpus, filename)
        if os.path.isfile(filepath) is False:
            continue

        utils.msg("[i] Handling file %s of %d files" % (filename, last_testcase_id))

        with open(filepath, 'r') as fobj:
            content = fobj.read().rstrip()

        for i in range(cfg.number_executions_during_initial_coverage_map_calculation):
            result = cfg.exec_engine.execute_safe(content)
            if result.status != Execution_Status.SUCCESS:
                utils.msg("[-] Found result different to success: %s => %s" % (filename, result.get_status_str()))

    cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
    utils.msg("[+] Successfully saved final coverage map to: %s" % cfg.output_path_final_coverage_map_file)


def initialize_exec_engine():
    coverage_map_path = cfg.output_path_final_coverage_map_file

    if cfg.fuzzer_arguments.resume is False:
        # It's the first execution and the coverage map therefore does not exist
        cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_max, enable_coverage=True)
        cfg.exec_engine.adjust_coverage_with_dummy_executions()
        cfg.exec_engine.save_global_coverage_map_in_file(coverage_map_path)

        # Save also some other coverage maps which are used by the sub modules to revert the coverage map
        cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_previous_coverage_map_file)
        return

    if cfg.fuzzer_arguments.testsuite:
        if cfg.fuzzer_arguments.disable_coverage:
            cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_testsuite, enable_coverage=False)
        else:
            cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_testsuite, enable_coverage=True)
            cfg.exec_engine.adjust_coverage_with_dummy_executions()
            # Save a coverage map with "empty coverage" so that the testsuite can later reset the coverage to
            # an empty coverage (to check if coverage can be found again after loading a saved coverage map)
            cfg.exec_engine.save_global_coverage_map_in_file(cfg.coverage_map_testsuite)
        return

    if os.path.isfile(coverage_map_path) is False:
        utils.perror("[-] Coverage map path seems to be wrong: %s" % coverage_map_path)

    if cfg.fuzzer_arguments.create_template_corpus_via_injection_mode:
        # enable_coverage=False => ensures that we run maximum speed (without coverage feedback)
        # when searching for new template files
        cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_templates_creation, enable_coverage=False)
        return

    if cfg.fuzzer_arguments.minimize_corpus_mode \
            or cfg.fuzzer_arguments.find_problematic_corpus_files_mode \
            or cfg.fuzzer_arguments.check_corpus_mode \
            or cfg.fuzzer_arguments.recalculate_coverage_map_mode:
        cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_corpus_minimizer * 2, enable_coverage=True)
        cfg.exec_engine.adjust_coverage_with_dummy_executions()
        cfg.exec_engine.save_global_coverage_map_in_file(cfg.coverage_map_corpus_minimizer)
        return    # the other stuff is not required
    else:
        if cfg.fuzzer_arguments.disable_coverage:
            cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_max, enable_coverage=False)
        else:
            # Default mode with coverage feedback enabled
            cfg.exec_engine = Executor(timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_max, enable_coverage=True)
            cfg.exec_engine.adjust_coverage_with_dummy_executions()

    if cfg.fuzzer_arguments.disable_coverage or cfg.fuzzer_arguments.developer_mode:
        return   # coverage map must not be loaded

    utils.msg("[i] Going to start to load coverage map...")
    cfg.exec_engine.load_global_coverage_map_from_file(coverage_map_path)

    number_triggered_edges, total_number_possible_edges = cfg.exec_engine.get_number_triggered_edges()
    triggered_edges_in_percent = (100 * number_triggered_edges) / float(total_number_possible_edges)
    cfg.my_status_screen.set_initial_coverage(number_triggered_edges, triggered_edges_in_percent)

    utils.msg("[+] Successfully loaded the coverage map with %d of %d possible edges" % (number_triggered_edges, total_number_possible_edges))
    utils.msg("[+] Initial coverage is: %.4f %%" % triggered_edges_in_percent)



def load_databases():
    # The databases are just loaded if fuzzing is performed.
    # Most modes don't require the databases because mutations or globals are not accessed
    # In these cases loading of databases can be skipped:
    if cfg.fuzzer_arguments.resume is False \
            or cfg.fuzzer_arguments.minimize_corpus_mode \
            or cfg.fuzzer_arguments.find_problematic_corpus_files_mode \
            or cfg.fuzzer_arguments.check_corpus_mode \
            or cfg.fuzzer_arguments.recalculate_coverage_map_mode \
            or cfg.fuzzer_arguments.create_template_corpus_via_injection_mode \
            or cfg.fuzzer_arguments.testsuite \
            or cfg.fuzzer_arguments.import_corpus_mode\
            or cfg.fuzzer_arguments.extract_data:
        return  # skip loading the databases

    # If this point is reached, standard fuzzing is going to start
    # => mutations require loaded databases, so load them here:
    database_operations.initialize()


def get_timeout_to_use(expected_runtime):
    timeout_to_use = expected_runtime * cfg.v8_default_timeout_multiplication_factor
    if timeout_to_use < cfg.v8_timeout_per_execution_in_ms_min:
        tagging.add_tag(Tag.RUNTIME_ENFORCE_MINIMUM)
        timeout_to_use = cfg.v8_timeout_per_execution_in_ms_min    # enforce a minimum runtime
    elif timeout_to_use > cfg.v8_timeout_per_execution_in_ms_max:
        tagging.add_tag(Tag.RUNTIME_ENFORCE_MAXIMUM)
        timeout_to_use = cfg.v8_timeout_per_execution_in_ms_max     # enforce a maximum runtime

        # TODO: If the timeout_to_use is very very huge, e.g. lets say it's 8 seconds but I enforce a maximum of 2 seconds.
        # Does it then make sense to execute the code anyway? It will very likely lead to a hang which is time consuming.
        # Maybe I should just skip these testcases to get a better performance?
        # => Test this (But does this really occur? In such a case I should maybe reduce the number of testcases/mutations)
    else:
        tagging.add_tag(Tag.RUNTIME_DEFAULT_RUNTIME)
    return timeout_to_use


def log_tagging_with_success(timeout_to_use):
    if timeout_to_use == cfg.v8_timeout_per_execution_in_ms_min:
        tagging.add_tag(Tag.RUNTIME_SUCCESS_WITH_MINIMUM_ENFORCED)
    elif timeout_to_use == cfg.v8_timeout_per_execution_in_ms_max:
        tagging.add_tag(Tag.RUNTIME_SUCCESS_WITH_MAXIMUM_ENFORCED)
    else:
        tagging.add_tag(Tag.RUNTIME_SUCCESS_WITH_DEFAULT_RUNTIME)


def log_tagging_with_hang(timeout_to_use):
    if timeout_to_use == cfg.v8_timeout_per_execution_in_ms_min:
        tagging.add_tag(Tag.RUNTIME_HANG_WITH_MINIMUM_ENFORCED)
    elif timeout_to_use == cfg.v8_timeout_per_execution_in_ms_max:
        tagging.add_tag(Tag.RUNTIME_HANG_WITH_MAXIMUM_ENFORCED)
    else:
        tagging.add_tag(Tag.RUNTIME_HANG_WITH_DEFAULT_RUNTIME)



def get_random_testcase_for_insertion_point_in_template():
    number_testcases_to_combine = utils.get_random_int(cfg.testcases_to_combine_for_insertion_point_in_template_min, cfg.testcases_to_combine_for_insertion_point_in_template_max)
    return get_combined_testcase(number_testcases_to_combine)


def get_combined_testcase(number_testcases_to_combine):
    # get an initial testcase and then merge all others with this one
    (filename, final_testcase, final_testcase_state) = cfg.corpus_js_snippets.get_random_testcase(runtime_adjustment_factor=cfg.adjustment_factor_code_snippet_corpus)

    # tagging.add_testcase(filename)
    for i in range(number_testcases_to_combine-1):
        (filename, content, state) = cfg.corpus_js_snippets.get_random_testcase(runtime_adjustment_factor=cfg.adjustment_factor_code_snippet_corpus)
        # tagging.add_testcase(filename)
        # Merge the testcases using a random technique
        (final_testcase, final_testcase_state) = testcase_merger.merge_two_testcases_randomly(final_testcase, final_testcase_state, content, state)

    return final_testcase, final_testcase_state


def get_random_testcase_with_template():
    insertion_point_lines = []

    number_templates_to_combine = utils.get_random_int(cfg.templates_to_combine_min, cfg.templates_to_combine_max)
    (template_filename, final_testcase, final_testcase_state) = cfg.corpus_template_files.get_random_testcase(
        runtime_adjustment_factor_self_created=cfg.adjustment_factor_template_files_self_created_files,
        runtime_adjustment_factor_injected_callbacks=cfg.adjustment_factor_template_files_injected_callbacks)

    # print(template_filename)    # for debugging
    # utils.print_code_with_line_numbers(final_testcase)

    insertion_point_lines.append(0)    # line 0 means we can insert before the first template
    insertion_point_lines.append(final_testcase_state.testcase_number_of_lines)    # after the last line 

    for i in range(number_templates_to_combine-1):
        (temp_filename, content, state) = cfg.corpus_template_files.get_random_testcase(
            runtime_adjustment_factor_self_created=cfg.adjustment_factor_template_files_self_created_files,
            runtime_adjustment_factor_injected_callbacks=cfg.adjustment_factor_template_files_injected_callbacks)

        # Merge the testcases by appending the template at the end (other insertion methods doesn't make sense)
        (final_testcase, final_testcase_state) = merge_testcase_append(final_testcase, final_testcase_state, content, state)
        insertion_point_lines.append(final_testcase_state.testcase_number_of_lines)

    # print("BEFORE:")
    # utils.print_code_with_line_numbers(final_testcase)
    # print(final_testcase_state)
    # print("-----------")

    lines = final_testcase.split("\n")
    lines_len = len(lines)
    line_number = 0
    # Now iterate through all possible lines and mark the lines where a callback was executed
    for line in lines:
        if cfg.v8_print_js_codeline in line:
            insertion_point_lines.append(line_number)
        line_number += 1

    insertion_point_lines.sort()

    # Comment out the fuzzilli codelines, including lines like:
    # fuzzilli('FUZZILLI_PRINT', '_NOT_REACHED_');
    final_testcase = final_testcase.replace(cfg.v8_print_start, "//%s" % cfg.v8_print_start)
    # Now, instead of removing the lines, I just comment out all "fuzzilli(" lines
    # => Then the line numbers must not be updated!


    # Now check how we fill the callbacks
    adapt_line_numbers_by_offset = 0
    """
    # Add a testcase at the start
    (prefix_content, prefix_state) = get_random_testcase_for_insertion_point_in_template()
    adapt_line_numbers_by_offset = len(prefix_content.split("\n"))
    (final_testcase, final_testcase_state) = merge_testcase_append(prefix_content, prefix_state, final_testcase, final_testcase_state)
    insertion_point_lines.pop(0)    # should pop line number 0

    print("Next template is3: %s" % final_testcase_state.testcase_filename)

    # Add a testcase at the end
    (suffix_content, suffix_state) = get_random_testcase_for_insertion_point_in_template()
    (final_testcase, final_testcase_state) = merge_testcase_append(final_testcase, final_testcase_state, suffix_content, suffix_state)
    insertion_point_lines.pop()    # should pop last line number

    print("Next template is4: %s" % final_testcase_state.testcase_filename)
    """

    # If I have a lot of injection points (e.g. callback locations) I would very likely
    # get a high exception rate because my fuzzer would add a lot of code (at least 1 code line
    # at every callback location. To prevent this, I sometimes don't add code at a callback
    # The likelihood depends on the number of callbacks, e.g. if I just have 2 callbacks then
    # I will always add code there. If I have 60 callback locations, then I would 95% of the time
    # don't add code 

    # Example:
    # Let's say I have 30 insertion points and I want that approx. 3 of them are used
    # and the other 27 are not filled in one fuzzing iteration
    # That would be the following math formula:
    # (30 / 100) * (100 - X) = 3
    # 
    # I divide 30 by 100% and then multiple by the likelihood that it should occur
    # since the below code stores the "do nothing" likelihood I have to calculate "100% - X%"
    # The result should be 3
    # For example, doing 90% of the time "nothing" would solve the above formula and therefore
    # >do_nothing_at_insertion_point_probability< should be set to 0.9 (=90%)
    # Let's change the formula to calculate X (which is >do_nothing_at_insertion_point_probability<)
    # X = 100 - (3 / (<number_insertion_points> / 100))
    # Let's simplify the formula:
    # X = 100 - (3 * 100 / <number_insertion_points>)
    # The output of the above formula is in % but I want a number between 0 and 1, so divide both sides by 100
    # =>
    # X = 1 - (3/<number_insertion_points>)
    # And now make 3 configurable and replace it by cfg.template_number_insertion_points_to_use
    # =>
    # X  = 1 - (cfg.template_number_insertion_points_to_use / <number_insertion_points>)
    # Other example:
    # 
    number_insertion_points = len(insertion_point_lines)

    do_nothing_at_insertion_point_probability = 1.0 - (cfg.template_number_insertion_points_to_use / number_insertion_points)
    if do_nothing_at_insertion_point_probability < 0:
        do_nothing_at_insertion_point_probability = 0.0    # likelihood can't be negative
    """
    if number_insertion_points > 30:
        do_nothing_at_insertion_point_probability = 0.9
    if number_insertion_points > 20:
        do_nothing_at_insertion_point_probability = 0.6
    elif number_insertion_points > 10:
        do_nothing_at_insertion_point_probability = 0.3
    elif number_insertion_points > 5:
        do_nothing_at_insertion_point_probability = 0.1
    else:    # number_insertion_points <= 5
        do_nothing_at_insertion_point_probability = 0.0
    """

    # Select some random insertion points which I want to use in this fuzzing iteration
    number_insertion_points = len(insertion_point_lines)
    number_insertion_points_to_inject = round(number_insertion_points * (1.0 - do_nothing_at_insertion_point_probability))
    if number_insertion_points_to_inject == 0:
        number_insertion_points_to_inject = 1    # always inject at least at one insertion point
    insertion_point_lines_to_inject = []
    if number_insertion_points_to_inject == number_insertion_points:
        # use all insertion points, so just use the full list
        insertion_point_lines_to_inject = insertion_point_lines
    else:
        # just use a subset of it
        for tmp_idx in range(number_insertion_points_to_inject):
            selected_insertion_point = utils.get_random_entry(insertion_point_lines)
            insertion_point_lines.remove(selected_insertion_point)    # remove it so it can't be taken again in next iteration
            insertion_point_lines_to_inject.append(selected_insertion_point)

    # I need to sort the list to ensure that >adapt_line_numbers_by_offset< is calculated correctly below
    insertion_point_lines_to_inject.sort()


    for insertion_line in insertion_point_lines_to_inject:
        insertion_line_fixed = insertion_line + adapt_line_numbers_by_offset
        # print("Insertion line: %d" % insertion_line_fixed)
        # Old Code (now replaced with the above one:)
        # if utils.likely(do_nothing_at_insertion_point_probability):
        #    continue    # do nothing; Can be required in huge templates with many insertion points. Otherwise the testcase can become so huge that processing would take too long
        # utils.msg("[i] Going to modify insertion point in line %d" % insertion_line_fixed)

        # adapt_line_numbers_by_offset += 1    # always one line gets added
        # (final_testcase, final_testcase_state) = mutation_insert_random_operation_at_specific_line(final_testcase, final_testcase_state, insertion_line_fixed)
        
        already_inserted_operation = False
        if utils.likely(cfg.likelihood_template_insert_array_operation):
            (tmp_final_testcase, tmp_final_testcase_state) = testcase_mutator.insert_random_array_operation_at_specific_line(final_testcase, final_testcase_state, insertion_line_fixed)
            if tmp_final_testcase is None:
                # No insertion was performed, most likely because there were no arrays available
                already_inserted_operation = False    # just do nothing and use one of the below insertion methods
            else:
                # Insertion worked
                already_inserted_operation = True
                adapt_line_numbers_by_offset += 1    # always one line gets added
                final_testcase = tmp_final_testcase
                final_testcase_state = tmp_final_testcase_state

        if already_inserted_operation is False:
            # not inserted yet, so check some other methods:

            if utils.likely(cfg.likelihood_template_insert_operation_from_database):
                # Take operation from database
                
                # Calculation of lines before and after is in-performant and it's just a quick hotfix
                # TODO: Calculate it correctly by returning the number of new lines with
                # >mutation_insert_random_operation_from_database_at_specific_line<
                number_lines_before = len(final_testcase.split("\n"))
                (final_testcase, final_testcase_state) = mutation_insert_random_operation_from_database_at_specific_line(final_testcase,
                                                                                                                         final_testcase_state,
                                                                                                                         insertion_line_fixed,
                                                                                                                         number_of_operations=1)
                number_lines_after = len(final_testcase.split("\n"))
                adapt_line_numbers_by_offset += (number_lines_after - number_lines_before)

            else:
                # Take operation by adding some random code
                adapt_line_numbers_by_offset += 1    # always one line gets added
                (final_testcase, final_testcase_state) = mutation_insert_random_operation_at_specific_line(final_testcase,
                                                                                                           final_testcase_state,
                                                                                                           insertion_line_fixed)
            

        # Code below is old code and can maybe be removed:
        # insertion of a full testcase at an "insertion point" is not a good idea, I'm now using instead operations from the database!
        """
        if utils.likely(0.5):
            # Perform a state modification operation
            #print("State modification at line: %d" % insertion_line_fixed)

            adapt_line_numbers_by_offset += 1    # always one line gets added
            (final_testcase, final_testcase_state) = mutation_insert_random_operation_at_specific_line(final_testcase, final_testcase_state, insertion_line_fixed)
        else:
            # insert a new testcase
            (new_testcase_content, new_testcase_state) = get_random_testcase_for_insertion_point_in_template()
            adapt_line_numbers_by_offset += len(new_testcase_content.split("\n"))
            (final_testcase, final_testcase_state) = merge_testcase2_into_testcase1_at_line(final_testcase, final_testcase_state, new_testcase_content, new_testcase_state, insertion_line_fixed)
            #print("Added testcase was:")
            #print(new_testcase_content)
            #print("-------------------")
        """

    # print("AFTER:")
    # utils.print_code_with_line_numbers(final_testcase)
    # print(final_testcase_state)
    # print("STOP")
    # sys.exit(-1)
    return final_testcase, final_testcase_state


# TODO: Move this mode into the modes directory
def start_test_mode():
    utils.msg("[i] Test Mode was started...")

    # In the statistics mainly the "success rate" should be checked!
    # E.g. "new coverage" can be wrong because I don't reset the coverage map after testing a mutation
    testcase_mutator.mutation_operations.insert(0, mutation_do_nothing)    # add a mutation which does nothing to get a baseline

    # Test Mutations
    utils.msg("[i] Going to test mutations...")
    for mutation_function in testcase_mutator.mutation_operations:
        utils.msg("[i] Testing mutation: %s" % mutation_function.__name__)

        for i in range(cfg.test_mode_number_iterations):
            (filename, final_testcase, final_testcase_state) = cfg.corpus_js_snippets.get_random_testcase(runtime_adjustment_factor=cfg.adjustment_factor_code_snippet_corpus)
            original_state = final_testcase_state
            final_testcase_state = final_testcase_state.deep_copy()
            (final_testcase, final_testcase_state) = mutation_function(final_testcase, final_testcase_state)
            perform_execution(final_testcase, final_testcase_state)


        # TODO: I think I now need to pass forcefully_dump_everything=True to update_stats() now to show them?
        cfg.my_status_screen.update_stats()    # prints final statistics of the mutation strategy
        cfg.my_status_screen.reset_stats()


    # Test Merging
    # TODO Implement

    # Test Template
    # TODO Implement

    utils.exit_and_msg("Finished, stopping..")


def adjust_testcase_runtimes():
    # Since I calculated state files on different machines (e.g. local machines on different computers, AWS cloud, Azure cloud, ..)
    # the runtime in the .state files can be wrong (or adjusted to another computer)
    # I therefore execute here some random testcases and compare the runtime to get an "adjustment-factor"

    utils.msg("[i] Starting to adjust runtime")

    if cfg.enable_dynamic_runtime_adjustment is False:
        cfg.adjustment_factor_code_snippet_corpus = 1
        cfg.adjustment_factor_template_files_self_created_files = 1
        cfg.adjustment_factor_template_files_injected_callbacks = 1
        utils.msg("[i] Dynamic runtime adjustment is disabled, using default adjustment factor of 1")
        return
    
    # Step 1: Code snippet corpus
    adjustment_factor_list = []
    for x in range(cfg.adjust_runtime_executions):
        (filename, content, state) = cfg.corpus_js_snippets.get_random_testcase(runtime_adjustment_factor=None)
        expected_runtime = state.runtime_length_in_ms
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        if result.status != Execution_Status.SUCCESS:
            utils.msg("[-] Problem, initial testcase in adjust_testcase_runtimes() didn't execute successful! (code snippet: %s)" % filename)
            continue
        real_runtime = result.exec_time
        calculated_factor = float(real_runtime) / float(expected_runtime)
        adjustment_factor_list.append(calculated_factor)
    adjustment_factor_list.sort()

    for x in range(cfg.adjust_runtime_remove_first_and_last_number_of_entries):
        adjustment_factor_list.pop()
        adjustment_factor_list.pop(0)
    cfg.adjustment_factor_code_snippet_corpus = sum(adjustment_factor_list) / len(adjustment_factor_list)
    utils.msg("[i] Adjustment factor for code snippet corpus is: %.4f" % cfg.adjustment_factor_code_snippet_corpus)

    # Testing if the factor is correct:
    """
    diff_total = 0.0
    for x in range(20):
        (filename, content, state) = cfg.corpus_js_snippets.get_random_testcase(runtime_adjustment_factor=None)
        expected_runtime = state.runtime_length_in_ms * cfg.adjustment_factor_code_snippet_corpus
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        print("Expected: %.2f , Real: %.2f" % (expected_runtime, result.exec_time))
        diff = expected_runtime - result.exec_time    # can also become negative
        diff_total += diff
    print("Total diff: %.2f" % diff_total)
    """
    if cfg.fuzzer_arguments.import_corpus_mode or cfg.fuzzer_arguments.minimize_corpus_mode:
        return    # skip template corpus

    # Step 2: Template corpus: self created files
    adjustment_factor_list = []
    for x in range(cfg.adjust_runtime_executions):
        (filename, content, state) = cfg.corpus_template_files.get_random_testcase_self_created(runtime_adjustment_factor_self_created=None)
        expected_runtime = state.runtime_length_in_ms
        content = content.replace(cfg.v8_print_js_codeline, "1")    # writing to pipe can take long and will not be done during fuzzing!
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        if result.status != Execution_Status.SUCCESS:
            utils.msg("[-] Problem, initial testcase in adjust_testcase_runtimes() didn't execute successful! (templates self: %s)" % filename)
            continue
        real_runtime = result.exec_time
        calculated_factor = float(real_runtime) / float(expected_runtime)
        adjustment_factor_list.append(calculated_factor)
    adjustment_factor_list.sort()

    for x in range(cfg.adjust_runtime_remove_first_and_last_number_of_entries):
        adjustment_factor_list.pop()
        adjustment_factor_list.pop(0)
    cfg.adjustment_factor_template_files_self_created_files = sum(adjustment_factor_list) / len(adjustment_factor_list)
    utils.msg("[i] Adjustment factor for template corpus (self created) is: %.4f" % cfg.adjustment_factor_template_files_self_created_files)

    # Step 3: Template corpus: injected callback
    adjustment_factor_list = []
    for x in range(cfg.adjust_runtime_executions):
        (filename, content, state) = cfg.corpus_template_files.get_random_testcase_callback_injected(runtime_adjustment_factor_injected_callbacks=None)
        expected_runtime = state.runtime_length_in_ms
        content = content.replace(cfg.v8_print_js_codeline, "1")    # writing to pipe can take long and will not be done during fuzzing!
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        if result.status != Execution_Status.SUCCESS:
            utils.msg("[-] Problem, initial testcase in adjust_testcase_runtimes() didn't execute successful! (templates injected: %s" % filename)
            continue
        real_runtime = result.exec_time
        calculated_factor = float(real_runtime) / float(expected_runtime)
        adjustment_factor_list.append(calculated_factor)
    adjustment_factor_list.sort()

    for x in range(cfg.adjust_runtime_remove_first_and_last_number_of_entries):
        adjustment_factor_list.pop()
        adjustment_factor_list.pop(0)
    cfg.adjustment_factor_template_files_injected_callbacks = sum(adjustment_factor_list) / len(adjustment_factor_list)
    utils.msg("[i] Adjustment factor for template corpus (callback injected) is: %.4f" % cfg.adjustment_factor_template_files_injected_callbacks)

    # TODO check if the adjustment factor is approximately correct, if not, recalculate it
    # e.g. a value of 20 would be completely off or a value of 0.001
    # Note: Currently the adjustment factor can be 3-5 because I calculated corpus with a partially instrumented v8 version
    # The current version is fully instrumented which is slower


def deterministically_preprocess_queue():
    prev_operation = cfg.my_status_screen.get_current_operation()
    cfg.my_status_screen.set_current_operation("Preprocessing")
    deterministic_preprocessing.process_preprocessing_queue()
    cfg.my_status_screen.set_current_operation(prev_operation)


# If you manually call this function make sure to update the coverage afterwards!
def sync_new_file(content, state, required_coverage):
    if "new Worker" in content:
        return False    # skip workers

    cfg.exec_engine.restart_engine()        # Restart the engine so that every testcase to import starts in a new v8 process
    for i in range(0, 3):    # try 3 times to execute the new testcase and check if it leads to new coverage
        result = cfg.exec_engine.execute_safe(content, custom_timeout=cfg.v8_timeout_per_execution_in_ms_max)
        if result.status == Execution_Status.SUCCESS and result.num_new_edges > 0:
            # it really resulted in new behavior => so import it to the current corpus
            utils.msg("[+] Synced a file from another fuzzer to current corpus with %d new edges" % result.num_new_edges)
            cfg.corpus_js_snippets.add_new_testcase_to_corpus(content, state, required_coverage, 1)  # 1 because the factor would already be added from the other instance
            return True

    return False


def sync_import_new_files_from_folder(folder_path):
    number_files_processed = 0
    number_files_new_coverage = 0
    
    for filename_to_import in os.listdir(folder_path):
        if filename_to_import.endswith(".js"): 
            input_file_to_import = os.path.join(folder_path, filename_to_import)
            with open(input_file_to_import, "r") as fobj:
                content = fobj.read()

            state = testcase_state.load_state(input_file_to_import + ".pickle")
            
            required_coverage_filepath = input_file_to_import[:-3] + "_required_coverage.pickle"
            with open(required_coverage_filepath, 'rb') as finput:
                required_coverage = pickle.load(finput)

            new_coverage = sync_new_file(content, state, required_coverage)
            number_files_processed += 1
            if new_coverage:
                number_files_new_coverage += 1
            utils.msg("[+] Handled %d files (%d new coverage)" % (number_files_processed, number_files_new_coverage))

    cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
    cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_previous_coverage_map_file)


def sync_import_new_files_from_other_fuzzers():
    global last_sync_time

    if cfg.fuzzer_arguments.disable_coverage:
        return    # if coverage is disabled, then the fuzzer can't download files from the bucket because other fuzzers can't find new corpus files

    number_really_new_coverage_files = 0

    should_sync = False
    if last_sync_time == 0:
        should_sync = True    # not synced yet
    else:
        time_diff = datetime.datetime.now().replace(microsecond=0) - last_sync_time
        if time_diff.total_seconds() > cfg.sync_after_X_seconds:
            should_sync = True
    
    if should_sync:
        # Start a new sync process
        new_files = gce_bucket_sync.download_new_corpus_files()
        for entry in new_files:
            (new_file_content, new_file_state_content, required_coverage_content) = entry
            with open(cfg.tmp_file_to_import_states, "wb") as fobj:
                fobj.write(new_file_state_content)
            new_file_state = testcase_state.load_state(cfg.tmp_file_to_import_states)

            with open(cfg.tmp_file_to_import_states, "wb") as fobj:
                fobj.write(required_coverage_content)
            with open(cfg.tmp_file_to_import_states, 'rb') as finput:
                required_coverage = pickle.load(finput)

            new_coverage = sync_new_file(new_file_content, new_file_state, required_coverage)
            if new_coverage:
                number_really_new_coverage_files += 1

        utils.msg("[+] Finished syncing %d files from other fuzzers to the local corpus (resulted in %d new corpus files)" % (
            len(new_files),
            number_really_new_coverage_files))

        last_sync_time = datetime.datetime.now().replace(microsecond=0)
        tagging.clear_current_tags()
        cfg.my_status_screen.add_new_synced_files(len(new_files), number_really_new_coverage_files)

        if number_really_new_coverage_files > 0:
            # TODO update coverage map
            cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_final_coverage_map_file)
            cfg.exec_engine.save_global_coverage_map_in_file(cfg.output_path_previous_coverage_map_file)
            cfg.my_status_screen.update_last_new_coverage_time()


def configure_all_filesystem_paths():
    # Create the required folder structure in the output directory
    cfg.output_dir = cfg.fuzzer_arguments.output_dir
    cfg.output_dir_current_corpus = os.path.join(cfg.output_dir, cfg.current_corpus_dir)
    cfg.output_dir_new_files = os.path.join(cfg.output_dir, cfg.new_files_dir)
    cfg.output_dir_crashes = os.path.join(cfg.output_dir, cfg.crash_dir)
    cfg.output_dir_crashes_exception = os.path.join(cfg.output_dir, cfg.crash_exception_dir)

    # Set the correct database paths
    cfg.databases_dir = os.path.join(cfg.output_dir, cfg.databases_dir)
    cfg.pickle_database_path_strings = os.path.join(cfg.databases_dir, cfg.pickle_database_path_strings)
    cfg.pickle_database_path_numbers = os.path.join(cfg.databases_dir, cfg.pickle_database_path_numbers)
    cfg.pickle_database_globals = os.path.join(cfg.databases_dir, cfg.pickle_database_globals)

    cfg.pickle_database_generic_operations = os.path.join(cfg.databases_dir, cfg.pickle_database_generic_operations)
    cfg.pickle_database_variable_operations = os.path.join(cfg.databases_dir, cfg.pickle_database_variable_operations)
    cfg.pickle_database_variable_operations_others = os.path.join(cfg.databases_dir, cfg.pickle_database_variable_operations_others)
    cfg.pickle_database_variable_operations_list = os.path.join(cfg.databases_dir, cfg.pickle_database_variable_operations_list)
    cfg.pickle_database_variable_operations_states_list = os.path.join(cfg.databases_dir, cfg.pickle_database_variable_operations_states_list)

    cfg.output_path_final_coverage_map_file = os.path.abspath(os.path.join(cfg.output_dir, cfg.final_coverage_map_file))
    cfg.output_path_previous_coverage_map_file = os.path.abspath(os.path.join(cfg.output_dir, cfg.previous_coverage_map_file))

    current_unixtimestamp = int(time.time())
    cfg.tagging_filename = cfg.tagging_filename_template % (current_unixtimestamp, cfg.fuzzer_arguments.seed)

    cfg.output_dir_tagging_results_file = os.path.join(cfg.output_dir, cfg.tagging_filename)
    cfg.status_result_filename = cfg.status_filename_template % (current_unixtimestamp, cfg.fuzzer_arguments.seed)
    cfg.output_dir_status_result_file = os.path.join(cfg.output_dir, cfg.status_result_filename)

    cfg.logfile_filename = cfg.logfile_filename_template % (current_unixtimestamp, cfg.fuzzer_arguments.seed)
    cfg.logfile_filepath = os.path.join(cfg.output_dir, cfg.logfile_filename)


    # Configure in config/cfg all paths which depend on the output dir:
    cfg.permanently_disabled_files_file = os.path.join(cfg.output_dir, cfg.permanently_disabled_files_file)
    cfg.coverage_map_minimizer_filename = os.path.join(cfg.output_dir, cfg.coverage_map_minimizer_filename)
    cfg.coverage_map_corpus_minimizer = os.path.join(cfg.output_dir, cfg.coverage_map_corpus_minimizer)
    cfg.coverage_map_testsuite = os.path.join(cfg.output_dir, cfg.coverage_map_testsuite)
    cfg.synchronization_already_imported_files_filepath = os.path.join(cfg.output_dir, cfg.synchronization_already_imported_files_filepath)
    cfg.tmp_file_to_import_states = os.path.join(cfg.output_dir, cfg.tmp_file_to_import_states)

    if cfg.fuzzer_arguments.resume is False:
        # Create the output dirs if they don't exist yet
        utils.make_dir_if_not_exists(cfg.output_dir_current_corpus)
        utils.make_dir_if_not_exists(cfg.output_dir_new_files)
        utils.make_dir_if_not_exists(cfg.output_dir_crashes)
        utils.make_dir_if_not_exists(cfg.output_dir_crashes_exception)
        utils.make_dir_if_not_exists(cfg.databases_dir)


    utils.msg("[i] Log filepath will be: %s" % cfg.logfile_filepath)
    utils.msg("[i] Status filepath will be: %s" % cfg.output_dir_status_result_file)
    utils.msg("[i] Tagging filepath will be: %s" % cfg.output_dir_tagging_results_file)
    utils.msg("[i] Synchronization of already imported files filepath will be: %s" % cfg.synchronization_already_imported_files_filepath)


def import_testcases_if_first_fuzzer_invocation():
    if cfg.fuzzer_arguments.resume is False:
        if cfg.fuzzer_arguments.corpus_js_files_dir is not None:
            import_corpus_mode(os.path.abspath(cfg.fuzzer_arguments.corpus_js_files_dir))
            utils.exit_and_msg("[+] Finished creation of the initial corpus! You can now start fuzzing by executing the script with the --resume option!")
        elif cfg.fuzzer_arguments.upgrade_corpus_to_new_js_engine is not None:
            upgrade_corpus_to_new_js_engine_mode()
            utils.exit_and_msg("[+] Finished upgrading the JS corpus to a new JS engine! You can now start fuzzing by executing the script with the --resume option!")
        else:
            utils.perror("[-] Unkown mode?")


def start_possible_early_modes():
    if cfg.fuzzer_arguments.developer_mode:
        start_developer_mode()
        utils.exit_and_msg("[+] Finished Developer Mode, stopping now...")
    elif cfg.fuzzer_arguments.recalculate_coverage_map_mode:
        recalculate_coverage_map()
        utils.exit_and_msg("[+] Finished recalculation of coverage map, stopping now...")
    elif cfg.fuzzer_arguments.fix_corpus_mode:
        fix_corpus()
        utils.exit_and_msg("[+] Finished fix corpus mode, stopping now...")
    elif cfg.fuzzer_arguments.recalculate_testcase_runtimes_mode:
        recalculate_testcase_runtimes()
        utils.exit_and_msg("[+] Finished recalculation of testcase runtimes, stopping now...")
    elif cfg.fuzzer_arguments.recalculate_state is not None:
        recalculate_state(recalculate_state_for_file=cfg.fuzzer_arguments.recalculate_state)
        utils.exit_and_msg("[+] Finished Recalculate Testcase State Mode, stopping now...")
    elif cfg.fuzzer_arguments.check_corpus_mode:
        check_corpus()
        utils.exit_and_msg("[+] Finished Check Corpus Mode, stopping now...")


def start_possible_late_modes():
    if cfg.fuzzer_arguments.import_corpus_mode:
        # Check if the import corpus mode was started
        # Note: It's important that this code is executed here and not before the corpus files are loaded
        # => It's required that they are loaded because adjust_testcase_runtimes() must be called first to store runtime
        # information correct in the newly generated .state files!
        total_number_files_to_import = import_corpus_mode(os.path.abspath(cfg.fuzzer_arguments.import_corpus_mode))
        utils.exit_and_msg("[+] Finished importing %d new files. Stopping now..." % total_number_files_to_import)
    elif cfg.fuzzer_arguments.import_corpus_precalculated_files_mode:
        sync_import_new_files_from_folder(folder_path=cfg.fuzzer_arguments.import_corpus_precalculated_files_mode)
        utils.exit_and_msg("[+] Finished importing files, stopping now...")
    elif cfg.fuzzer_arguments.test_mode:
        start_test_mode()
        utils.exit_and_msg("[+] Finished Test Mode, stopping now...")
    elif cfg.fuzzer_arguments.minimize_corpus_mode:
        minimize_corpus()
        utils.exit_and_msg("[+] Finished Minimize Corpus Mode, stopping now...")
    elif cfg.fuzzer_arguments.find_problematic_corpus_files_mode:
        find_problematic_corpus_files()
        utils.exit_and_msg("[+] Finished Find problematic Corpus Files Mode, stopping now...")
    elif cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id is not None:
        deterministically_preprocess_queue()
        utils.exit_and_msg("[+] Finished deterministically preprocessing all queue files! Stopping now...")
    elif cfg.fuzzer_arguments.testsuite is not None:
        execute_testsuite(cfg.fuzzer_arguments.testsuite)
        utils.exit_and_msg("[+] Finished testsuite, going to stop now...")
    elif cfg.fuzzer_arguments.extract_data is not None:
        if cfg.fuzzer_arguments.extract_data == "numbers_and_strings":
            extract_numbers_and_strings.create_database()
        elif cfg.fuzzer_arguments.extract_data == "operations":
            extract_operations.create_database()
            pass    # TODO
        else:
            utils.perror("Wrong --extract_data argument!")  # should not occur because it should already be handled earlier

        utils.exit_and_msg("[+] Finished extract data mode, going to stop now...")


if __name__ == '__main__':
    main()
