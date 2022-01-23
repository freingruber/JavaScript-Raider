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



# If I know from result analysis (analysis of the created tagging files) that some specific testcases perform
# not very good, I use this script to check if the file was permanently disabled
#
# Example invocation:
# python3 check_if_testcase_is_permanently_disabled.py
#
import pickle

with open("/home/user/Desktop/input/OUTPUT/disabled_files.pickle", "rb") as fobj:
    disabled_files = pickle.load(fobj)

print("Number disabled files: %d" % len(disabled_files))

# Query specific files
if "tc13789.js" in disabled_files:
    print("Yes")
if "tc510.js" in disabled_files:
    print("Yes")
if "tc627.js" in disabled_files:
    print("Yes") 
