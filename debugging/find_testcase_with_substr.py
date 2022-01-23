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



# The script is used to detect corpus files which use specific words / a substring.
# For example, the current version searches for v8-specific testcases
# (which may need to be rewritten to target SpiderMonkey, JSC, ...)


import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)


words = [
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
    "%IsValidSmi",
    "%CreateAsyncFromSyncIterator",
    "%HasSmiOrObjectElements",
    "%CreatePrivateSymbol",
    "%GetOptimizationStatus",
    "quit(",
    "%IsBeingInterpreted",
]

testcase_dir = "/home/user/Desktop/input/OUTPUT/current_corpus/"


for filename in os.listdir(testcase_dir):
    if filename.endswith("pickle"):
        continue
    if filename.endswith(".js") is False:
        continue

    filepath = os.path.join(testcase_dir, filename)
    with open(filepath, 'r') as fobj:
        content = fobj.read().rstrip()
    
    for word in words:
        if word in content:
            print("Word: %s in %s" % (word, filename))
            break
