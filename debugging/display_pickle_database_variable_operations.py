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



import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import pickle


with open("generic_operations.pickle", 'rb') as finput:
    all_generic_operations_with_state = pickle.load(finput)

with open("variable_operations.pickle", 'rb') as finput:
    all_variable_operations_with_state = pickle.load(finput)

with open("variable_operations_others.pickle", 'rb') as finput:
    all_variable_operations_others_with_state = pickle.load(finput)

with open("variable_operations_states_list.pickle", 'rb') as finput:
    variable_operations_states_list = pickle.load(finput)

with open("variable_operations_list.pickle", 'rb') as finput:
    variable_operations_list = pickle.load(finput)


print("Generic operations: %d" % len(all_generic_operations_with_state))
"""
for operation in all_generic_operations_with_state:
    
    (code, state) = operation
    #print("Code (generic):%s" % code)
    print(code)
    #print(state)
    print("---------")
print("\n"*5)
"""


for variable_type in all_variable_operations_with_state:
    print("Datatype_operation %s : %d" % (variable_type, len(all_variable_operations_with_state[variable_type])))
    """
    for operation in all_variable_operations_with_state[variable_type]:
        (code, state) = operation
        print("Code (%s):%s" % (variable_type,code))
        #print(state)
        print("---------")
    """

print("\n"*5)
for variable_type in all_variable_operations_others_with_state:
    print("Datatype_operation (others) %s : %d" % (variable_type, len(all_variable_operations_others_with_state[variable_type])))
    """
    for operation in all_variable_operations_others_with_state[variable_type]:
        (code, state) = operation
        print("Code (%s other):%s" % (variable_type,code))
        #print(state)
        print("---------")
    """



# Manual checks if specific operations are in the database
for operation in all_variable_operations_with_state["regexp"]:
    (code_index, state_index) = operation
    code = variable_operations_list[code_index]
    print(code)
    print("---------")
    # if state != None:
    #    print("HERE")
    
    # if "new RegExp(var_TARGET_[var_1" in code:
    #    print("Code:\n%s" % code)
    #    print("---------")
    #    #print(state)

"""
    if len(code.split("\n")) == 1 or  len(code.split("\n")) == 2:
        #print(code)
        #print("---------")
    
        if "var var_1_ = false;" in code:
            print("Code:\n%s" % code)
            print("---------")
            print(state)
    """

"""
for operation in all_generic_operations_with_state:
    (code, state) = operation
    if len(code.split("\n")) == 1 or  len(code.split("\n")) == 2:
    #    print(code)
    #    print("---------")
    
        if ".sign(" in code:
            print("Code:\n%s" % code)
            print("---------")
"""