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



# This script tries to detect testcases for which variable renaming didn't work.
# This mainly occurred when importing a corpus from Fuzzilli.
# For example, Fuzzilli named a variable "v198" and then my fuzzer tries to rename the variable
# to for example: "var_50_". The last "_" is important for me for some operations, because if
# the testcase would also contain "v1981" and I would just do a stupid string-renaming in a
# mutation, I would also rename "v1981" and not just "v198". I therefore use a "_" after the ID
# like "var_198_". Because of this reason I try to rename all variable names, but this
# sometimes doesn't work because the newly detected coverage is not triggered after renaming.
# (e.g. the testcase triggers new coverage in the parsing code of the JS engine;
# which is most of the times not so interesting)
# In such a case I skip variable renaming and keep something like "v198" as variable name.
# This script tries to detect such testcases (in a hacky way..).
# I can then manually analyse them to better understand why variable renaming failed.


import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

testcase_dir = "/home/user/Desktop/input/OUTPUT/current_corpus/"

for filename in os.listdir(testcase_dir):
    if filename.endswith("pickle"):
        continue
    if filename.endswith(".js") is False:
        continue

    filepath = os.path.join(testcase_dir, filename)
    with open(filepath, 'r') as fobj:
        content = fobj.read().rstrip()

    for line in content.split("\n"):
        if "let " in line or "var " in line or "const " in line:
            if "var_" not in line:
                if line.strip().endswith("{"):
                    continue
                if "let of" in line:
                    continue
                print("Wrong variable name in file: %s" % filename)
                print(line)
                print("---------------")
