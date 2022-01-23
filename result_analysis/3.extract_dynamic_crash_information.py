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



# This script will execute all crashes and store stdout/stderr (+ GDB output?)
# The collected information can be used by the next script to categorize the crashes

import os
import sys
sys.path.append("..")

from native_code.executor import Executor, Execution_Status
import hashlib
import re
import subprocess
import pickle


# GDB command:
# gdb ./d8 -ex="r --expose-gc --single-threaded --predictable --allow-natives-syntax --interrupt-budget=1024 --fuzzing /home/user/Desktop/downloaded_crashes/crashes_filtered_BUCKET/2477b1bf849645212d7a79fc45b30479.js; q"

d8_path = "/home/user/Desktop/fuzzer/Target_v8/v8_aug_2021_without_coverage/d8"
crash_dir1 = "/home/user/Desktop/fuzzer_data/crashes_filtered/"
exec_engine = None

all_crashes = []
all_crashes_hashes = set()
crash_content_to_filepath = dict()
files_without_crashes = set()



def get_hash_of_content(content):
    m = hashlib.md5()
    m.update(content.encode("utf-8"))
    crash_hash = str(m.hexdigest())
    return crash_hash


def handle_crash(fullpath):
    global all_crashes, crash_content_to_filepath
    with open(fullpath, "r") as fobj:
        content = fobj.read()

    crash_hash = get_hash_of_content(content)

    if crash_hash not in all_crashes_hashes:    # crash not seen yet
        all_crashes.append(content)
        all_crashes_hashes.add(crash_hash)

        crash_content_to_filepath[content] = fullpath
    # print(fullpath)
    # print(content)
    # input("<enter>")


# This function will execute d8 and collected crash data (e.g. stdout/stderr or GDB output)
# Results are stored in two pickle files!
def extract_crash_information():
    global exec_engine, all_crashes, files_without_crashes

    if os.path.isfile("analyzed_crashes.pickle"):
        with open("analyzed_crashes.pickle", 'rb') as finput:
            # This is a cache file of already analyzed files
            # E.g.: If I fuzz for 3 days, and start to download/analyze crashes on day1
            # then I must not execute on day3 all crashes again because day1 crashes were already analyzed
            # These results are stored in this pickle file
            all_crashes_analyzed = pickle.load(finput)
    else:
        all_crashes_analyzed = []

    # Current d8 default instrumentation
    if exec_engine is not None:
        del exec_engine
    exec_engine = Executor(timeout_per_execution_in_ms=2000, enable_coverage=False, custom_path_d8=d8_path)
    current_id = 0
    number_crashes = len(all_crashes)
    print("number_crashes: %d" % number_crashes)
    for crash_content in all_crashes:
        current_id += 1

        already_calculated = False
        for entry in all_crashes_analyzed:
            (prev_content, tmp2, tmp3) = entry
            if prev_content == crash_content:
                already_calculated = True
                break
        if already_calculated:
            print("Already calculated, so skipping file")
            continue

        exec_engine.restart_engine()
        result = exec_engine.execute_once(crash_content)
        print("Handling file %d of %d " % (current_id, number_crashes))
        if result.status == Execution_Status.CRASH:
            # Crash is reliable, so get some additional information

            stderr = result.engine_stderr

            fullpath_crash_content = crash_content_to_filepath[crash_content]
            try:
                result = subprocess.run([d8_path, '--debug-code', "--expose-gc", "--single-threaded", "--predictable",
                                         "--allow-natives-syntax", "--interrupt-budget=1024", "--fuzzing",
                                         fullpath_crash_content], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=10)
                full_output = result.stdout + result.stderr
            except:
                print("EXECUTION TIMEOUT!")
                full_output = "TIMEOUT"

            all_crashes_analyzed.append((crash_content, stderr, full_output))
        else:
            print("NO CRASH: %s" % crash_content_to_filepath[crash_content])
            files_without_crashes.add(crash_content_to_filepath[crash_content])


    # A short note why I store pickle files here (and not just return the data)
    # Analyzing crash information can take several hours, so I store the results in a file
    # If I then want to
    with open("analyzed_crashes.pickle", 'wb') as fout:
        pickle.dump(all_crashes_analyzed, fout, pickle.HIGHEST_PROTOCOL)
    with open("files_without_crashes.pickle", 'wb') as fout:
        pickle.dump(files_without_crashes, fout, pickle.HIGHEST_PROTOCOL)


def check_files_without_crashes():
    with open("files_without_crashes.pickle", 'rb') as finput:
        my_files_without_crashes = pickle.load(finput)

    for fullpath in my_files_without_crashes:
        with open(fullpath, "r") as fobj:
            content = fobj.read()
        if "await import(\"test\")" in content:
            continue
        if "await import((() => \"test\")())" in content:
            continue
        if ".repeat(0x201f" in content:
            continue
        if "await import" in content:
            continue
        if " ...var_" in content and "40000" in content:
            continue
        print(fullpath)
        # print(content)
        # sys.exit(-1)


def main():
    global crash_dir1, exec_engine, all_crashes, crash_content_to_filepath

    # Iterate over all crash files and pass them to handle_crash()
    for root, dirnames, filenames in os.walk(crash_dir1):
        for filename in filenames:
            if filename.endswith(".js"):
                fullpath = os.path.join(root, filename)
                handle_crash(fullpath)

    extract_crash_information()
    # check_files_without_crashes()

    with open("crash_content_to_filepath.pickle", 'wb') as fout:
        pickle.dump(crash_content_to_filepath, fout, pickle.HIGHEST_PROTOCOL)


if __name__ == "__main__":
    main()
