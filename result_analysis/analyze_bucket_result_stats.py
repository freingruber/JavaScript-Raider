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



# This script will take the stats files downloaded from GCE (or via SSH)
# and merges them to a final stats file (e.g. it adds up all numbers)
# Moreover, it can also merge tagging results, however, this is currently commented out
# because executing this for very long fuzzing sessions can take time

import os
import csv
import sys

sys.path.append("..")
import utils

stats_folder = "/home/user/Desktop/fuzzer_data/gce_synced_data/stats/"
tagging_output_filepath = "final_results_tagging.csv"
new_corpus_files_folder = "/home/user/Desktop/fuzzer_data/gce_synced_data/new_coverage/"

total_total_executions = 0
total_total_fuzzing_executions = 0
total_passed_seconds = 0
total_new_behavior = 0
total_crashes = 0
total_success = 0
total_exceptions = 0
total_timeouts = 0
total_engine_restarts = 0

total_number_status_log_files = 0


def handle_status_log(filepath):
    global total_total_executions, total_passed_seconds, total_new_behavior, total_crashes, total_total_fuzzing_executions
    global total_success, total_exceptions, total_timeouts, total_engine_restarts
    global total_number_status_log_files

    print(filepath)

    total_executions = None
    passed_seconds = None
    new_behavior = None
    crashes = None
    success = None
    exceptions = None
    timeouts = None
    engine_restarts = None
    total_fuzzing_executions = 0

    total_number_status_log_files += 1
    with open(filepath, "r") as fobj:
        content = fobj.read()
    for line in content.split("\n"):
        line = line.strip()
        parts = line.split(" ")
        line = line.lower()
        if "total executions:" in line:
            # example: 
            # Old line:
            # Speed: 18.16 execs / sec (total Executions: 18953647 ; passed seconds: 1043691)
            # New line:
            # speed: 14.45 execs / sec (total executions: 10000 ; total fuzzing executions: 8553 ; passed seconds: 692)
            total_executions = parts[7]
            total_fuzzing_executions = parts[12]
            passed_seconds = parts[16][:-1]
        if line.startswith("new behavior:"):
            new_behavior = parts[2]
        if line.startswith("crashes:"):
            crashes = parts[1]
        if line.startswith("success:"):
            success = parts[1]
        if line.startswith("exceptions:"):
            exceptions = parts[1]
        if line.startswith("timeouts:"):
            timeouts = parts[1]
        if line.startswith("engine restarts:"):
            engine_restarts = parts[2]

    total_total_executions += int(total_executions, 10)
    total_total_fuzzing_executions += int(total_fuzzing_executions, 10)
    # print("total_total_executions: %d" % total_total_executions)
    total_passed_seconds += int(passed_seconds, 10)
    total_new_behavior += int(new_behavior, 10)
    total_crashes += int(crashes, 10)
    total_success += int(success, 10)
    total_exceptions += int(exceptions, 10)
    total_timeouts += int(timeouts, 10)
    total_engine_restarts += int(engine_restarts, 10)


tags_to_values = dict()
tag_list = []  # used to keep the same order


def handle_tagging_log(filepath):
    global tags_to_values
    global tag_list

    with open(filepath) as fobj:
        readCSV = csv.DictReader(fobj, delimiter=",")
        for row in readCSV:
            tag = row['Tag']
            if tag.startswith("tc"):
                # skip testcase numbers, otherwise it would take very long to parse the files
                continue
            if tag not in tag_list:
                tag_list.append(tag)

            total_executions = int(row['Total executions'], 10)
            success = int(row['Success'], 10)
            new_coverage = int(row['New Coverage'], 10)
            exceptions = int(row['Exceptions'], 10)
            hangs = int(row['Hangs'], 10)
            crashes = int(row['Crashes'], 10)

            if tag not in tags_to_values:
                tags_to_values[tag] = (total_executions, success, new_coverage, exceptions, hangs, crashes)
            else:
                (prev_total_executions, prev_success, prev_new_coverage, prev_exceptions, prev_hangs, prev_crashes) = tags_to_values[tag]
                tags_to_values[tag] = (total_executions + prev_total_executions, success + prev_success, new_coverage + prev_new_coverage,
                                       exceptions + prev_exceptions, hangs + prev_hangs, crashes + prev_crashes)


def save_total_tagging_results():
    global tagging_output_filepath
    global tags_to_values
    global tag_list

    with open(tagging_output_filepath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(
            ["Tag", "Total executions", "Success", "Success %", "New Coverage", "New Coverage %", "Exceptions",
             "Exceptions %", "Hangs", "Hangs %", "Crashes", "Crashes %", ])

        for tag_name in tag_list:

            (total_executions, success, new_coverage, exceptions, hangs, crashes) = tags_to_values[tag_name]

            number_success_without_new_coverage = success
            number_success_with_new_coverage = new_coverage
            number_exception = exceptions
            number_hang = hangs
            number_crash = crashes

            total_executions_of_tag = total_executions
            if total_executions_of_tag == 0:
                number_success_without_new_coverage_relative = "0.0"
                number_success_with_new_coverage_relative = "0.0"
                number_exception_relative = "0.0"
                number_hang_relative = "0.0"
                number_crash_relative = "0.0"
            else:
                number_success_without_new_coverage_relative = "%.2f" % (
                            100 * float(number_success_without_new_coverage) / float(total_executions_of_tag))
                number_success_with_new_coverage_relative = "%.2f" % (
                            100 * float(number_success_with_new_coverage) / float(total_executions_of_tag))
                number_exception_relative = "%.2f" % (100 * float(number_exception) / float(total_executions_of_tag))
                number_hang_relative = "%.2f" % (100 * float(number_hang) / float(total_executions_of_tag))
                number_crash_relative = "%.2f" % (100 * float(number_crash) / float(total_executions_of_tag))

            writer.writerow([tag_name, total_executions_of_tag,
                             number_success_without_new_coverage,
                             number_success_without_new_coverage_relative,
                             number_success_with_new_coverage,
                             number_success_with_new_coverage_relative,
                             number_exception,
                             number_exception_relative,
                             number_hang,
                             number_hang_relative,
                             number_crash,
                             number_crash_relative,
                             ])


for filename in os.listdir(stats_folder):
    full_path = os.path.join(stats_folder, filename)
    if filename.endswith("status_log.txt"):
        handle_status_log(full_path)
    # if filename.endswith("_tagging_log.csv") == True:
    #    handle_tagging_log(full_path)

exec_speed = float(total_total_executions) / float(total_passed_seconds)
exec_speed_fuzzing = float(total_total_executions) / float(total_passed_seconds)

success_rate = 100.0 / (float(total_total_fuzzing_executions) / total_success)
timeout_rate = 100.0 / (float(total_total_fuzzing_executions) / total_timeouts)
exception_rate = 100.0 / (float(total_total_fuzzing_executions) / total_exceptions)

runtime_str = utils.covert_runtime_to_string(total_passed_seconds)

print("total_total_executions: %d" % total_total_executions)
print("total_total_fuzzing_executions: %d" % total_total_fuzzing_executions)
print("Execution speed: %.2f exec/sec" % exec_speed)
print("Fuzzing speed: %.2f exec/sec" % exec_speed_fuzzing)
print("total_passed_seconds: %d (%s)" % (total_passed_seconds, runtime_str))

# I don't display new behavior because currently I'm counting one file multiple times
# e.g. if a file gets imported from the bucket, then it's counted twice
# => I need an extra field "imported files" in the status update to count the number of unique
# new behavior files => but I don't really need this, I can just check how many .js files are stored in
# the "new_corpus_files" folder
# print("total_new_behavior: %d" % total_new_behavior)
if os.path.exists(new_corpus_files_folder):
    number_new_corpus_files = 0
    for filename in os.listdir(new_corpus_files_folder):
        if filename.endswith(".js"):
            number_new_corpus_files += 1
    print("total_new_behavior: %d" % number_new_corpus_files)

print("total_crashes: %d" % total_crashes)
print("total_success: %d (%.2f %%)" % (total_success, success_rate))
print("total_exceptions: %d (%.2f %%)" % (total_exceptions, exception_rate))
print("total_timeouts: %d (%.2f %%)" % (total_timeouts, timeout_rate))
print("total_engine_restarts: %d" % total_engine_restarts)

# save_total_tagging_results()
