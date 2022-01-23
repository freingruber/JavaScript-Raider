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
import datetime
import config as cfg
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import sync_engine.gce_bucket_sync as gce_bucket_sync
import sys


class Status_Screen:
    def __init__(self):
        self.number_fuzzing_executions = 0
        self.stats_success = 0
        self.stats_crash = 0
        self.stats_exception_crash = 0
        self.stats_exception = 0
        self.stats_timeout = 0
        self.stats_new_behavior = 0
        self.start_time = datetime.datetime.now().replace(microsecond=0)
        self.start_time_str = self.start_time.strftime(cfg.status_update_time_format)
        self.last_crash_time = None
        self.last_crash_time_str = cfg.status_update_time_not_set
        self.last_crash_exception_time = None
        self.last_crash_exception_time_str = cfg.status_update_time_not_set
        self.last_new_coverage_time = None
        self.last_new_coverage_time_str = cfg.status_update_time_not_set

        # The fuzzer prints in the stats the average expected runtime
        # and the average real runtime
        # => These stats can be used to set correct max/min runtime values
        # and can be used to detect if the runtime is correctly guessed
        # Let's assume the expected runtimes were 5 , 7 and 5
        # Then "_total_sum" would hold 5+7+5 = 17
        # And "_number_values" would be 3 because there were 3 values (5,7 and 5)
        # The average would therefore be "total_sum" / "number_values" = 17/3 = 5.6
        self.expected_runtime_total_sum = 0
        self.expected_runtime_number_values = 0
        self.real_runtime_total_sum = 0
        self.real_runtime_number_values = 0
        self.measure_mode_print_iterations = 0
        self.current_operation = "Initialization"  # used in the status_update() to show which operations are currently performed
        self.number_files_synced_from_other_fuzzers = 0  # count number of files downloaded from bucket
        self.number_files_synced_from_other_fuzzers_real_new_behavior = 0  # just count the number of files downloaded from bucket which really resulted in new behavior
        self.total_passed_seconds_in_last_status_update = 0
        self.total_executions_in_last_status_update = 0
        self.initial_coverage_triggered_edges = 0
        self.initial_coverage_percent = 0.0


    def add_expected_runtime_total_sum(self, value_to_add):
        self.expected_runtime_total_sum += value_to_add
        self.expected_runtime_number_values += 1

    def add_real_runtime_total_sum(self, value_to_add):
        self.real_runtime_total_sum += value_to_add
        self.real_runtime_number_values += 1

    def update_last_new_coverage_time(self):
        (self.last_new_coverage_time, self.last_new_coverage_time_str) = _get_current_time()

    def update_last_crash_exception_time(self):
        (self.last_crash_exception_time, self.last_crash_exception_time_str) = _get_current_time()

    def update_last_crash_time(self):
        (self.last_crash_time, self.last_crash_time_str) = _get_current_time()


    def set_initial_coverage(self, initial_coverage_triggered_edges, initial_coverage_percent):
        self.initial_coverage_triggered_edges = initial_coverage_triggered_edges
        self.initial_coverage_percent = initial_coverage_percent

    def get_initial_coverage_triggered_edges(self):
        return self.initial_coverage_triggered_edges

    def get_initial_coverage_percent(self):
        return self.initial_coverage_percent

    def add_new_synced_files(self, number_new_files_synced_from_other_fuzzers, number_new_files_synced_from_other_fuzzers_real_new_behavior):
        self.number_files_synced_from_other_fuzzers += number_new_files_synced_from_other_fuzzers
        self.number_files_synced_from_other_fuzzers_real_new_behavior += number_new_files_synced_from_other_fuzzers_real_new_behavior


    def set_current_operation(self, new_current_operation):
        self.current_operation = new_current_operation

    def get_current_operation(self):
        return self.current_operation

    def signal_handler(self, sig, frame):
        utils.msg("[i] Ctrl+c was pressed! Going to save results...")
        self.update_stats(forcefully_dump_everything=True)
        utils.msg("[i] Stopping...")
        sys.exit(0)

    def inc_number_fuzzing_executions(self):
        self.number_fuzzing_executions += 1

    def inc_stats_success(self):
        self.stats_success += 1

    def inc_stats_crash(self):
        self.stats_crash += 1

    def inc_stats_exception_crash(self):
        self.stats_exception_crash += 1


    def inc_stats_exception(self):
        self.stats_exception += 1

    def inc_stats_timeout(self):
        self.stats_timeout += 1

    def inc_stats_new_behavior(self):
        self.stats_new_behavior += 1

    def get_stats_new_behavior(self):
        return self.stats_new_behavior

    # This function is called after every execution.
    # After X executions (defined by cfg.status_update_after_x_executions),
    # the current stats will be displayed via the status screen
    def update_stats(self, forcefully_dump_everything=False):
        if cfg.fuzzer_arguments.skip_executions:
            # In this case I don't have an execution engine, so use the fuzzing executions as source
            number_executions = self.number_fuzzing_executions
        else:
            # DEFAULT MODE: Query it from the execution engine
            number_executions = cfg.exec_engine.get_total_number_executions()

        if (number_executions % cfg.invoke_check_to_disable_testcases_all_X_executions) == 0:
            # check if some testcases can be disabled (because fuzzing them would be inefficient)
            cfg.corpus_js_snippets.check_if_testcases_should_be_disabled()

        dumped_tags = False
        if forcefully_dump_everything or (number_executions % cfg.dump_tags_after_x_executions) == 0:
            tagging.dump_current_tagging_results(cfg.output_dir_tagging_results_file)
            dumped_tags = True

        if forcefully_dump_everything or dumped_tags or cfg.fuzzer_arguments.test_mode or \
                (number_executions % cfg.status_update_after_x_executions) == 0:
            now = datetime.datetime.now().replace(microsecond=0)
            now_str = now.strftime(cfg.status_update_time_format)
            runtime = (now - self.start_time)
            total_passed_seconds = runtime.total_seconds()
            if total_passed_seconds == 0:
                total_passed_seconds = 1  # fix to avoid division by zero (in very fast execution speeds)
            runtime_str = utils.covert_runtime_to_string(total_passed_seconds)

            exec_speed = float(number_executions) / float(total_passed_seconds)
            if self.stats_success != 0:
                success_rate = 100.0 / (float(self.number_fuzzing_executions) / self.stats_success)
            else:
                success_rate = 0.0
            if self.stats_timeout != 0:
                timeout_rate = 100.0 / (float(self.number_fuzzing_executions) / self.stats_timeout)
            else:
                timeout_rate = 0.0
            if self.stats_exception != 0:
                exception_rate = 100.0 / (float(self.number_fuzzing_executions) / self.stats_exception)
            else:
                exception_rate = 0.0

            number_triggered_edges, total_number_possible_edges = cfg.exec_engine.get_number_triggered_edges()
            if total_number_possible_edges == 0:
                total_number_possible_edges = 1
            triggered_edges_in_percent = (100 * number_triggered_edges) / float(total_number_possible_edges)

            average_expected_runtime = float(self.expected_runtime_total_sum) / self.expected_runtime_number_values
            average_real_runtime = float(self.real_runtime_total_sum) / self.real_runtime_number_values

            # Get stats from corpus
            (current_corpus_size, stats_real_new_behavior, last_newly_added_testcase_time,
             last_newly_added_testcase_time_str, number_disabled_files) = cfg.corpus_js_snippets.get_stats()

            last_new_coverage_time_str_diff = ""
            last_crash_time_str_diff = ""
            last_crash_exception_time_str_diff = ""
            last_newly_added_testcase_time_str_diff = ""
            if self.last_new_coverage_time is not None:
                last_new_coverage_time_str_diff = " (" + utils.covert_runtime_to_string((now - self.last_new_coverage_time).total_seconds()) + " ago)"
            if self.last_crash_time is not None:
                last_crash_time_str_diff = " (" + utils.covert_runtime_to_string((now - self.last_crash_time).total_seconds()) + " ago)"
            if self.last_crash_exception_time is not None:
                last_crash_exception_time_str_diff = " (" + utils.covert_runtime_to_string((now - self.last_crash_exception_time).total_seconds()) + " ago)"
            if last_newly_added_testcase_time is not None:
                last_newly_added_testcase_time_str_diff = " (" + utils.covert_runtime_to_string((now - last_newly_added_testcase_time).total_seconds()) + " ago)"

            total_passed_seconds_in_v8_engine = cfg.exec_engine.get_total_testcases_execution_time()  # time spent executing testcases
            fuzzer_overhead_percent = 0.0
            if total_passed_seconds_in_v8_engine != 0:
                total_passed_seconds_just_in_fuzzer = total_passed_seconds - total_passed_seconds_in_v8_engine
                fuzzer_overhead_percent = (total_passed_seconds_just_in_fuzzer / float(total_passed_seconds_in_v8_engine)) * 100.0

            # Calculate current exec speed:
            if self.total_passed_seconds_in_last_status_update == 0 or self.total_executions_in_last_status_update == 0:
                current_exec_speed = exec_speed  # Can't calculate it right now because there is no previous data
            else:
                passed_seconds_since_last_status_update = total_passed_seconds - self.total_passed_seconds_in_last_status_update
                number_executions_since_last_status_update = number_executions - self.total_executions_in_last_status_update
                if passed_seconds_since_last_status_update <= 0:
                    passed_seconds_since_last_status_update = 1  # avoid division by zero
                current_exec_speed = float(number_executions_since_last_status_update) / float(passed_seconds_since_last_status_update)
            # Now Update the fields for the next status update
            self.total_passed_seconds_in_last_status_update = total_passed_seconds
            self.total_executions_in_last_status_update = number_executions

            # Create the status string
            output = ""
            output += "\n" + "#" * 95 + "\n"
            output += "\n\n" + "#" * 32 + " JS Raider by @ReneFreingruber " + "#" * 32 + "\n"
            output += "\n" + "#" * 95 + "\n"
            output += "Current operation: %s\n" % self.current_operation
            output += "Speed: %.2f execs / sec (total executions: %d ; total fuzzing executions: %d ; passed seconds: %d)\n" % (
                exec_speed,
                number_executions,
                self.number_fuzzing_executions,
                total_passed_seconds)
            output += "Speed since last status update: %.2f execs / sec\n" % current_exec_speed
            output += "Current coverage: %.4f %% (%d edges)\n" % (triggered_edges_in_percent, number_triggered_edges)
            output += "Initial coverage: %.4f %% (%d edges)\n" % (self.initial_coverage_percent, self.initial_coverage_triggered_edges)
            output += "Current corpus size: %d files (and %d disabled files)\n" % (current_corpus_size, number_disabled_files)
            output += "New behavior: %d files\n" % self.stats_new_behavior

            # files which resulted after several executions again in new coverage and which were therefore imported to the corpus
            output += "New real behavior: %d files\n" % stats_real_new_behavior

            output += "Crashes: %d files\n" % self.stats_crash
            output += "Exception crashes: %d files\n" % self.stats_exception_crash
            output += "Success: %d files (success rate: %.2f %%)\n" % (self.stats_success, success_rate)
            output += "Exceptions: %d files (exception rate: %.2f %%)\n" % (self.stats_exception, exception_rate)
            output += "Timeouts: %d files (timeout rate: %.2f %%)\n" % (self.stats_timeout, timeout_rate)
            output += "Engine restarts: %d\n" % cfg.exec_engine.get_number_engine_restarts()
            output += "Occurred problems: %d\n" % utils.number_of_occurred_problems
            output += "Synchronized files: %d\n" % self.number_files_synced_from_other_fuzzers
            output += "Synchronized files with new behavior: %d\n" % self.number_files_synced_from_other_fuzzers_real_new_behavior
            output += "Average testcase runtime real: %.2f ms\n" % average_real_runtime
            output += "Average testcase runtime expected: %.2f ms\n" % average_expected_runtime
            output += "Total runtime: %s\n" % runtime_str
            output += "Started: %s\n" % self.start_time_str
            output += "Current time: %s\n" % now_str
            output += "Last new coverage: %s%s\n" % (self.last_new_coverage_time_str, last_new_coverage_time_str_diff)
            output += "Last real new coverage: %s%s\n" % (last_newly_added_testcase_time_str, last_newly_added_testcase_time_str_diff)
            output += "Last crash: %s%s\n" % (self.last_crash_time_str, last_crash_time_str_diff)
            output += "Last exception crash: %s%s\n" % (self.last_crash_exception_time_str, last_crash_exception_time_str_diff)

            # Debugging code:
            if total_passed_seconds_in_v8_engine != 0:
                # just print if I measure the overhead
                output += "Fuzzer overhead: %.4f %%\n" % fuzzer_overhead_percent

            # measured_time_in_mutation_total_seconds = mutation_debug_timing_query_time()
            measured_time_in_mutation_total_seconds = 0
            if measured_time_in_mutation_total_seconds != 0:
                runtime_mutate_measure_time = utils.covert_runtime_to_string(measured_time_in_mutation_total_seconds)
                measured_time_in_mutation_percent = (100.0 / total_passed_seconds) * measured_time_in_mutation_total_seconds
                output += "DEBUGGING Measure time in mutation: %s (%.2f %% of total runtime)" % (runtime_mutate_measure_time, measured_time_in_mutation_percent)

            output += "\n" + "#" * 95 + "\n"

            # dumping status updates to the log would create huge logs => the status msg is stored in a separate file,
            # therefore pass false to dump_message_to_logfile
            utils.msg(output, dump_message_to_logfile=False)
            if dumped_tags or forcefully_dump_everything:
                # Also dump the current status to an output file
                with open(cfg.output_dir_status_result_file, "w") as fobj:
                    fobj.write(output)
                gce_bucket_sync.save_stats(cfg.status_result_filename, output)

            if cfg.fuzzer_arguments.measure_mode:
                self.measure_mode_print_iterations += 1
                if self.measure_mode_print_iterations >= cfg.measure_mode_number_of_status_updates:
                    cfg.exec_engine.print_statistics()
                    utils.exit_and_msg("Finished measuring, stopping...")

            if cfg.fuzzer_arguments.max_executions != 0 and number_executions >= cfg.fuzzer_arguments.max_executions:
                utils.exit_and_msg("Max number executions reached, going to stop...")


    def reset_stats(self):
        self.number_fuzzing_executions = 0
        self.stats_success = 0
        self.stats_crash = 0
        self.stats_exception_crash = 0
        self.stats_exception = 0
        self.stats_timeout = 0
        self.stats_new_behavior = 0
        self.start_time = datetime.datetime.now().replace(microsecond=0)
        self.start_time_str = self.start_time.strftime(cfg.status_update_time_format)

        self.expected_runtime_total_sum = 0
        self.expected_runtime_number_values = 0
        self.real_runtime_total_sum = 0
        self.real_runtime_number_values = 0



def _get_current_time():
    current_time = datetime.datetime.now().replace(microsecond=0)
    current_time_str = current_time.strftime(cfg.status_update_time_format)
    return current_time, current_time_str
