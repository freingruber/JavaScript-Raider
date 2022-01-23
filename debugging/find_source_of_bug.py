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



# This script is basically just a grep in all source-directories.
# For example, if a crash is found during corpus generation, this script checks
# from which source the crash originated.
# E.g: if v8 (Chrome) crashes because of a testcase from SpiderMonkey (Firefox),
# it's maybe a new bug in v8. But if v8 crashes because of a testcase from v8 regression tests
# it's very likely an already known-bug.
# It' therefore useful to quickly grep for the source of the testcase
#
# Example invocation:
# python3 find_source_of_bug.py

import os
import os.path


source_dirs = [
    "ChakraCore",
    "javascript_snippets",
    "js-by-examples",
    "js-vuln-db",
    "mozilla_developer",
    "mozilla_developer_old",
    "mozilla_interactive_examples",
    "spidermonkey",
    "sputniktests",
    "v8_test_regex",
    "v8_tests",
    "w3resource",
    "w3resource_exercises",
    "Webkit_tests",
    "fuzzilli",
    "fuzzilli_from_samuel",
    "DIE_corpus",
]

base_path = '.'
base_path = os.path.abspath(base_path)
subfolder_name = "files"

for directory_name in source_dirs:
    fullpath = os.path.join(base_path, directory_name)

    if os.path.isdir(fullpath):
        fullpath = os.path.join(fullpath, subfolder_name)
        if os.path.isdir(fullpath):
            print("Processing folder: %s" % fullpath)
            for testcase_name in os.listdir(fullpath):
                testcase_path = os.path.join(fullpath, testcase_name)
                with open(testcase_path, 'r') as fobj:
                    try:
                        content = fobj.read().rstrip().encode('utf-8')
                        content = content.decode("utf-8")
                    except:
                        continue

                if "someBugPattern" in content and "anotherBugPattern" in content:
                    print("Found bug at: %s" % testcase_path)
