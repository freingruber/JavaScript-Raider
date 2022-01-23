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



# I saved pickle files with a different folder structure
# Since I changed the folder structure, the pickle files can't be loaded anymore
# because pickle stores the paths to the classes
# => This script rewrites the pickle files to the new folder structure
# You should not need this script anymore.

import pickle

import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import testcase_state


class RenameUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        if module == "initial_js_corpus.testcase_state":
            module = "testcase_state"
        print(module)
        return super(RenameUnpickler, self).find_class(module, name)

# Code to handle Operations Pickle files:
# x = open("/home/user/Desktop/input/databases/variable_operations_states_list.pickle", "rb")
# y = RenameUnpickler(x).load()
# with open("/home/user/Desktop/input/databases/variable_operations_states_list2.pickle", 'wb') as fout:
#     pickle.dump(y, fout, pickle.HIGHEST_PROTOCOL)


# Code to handle corpus dirs:
"""
basedir = "/home/user/Desktop/input/OUTPUT/current_corpus/"
for filename in os.listdir(basedir):
    if filename.endswith(".js.pickle") is False:
        continue
    fullpath = os.path.join(basedir, filename)
    with open(fullpath, "rb") as x:
        y = RenameUnpickler(x).load()
    with open(fullpath, 'wb') as fout:
        pickle.dump(y, fout, pickle.HIGHEST_PROTOCOL)
"""