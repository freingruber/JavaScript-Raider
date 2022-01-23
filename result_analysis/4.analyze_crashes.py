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



# This script takes the extract information from the previous script and
# tries to detect which crash files belongs to which bug
# I typically restart the script until I don't find new bugs.
# If I find a new bug, I try to develop a detection rule in the function
# analyze_crash_information() which detects all similar crashes
# Then I restart this script and I continue this until I find no new crashes

import os
import sys
import hashlib
import re
import pickle


output_dir = "/home/user/Desktop/fuzzer_data/crashes_analyzed/"


def get_hash_of_content(content):
    m = hashlib.md5()
    m.update(content.encode("utf-8"))
    crash_hash = str(m.hexdigest())
    return crash_hash


def store_crash(crash_content, full_output, crash_folder_to_use):
    global output_dir

    output_folder_path = os.path.join(output_dir, crash_folder_to_use)
    if not os.path.exists(output_folder_path):
        os.makedirs(output_folder_path)

    crash_hash = get_hash_of_content(crash_content)
    output_filename = crash_hash + ".js"
    output_filename_analysis = crash_hash + ".txt"
    output_fullpath = os.path.join(output_folder_path, output_filename)
    output_fullpath_analysis = os.path.join(output_folder_path, output_filename_analysis)

    with open(output_fullpath, "w") as fobj:
        fobj.write(crash_content)

    with open(output_fullpath_analysis, "w") as fobj:
        fobj.write(full_output)




def analyze_crash_information():
    with open("analyzed_crashes.pickle", 'rb') as finput:
        all_crashes_analyzed = pickle.load(finput)


    with open("crash_content_to_filepath.pickle", 'rb') as finput:
        crash_content_to_filepath = pickle.load(finput)

    print("Number of crashes:")
    print(len(all_crashes_analyzed))
    for entry in all_crashes_analyzed:
        (crash_content, stderr, full_output) = entry

        fullpath_crashfile = crash_content_to_filepath[crash_content]

        try:
            if b"Debug check failed: GetCurrentStackPosition() >= stack_guard()->real_climit() - 8 * KB" in full_output:
                store_crash(crash_content, full_output, "bug_stack_overflow")
                continue
            elif b"Fatal JavaScript invalid size error" in full_output:
                continue
            elif b"Debug check failed: IsAbsolutePath(" in full_output:
                continue
            elif b"Fatal error in ../../src/objects/js-locale.cc, line 428\n# Debug check failed: U_SUCCESS(status)" in full_output:
                store_crash(crash_content, full_output, "bug_jslocal1")
                continue
            elif b"Fatal error in ../../src/objects/js-locale.cc, line 458\n# Debug check failed: U_SUCCESS(status)" in full_output:
                store_crash(crash_content, full_output, "bug_jslocal2")
                continue
            elif b"Fatal error in ../../src/compiler/typer.cc, line 339\n# Check failed: visitor.InductionVariablePhiTypeIsPrefixedPoint(induction_var)" in full_output:
                store_crash(crash_content, full_output, "bug_typer4")
                continue
            elif b"simplified-lowering.cc, line 4030" in full_output and b"Debug check failed: restriction_type.Is(info->restriction_type())" in full_output:
                store_crash(crash_content, full_output, "bug_simplified_lowering")
                continue  # bug1 (Simplified lowering with + and * in optimized code)
            elif full_output == b"TIMEOUT":
                store_crash(crash_content, full_output, "bug_timeout")
                continue
            elif b"../../src/objects/js-function.cc, line 336" in full_output and b"function->shared().HasFeedbackMetadata()" in full_output and b"%OptimizeOsr" in crash_content:
                store_crash(crash_content, full_output, "bug_optimize_osr")
                continue  # calling %OptimizeOsr() without previously preparing the function
            elif b"Stacktrace:" in full_output and b"failure_message_object=" in full_output and b"Object.freez" in crash_content:
                store_crash(crash_content, full_output, "bug_object_freeze")
                continue
            elif b"Object.freeze" in crash_content:
                store_crash(crash_content, full_output, "bug_object_freeze_without_output")
                continue
            elif b"../../src/handles/maybe-handles.h, line 51" in full_output and b"(location_) != nullptr" in full_output and b"use asm" in crash_content:
                store_crash(crash_content, full_output, "bug_big_int_and_use_asm")
                continue  # A big int is passed to a function which uses "use asm" and the "| 0" operation is performed on the BigInt
            elif b"../../src/d8/d8.cc, line 947" in full_output and b"IsAbsolutePath(file_name)" in full_output and b"import" in crash_content:
                store_crash(crash_content, full_output, "bug_importing_relative_path")
                continue
            elif b"../../src/objects/js-locale.cc, line 418" in full_output and b"U_SUCCESS(status)" in full_output and b"Intl." in crash_content:
                store_crash(crash_content, full_output, "bug_intl_not_successful1")
                continue
            elif b"../../src/objects/js-locale.cc, line 448" in full_output and b"U_SUCCESS(status)" in full_output and b"Intl." in crash_content:
                store_crash(crash_content, full_output, "bug_intl_not_successful2")
                continue
            elif b"double free or corruption (" in full_output:
                store_crash(crash_content, full_output, "bug8_double_free")
                continue
            elif b"abort: 32 bit value in register is not zero-extended" in full_output:
                store_crash(crash_content, full_output, "bug9_value_not_zero_extended")
                continue
            elif b"Received signal 11 SEGV_MAPERR" in full_output:
                store_crash(crash_content, full_output, "bug_segv_maperr")
                continue
        except:
            print("Testcase throws exception, manually check: %s" % fullpath_crashfile)

        print("Not yet handled crash: %s" % fullpath_crashfile)
        print("Crash content:")
        print(crash_content)
        print("\n"*5 + "Stderr:\n%s" % stderr)
        print("\n"*2 + "Full output:\n%s" % full_output)
        sys.exit(-1)


def main():
    analyze_crash_information()


if __name__ == "__main__":
    main()
