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



# Purpose of the file:
# I have a lot of crashes originating from stupid bugs.
# If I would execute all crashes in d8 to collect crash information it would take very long (e.g. I would have to
# do this for ~50 000 - 70 000 crashes (every attempt requires an engine restart).
# Instead I'm statically skipping these "uninteresting" crashes.
# E.g.: if the crash content contains "%GetOptimizationStatus(" and the line afterwards starts with ","
# then it's very likely that my fuzzer added a 2nd argument to this native function call which leads always to a crash
# These crashes must not be analyzed and can be skipped to speed things up
# Please note: The fuzzer itself already tries to avoid the creation of such "simple-to-trigger-crashes", but it
# still found several ten thousand of them.

import os
import sys
import hashlib
import re
sys.path.append("..")
import javascript.js_parsing as js_parsing

# Files downloaded via GCE or SSH:
crash_dir = "/home/user/Desktop/fuzzer_data/crashes_from_gce_bucket/"
out_path = "/home/user/Desktop/fuzzer_data/crashes_filtered/"
files_downloaded_via = "bucket"    # valid options are "bucket" or "ssh"; This depends if the files in "crash_dir" were downloaded via ssh or via bucket
total_number = 0

# You can also define the hashes of specific crashes which should be skipped, but if you make a longer fuzzing run
# You will end up with ten thousands of crashes and then specifying every file manually will not work
# In this case you should go to the function >should_crash_be_skipped< and modify it to add new filter-rules
skip_files = set()
"""
skip_files.add("1d4655a85d4d07fc45b9548afbb530bc.js")
skip_files.add("20ad4beeb6a480fd45ed306ca67a8ad8.js")
skip_files.add("210109999c0c87ac45c4a0e7c64c24c2.js")
skip_files.add("2579dae6e18da6b87862f2be87910306.js")
skip_files.add("2744292d371134ca9da1d75533055caa.js")
skip_files.add("296905291da6b9c42cf6c86c2945a404.js")
skip_files.add("2d637ab6cdda7e8453fa03ffe79d94a9.js")
skip_files.add("31811d8004bafd11c3b2363cba6398b8.js")
skip_files.add("3224565b4fb12071181ff17a1c898b3b.js")
skip_files.add("32d35c1e0ece4bc6c43bbc46d7f6b88a.js")
skip_files.add("33ccf67ec7700224d4c3862bc27b77d0.js")
skip_files.add("34e186ea09a808fc243cb5c1b96e064b.js")
skip_files.add("362181306158fe5eaf3d18a4993e52dd.js")
skip_files.add("37644979b8350eb41a6d580883ab294b.js")
skip_files.add("3a22a517f93fd0ce07c942747bedfb13.js")
skip_files.add("3efe0f3225252dc0846358f3df5e6f7a.js")
skip_files.add("40d263c0a2b63bf8713c503f72e2dfbd.js")
skip_files.add("43799588a8a59808517e7fa98459840b.js")
skip_files.add("464e474f2f25c73ca2d9e516492afacb.js")
skip_files.add("479bf5fa21799d991911bd9db1db3196.js")
skip_files.add("484bbdcdc886d1ad8485252af881c5c5.js")
skip_files.add("4b6005013a641ad78b01f08831bb30e8.js")
skip_files.add("4bf1b8a8e8a5a0ba799cd2ab320a5613.js")
skip_files.add("4ca6c14af6b64e921c36461006ee1e3d.js")
skip_files.add("50e7b2e1e4feabf04c81c7f11fde0d80.js")
skip_files.add("53f05c9bb38b56dc8c32f2cc51a39478.js")
skip_files.add("578b9b5fade7b10968a2ce5ca8e7aaaf.js")
skip_files.add("6045369e0d4b3bab68cb7385f97560f6.js")
skip_files.add("621f29fa5c228d546a929cd244400a7d.js")
skip_files.add("64a669ad8484ac8e3059f62a7fcf2631.js")
skip_files.add("67adc68450b35cb437645e4c27cd561f.js")
skip_files.add("6c3ac3c2d7754706fdfe68695d2e0f2f.js")
skip_files.add("6cceb08fe618c3e78ec57da56c072859.js")
skip_files.add("6db9f80b146219d61f3947b5aa1d59d1.js")
skip_files.add("6dcca8a63d4747ea2e7ef4a6e510c55e.js")
skip_files.add("72dcd01aef74b3958f108f1f1a8ce856.js")
skip_files.add("7664b8f152553b6969fc3f670878cab2.js")
skip_files.add("7881c2661a4625c9b38e6dc959d57489.js")
skip_files.add("7c3248f232435abfc333cde123775bcd.js")
skip_files.add("7c3d51b1eb58c1a92bdd3ea16f8108a0.js")
skip_files.add("7cfb79af2c4e4e3a8ff1e2cafcea5199.js")
skip_files.add("82245e50563dad5b2e27b364a09b76b9.js")
skip_files.add("066413c9653c4d1dbb729145f6940682.js")
skip_files.add("0948f53c00a5e44c7f1c876959b96572.js")
skip_files.add("10d55b3f6c5a86fb97b43118c26f0143.js")
skip_files.add("1b6713c2b81591283f0839f30147f9e3.js")
skip_files.add("2cdfa76d20cd09d3b4964ed90a8ae1aa.js")
skip_files.add("3817d5ac748182da503f9cefdfa4373a.js")
skip_files.add("5861179b781e2e3ae01d2203d8783a61.js")
skip_files.add("607043078ad6c8681b60d2d62028aefe.js")
skip_files.add("9812f5a467b9e3806d83beb5c50ac584.js")
skip_files.add("9a64b359fdc50110dac0004332480814.js")
skip_files.add("a9a37283fc36a4349ba32ecfad0fcc7b.js")
skip_files.add("b0108c869af91d298a89ae9b95c1a5a0.js")
skip_files.add("c69489908eec307566f6040dc49d6a77.js")
skip_files.add("020db36494adbf3a8719ef20d9c1a7f6.js")
skip_files.add("0324570921c39f0abd84ae70445cb4f8.js")
skip_files.add("0a51145d0dcb3970d6256df1fb413040.js")
skip_files.add("0d33f88285ecb36290ae57b2516c1b8c.js")
skip_files.add("0d5d16e920ef4613d1a547324c257e17.js")
skip_files.add("1249586db0002cf3fecfe55c354a2901.js")
skip_files.add("15d00efbf9ff8fdd103d00ff0c3d204e.js")
skip_files.add("17107ea8e24bef5399dca7d4fca082e3.js")
"""



native_functions_names = [
    "%LiveEditPatchScript",
    "%IsWasmCode",
    "%IsAsmWasmCode",
    "%ConstructConsString",
    "%HaveSameMap",
    "%IsJSReceiver",
    "%HasSmiElements",
    "%HasObjectElements",
    "%HasDoubleElements",
    "%HasDictionaryElements",
    "%HasHoleyElements",
    "%HasSloppyArgumentsElements",
    "%HasFastProperties",
    "%HasPackedElement",
    "%ProfileCreateSnapshotDataBlob",
    "%NormalizeElements",
    "%SetWasmCompileControls",
    "%SetForceSlowPath",
    "%SetAllocationTimeout",
    "%ConstructDouble",
    "%OptimizeObjectForAddingMultipleProperties",
    "%RegexpHasNativeCode",
    "%RegexpHasBytecode",
    "%NewRegExpWithBacktrackLimit",
    "%TurbofanStaticAssert",
    "%DebugToggleBlockCoverage",
    "%StringLessThan",
    "%OptimizeOsr",
    "%IsBeingInterpreted",
    "%IsValidSmi",
    "%CreateAsyncFromSyncIterator",
    "%HasSmiOrObjectElements",
    "%CreatePrivateSymbol",
    "%GetOptimizationStatus",
    "%NeverOptimizeFunction",
    "%PrepareFunctionForOptimization",
]


def should_crash_be_skipped(content, fullpath):
    global native_functions_names

    lines = content.split("\n")
    if ".repeat(0x201f)" in content or ".repeat(({_:0x201f}" in content:
        return True
    if "await import(\"/\")" in content:
        return True
        
    if ".repeat((function _() {return _.arguments[0]})(0x201f)" in content:
        return True
    if (".repeat(3189095" in content or "'.repeat(({_:318909" in content) and ".split(" in content:
        return True
        
    if "%GetOptimizationStatus(" in content:
        current_line_number = 0
        for line in lines:
            if "%GetOptimizationStatus(" in line:
                # check if next line starts with ","
                if current_line_number+1 >= len(lines):
                    continue
                if lines[current_line_number+1].startswith(","):
                    return True        # skip this because a 2nd argument was injected to  "%GetOptimizationStatus"
            current_line_number += 1

    # Check if arguments were injected into native functions (which easily leads to crashes)
    """
    for word in native_functions_names:
        if word in content:
            all_occurrences = [m.start() for m in re.finditer(re.escape(word), content)]
            for occurrence_idx in all_occurrences:
                rest = content[occurrence_idx:]
                instr = js_parsing.parse_next_instruction(rest)
                if "," in instr:
                    return True # a lot of builtin-functions like %GetOptimizationStatus crash when multiple arguments are passed, ignore all of them
    """

    # If this point is reached, you can dump testcase contents and check if you can add
    # more filter rules
    # print(fullpath)
    # print(content)
    # sys.exit(-1)
    return False


def handle_file(fullpath, filename):
    global out_path, skip_files, total_number

    # print("Going to handle file %s ..." % fullpath)
    if filename in skip_files:
        return    # skip the file
                
    with open(fullpath, "r") as fobj:
        content = fobj.read()
        
        if should_crash_be_skipped(content, fullpath):
            return
        
        # Save the crash because it looks interesting
        total_number += 1
        full_out_path = os.path.join(out_path, filename)
        with open(full_out_path, "w") as fobj_out:
            fobj_out.write(content)
            

def parse_bucket_results():
    for root, dirnames, filenames in os.walk(crash_dir):
        for filename in filenames:
            if filename.endswith(".js") is False:
                continue    # skip the .tags files
            fullpath = os.path.join(root, filename)
            handle_file(fullpath, filename)


def parse_ssh_results():
    for hostname_dirname in os.listdir(crash_dir):
        fuzzer_hostname_dir = os.path.join(crash_dir, hostname_dirname)
        if os.path.isdir(fuzzer_hostname_dir):
            for output_dirname in os.listdir(fuzzer_hostname_dir):
                output_crash_dir = os.path.join(fuzzer_hostname_dir, output_dirname, "crashes")
                if os.path.isdir(output_crash_dir):
                    for filename in os.listdir(output_crash_dir):
                        if filename.endswith(".js") is False:
                            continue    # skip the previous folders
                        fullpath = os.path.join(output_crash_dir, filename)
                        handle_file(fullpath, filename)


def main():
    global total_number
    if files_downloaded_via == "bucket":
        parse_bucket_results()
    elif files_downloaded_via == "ssh":
        parse_ssh_results()
    else:
        print("Unkown option: %s" % files_downloaded_via)
        sys.exit(-1)
    print("Total number: %d" % total_number)
    

if __name__ == "__main__":
    main()
