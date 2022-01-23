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



# I think I used to file to perform some tests of generated testcase states
# Currently I store the testcase state very inefficiently (e.g. strings instead of numbers).
# For example, I store as datatype "uint8clampedarray", but I could just assign the number 4
# for "uint8clampedarray". Then I would just need to store 4 instead of "uint8clampedarray" in the state
# which would dramatically reduce the disk space and RAM memory required to store all states.
# However, this requires one additional lookup.
# I used this script to perform some tests to detect the optimal way to store the state in the future

# It's most likely that the script doesn't work at the moment

from __future__ import print_function
from sys import getsizeof, stderr
from itertools import chain
from collections import deque
from reprlib import repr
import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import testcase_state
import psutil
import pickle
import math
import gc
import bz2
import utils




mapping_lower_datatype_to_datatype_index = dict()

# Important, "mapping_datatype_index_to_real_datatype" must be a list and not a 
# dict to ensure fast lookups!
mapping_datatype_index_to_real_datatype = [""]*62
mapping_lower_datatype_to_datatype_index["string"] = 0
mapping_datatype_index_to_real_datatype[0] = "String"
mapping_lower_datatype_to_datatype_index["array"] = 1
mapping_datatype_index_to_real_datatype[1] = "Array"
mapping_lower_datatype_to_datatype_index["int8array"] = 2
mapping_datatype_index_to_real_datatype[2] = "Int8Array"
mapping_lower_datatype_to_datatype_index["uint8array"] = 3
mapping_datatype_index_to_real_datatype[3] = "Uint8Array"
mapping_lower_datatype_to_datatype_index["uint8clampedarray"] = 4
mapping_datatype_index_to_real_datatype[4] = "Uint8ClampedArray"
mapping_lower_datatype_to_datatype_index["int16array"] = 5
mapping_datatype_index_to_real_datatype[5] = "Int16Array"
mapping_lower_datatype_to_datatype_index["uint16array"] = 6
mapping_datatype_index_to_real_datatype[6] = "Uint16Array"
mapping_lower_datatype_to_datatype_index["int32array"] = 7
mapping_datatype_index_to_real_datatype[7] = "Int32Array"
mapping_lower_datatype_to_datatype_index["uint32array"] = 8
mapping_datatype_index_to_real_datatype[8] = "Uint32Array"
mapping_lower_datatype_to_datatype_index["float32array"] = 9
mapping_datatype_index_to_real_datatype[9] = "Float32Array"
mapping_lower_datatype_to_datatype_index["float64array"] = 10
mapping_datatype_index_to_real_datatype[10] = "Float64Array"
mapping_lower_datatype_to_datatype_index["bigint64array"] = 11
mapping_datatype_index_to_real_datatype[11] = "BigInt64Array"
mapping_lower_datatype_to_datatype_index["biguint64array"] = 12
mapping_datatype_index_to_real_datatype[12] = "BigUint64Array"
mapping_lower_datatype_to_datatype_index["set"] = 13
mapping_datatype_index_to_real_datatype[13] = "Set"
mapping_lower_datatype_to_datatype_index["weakset"] = 14
mapping_datatype_index_to_real_datatype[14] = "WeakSet"
mapping_lower_datatype_to_datatype_index["map"] = 15
mapping_datatype_index_to_real_datatype[15] = "Map"
mapping_lower_datatype_to_datatype_index["weakmap"] = 16
mapping_datatype_index_to_real_datatype[16] = "WeakMap"
mapping_lower_datatype_to_datatype_index["regexp"] = 17
mapping_datatype_index_to_real_datatype[17] = "RegExp"
mapping_lower_datatype_to_datatype_index["arraybuffer"] = 18
mapping_datatype_index_to_real_datatype[18] = "ArrayBuffer"
mapping_lower_datatype_to_datatype_index["sharedarraybuffer"] = 19
mapping_datatype_index_to_real_datatype[19] = "SharedArrayBuffer"
mapping_lower_datatype_to_datatype_index["dataview"] = 20
mapping_datatype_index_to_real_datatype[20] = "DataView"
mapping_lower_datatype_to_datatype_index["promise"] = 21
mapping_datatype_index_to_real_datatype[21] = "Promise"
mapping_lower_datatype_to_datatype_index["intl.collator"] = 22
mapping_datatype_index_to_real_datatype[22] = "Intl.Collator"
mapping_lower_datatype_to_datatype_index["intl.datetimeformat"] = 23
mapping_datatype_index_to_real_datatype[23] = "Intl.DateTimeFormat"
mapping_lower_datatype_to_datatype_index["intl.listformat"] = 24
mapping_datatype_index_to_real_datatype[24] = "Intl.ListFormat"
mapping_lower_datatype_to_datatype_index["intl.numberformat"] = 25
mapping_datatype_index_to_real_datatype[25] = "Intl.NumberFormat"
mapping_lower_datatype_to_datatype_index["intl.pluralrules"] = 26
mapping_datatype_index_to_real_datatype[26] = "Intl.PluralRules"
mapping_lower_datatype_to_datatype_index["intl.relativetimeformat"] = 27
mapping_datatype_index_to_real_datatype[27] = "Intl.RelativeTimeFormat"
mapping_lower_datatype_to_datatype_index["intl.locale"] = 28
mapping_datatype_index_to_real_datatype[28] = "Intl.Locale"
mapping_lower_datatype_to_datatype_index["webassembly.module"] = 29
mapping_datatype_index_to_real_datatype[29] = "WebAssembly.Module"
mapping_lower_datatype_to_datatype_index["webassembly.instance"] = 30
mapping_datatype_index_to_real_datatype[30] = "WebAssembly.Instance"
mapping_lower_datatype_to_datatype_index["webassembly.memory"] = 31
mapping_datatype_index_to_real_datatype[31] = "WebAssembly.Memory"
mapping_lower_datatype_to_datatype_index["webassembly.table"] = 32
mapping_datatype_index_to_real_datatype[32] = "WebAssembly.Table"
mapping_lower_datatype_to_datatype_index["webassembly.compileerror"] = 33
mapping_datatype_index_to_real_datatype[33] = "WebAssembly.CompileError"
mapping_lower_datatype_to_datatype_index["webassembly.linkerror"] = 34
mapping_datatype_index_to_real_datatype[34] = "WebAssembly.LinkError"
mapping_lower_datatype_to_datatype_index["webassembly.runtimeerror"] = 35
mapping_datatype_index_to_real_datatype[35] = "WebAssembly.RuntimeError"
mapping_lower_datatype_to_datatype_index["urierror"] = 36
mapping_datatype_index_to_real_datatype[36] = "URIError"
mapping_lower_datatype_to_datatype_index["typeerror"] = 37
mapping_datatype_index_to_real_datatype[37] = "TypeError"
mapping_lower_datatype_to_datatype_index["syntaxerror"] = 38
mapping_datatype_index_to_real_datatype[38] = "SyntaxError"
mapping_lower_datatype_to_datatype_index["rangeerror"] = 39
mapping_datatype_index_to_real_datatype[39] = "RangeError"
mapping_lower_datatype_to_datatype_index["evalerror"] = 40
mapping_datatype_index_to_real_datatype[40] = "EvalError"
mapping_lower_datatype_to_datatype_index["referenceerror"] = 41
mapping_datatype_index_to_real_datatype[41] = "ReferenceError"
mapping_lower_datatype_to_datatype_index["error"] = 42
mapping_datatype_index_to_real_datatype[42] = "Error"
mapping_lower_datatype_to_datatype_index["date"] = 43
mapping_datatype_index_to_real_datatype[43] = "Date"
mapping_lower_datatype_to_datatype_index["null"] = 44
mapping_datatype_index_to_real_datatype[44] = "null"
mapping_lower_datatype_to_datatype_index["math"] = 45
mapping_datatype_index_to_real_datatype[45] = "Math"
mapping_lower_datatype_to_datatype_index["json"] = 46
mapping_datatype_index_to_real_datatype[46] = "JSON"
mapping_lower_datatype_to_datatype_index["reflect"] = 47
mapping_datatype_index_to_real_datatype[47] = "Reflect"
mapping_lower_datatype_to_datatype_index["globalThis"] = 48
mapping_datatype_index_to_real_datatype[48] = "globalThis"
mapping_lower_datatype_to_datatype_index["atomics"] = 49
mapping_datatype_index_to_real_datatype[49] = "Atomics"
mapping_lower_datatype_to_datatype_index["intl"] = 50
mapping_datatype_index_to_real_datatype[50] = "Intl"
mapping_lower_datatype_to_datatype_index["webassembly"] = 51
mapping_datatype_index_to_real_datatype[51] = "WebAssembly"
mapping_lower_datatype_to_datatype_index["object1"] = 52
mapping_datatype_index_to_real_datatype[52] = "Object"
mapping_lower_datatype_to_datatype_index["object2"] = 53
mapping_datatype_index_to_real_datatype[53] = "Object"
mapping_lower_datatype_to_datatype_index["unkown_object"] = 54
mapping_datatype_index_to_real_datatype[54] = "Object"
mapping_lower_datatype_to_datatype_index["real_number"] = 55
mapping_datatype_index_to_real_datatype[55] = "Number"
mapping_lower_datatype_to_datatype_index["special_number"] = 56
mapping_datatype_index_to_real_datatype[56] = "Number"
mapping_lower_datatype_to_datatype_index["function"] = 57
mapping_datatype_index_to_real_datatype[57] = "Function"
mapping_lower_datatype_to_datatype_index["boolean"] = 58
mapping_datatype_index_to_real_datatype[58] = "Boolean"
mapping_lower_datatype_to_datatype_index["symbol"] = 59
mapping_datatype_index_to_real_datatype[59] = "Symbol"
mapping_lower_datatype_to_datatype_index["undefined"] = 60
mapping_datatype_index_to_real_datatype[60] = "undefined"
mapping_lower_datatype_to_datatype_index["bigint"] = 61
mapping_datatype_index_to_real_datatype[61] = "BigInt"

# Debugging function to calculate size of objects
"""
def total_size(o, handlers={}, verbose=False):
    dict_handler = lambda d: chain.from_iterable(d.items())
    all_handlers = {tuple: iter,
                    list: iter,
                    deque: iter,
                    dict: dict_handler,
                    set: iter,
                    frozenset: iter,
                    }
    all_handlers.update(handlers)     # user handlers take precedence
    seen = set()                      # track which object id's have already been seen
    default_size = getsizeof(0)       # estimate sizeof object without __sizeof__

    def sizeof(o):
        if id(o) in seen:       # do not double count the same object
            return 0
        seen.add(id(o))
        s = getsizeof(o, default_size)

        if verbose:
            print(s, type(o), repr(o), file=stderr)

        for typ, handler in all_handlers.items():
            if isinstance(o, typ):
                s += sum(map(sizeof, handler(o)))
                break
        return s

    return sizeof(o)
"""


def convert_variable_name_to_variable_key(variable_name):
    # Note: In the state creation code I also extract "self" and "args"
    # but these names are not common and therefore they don't get an index
    # (6 occurrences in the full corpus)
    if variable_name == "this":
        return 0
    elif variable_name == "arguments":
        return 1
    elif variable_name == "new.target":
        return 2
    elif variable_name.startswith("var_") and variable_name.endswith("_") and "." not in variable_name:
        variable_id = int(variable_name[4:-1], 10)
        return variable_id + 3  # +3 because indexes 0-2 are used for this, arguments & new.target
    else:
        # These are variable names which I couldn't rename and can be arbitrary
        # => I need to store them using the full name and can't use an integer for this
        if str.isnumeric(variable_name):
            # This could overlap the "var_X_" entries, but I think this can't occur because a number is a number not a variable
            utils.perror("Error, found numeric variable name which should not occur")
        return variable_name
    

def convert_variable_key_to_variable_name(variable_key):
    if isinstance(variable_key, int):
        if variable_key == 0:
            return "this"
        elif variable_key == 1:
            return "arguments"
        elif variable_key == 2:
            return "new.target"
        else:
            variable_id = variable_key - 3
            return "var_%d_" % variable_id
    else:
        return variable_key     # it's already the variable name


def convert_size(size_bytes):
    if size_bytes == 0:
        return "0B"
    size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return "%s %s" % (s, size_name[i])


def show_current_usage(label):
    process = psutil.Process(os.getpid())
    print("%s usage: %s" % (label, convert_size(process.memory_info().rss)))


if len(sys.argv) > 1:
    show_current_usage("Before loading new pickle")
    with open("tester.pickle", 'rb') as finput:
        state_list = pickle.load(finput)
    show_current_usage("After loading new pickle")
    sys.exit(-1)


show_current_usage("Before loading pickle")
with open("../variable_operations_states_list.pickle", 'rb') as finput:
    state_list = pickle.load(finput)

show_current_usage("After loading pickle")

number_deletes_variable_types = 0
number_deletes_property_types = 0
number_deletes_array_lengths = 0

state_list2 = []
count = 0
for entry in state_list:
    count += 1
    entry_copy = entry.deep_copy()

    del entry_copy.testcase_filename
    del entry_copy.unreliable_score 
    del entry_copy.deterministic_processing_was_done
    del entry_copy.number_total_triggered_edges
    del entry_copy.unique_triggered_edges

    del entry_copy.curly_brackets_list  # I'm always recalculating it before I'm using it, so it doesn't make sense to store it

    
    # Fix the variable types
    x = dict()
    for key_name in entry_copy.variable_types.keys():
        values = entry_copy.variable_types[key_name]
        y = []
        for value in values:
            (line_number, data_type_str) = value
            data_type_index = mapping_lower_datatype_to_datatype_index[data_type_str]
            y.append((line_number, data_type_index))
        
        new_key_name = convert_variable_name_to_variable_key(key_name)
        x[new_key_name] = y
    
    if len(x.keys()) == 0:
        # will likely never occur because I have always entries such as "this"
        x = None
    entry_copy.variable_types = x
    

    # Fix the array items/properties
    x = dict()
    for key_name in entry_copy.array_items_or_properties.keys():
        values = entry_copy.array_items_or_properties[key_name]
        y = []
        for value in values:
            (line_number, data_type_str) = value
            data_type_index = mapping_lower_datatype_to_datatype_index[data_type_str]
            y.append((line_number, data_type_index))
        x[key_name] = y
    if len(x.keys()) == 0:
        x = None
    entry_copy.array_items_or_properties = x

    
    # Fix the array length values:
    x = dict()
    for key_name in entry_copy.array_lengths.keys():
        values = entry_copy.array_lengths[key_name]
        # print("key_name: %s" % key_name)
        # print(values)
        # input("waiter")

        y = []
        for value in values:
            (line_number, list_length_values) = value
            if len(list_length_values) == 0:
                continue    # skip it
            elif len(list_length_values) == 1:
                list_length_values = list_length_values[0]
            y.append((line_number, list_length_values))

        new_key_name = convert_variable_name_to_variable_key(key_name)
        x[new_key_name] = y
    if len(x.keys()) == 0:
        x = None
    entry_copy.array_lengths = x

    del entry_copy.variable_types
    # del entry_copy.array_items_or_properties
    # del entry_copy.array_lengths

    state_list2.append(entry_copy)



with open("tester.pickle", 'wb') as fout:
    pickle.dump(state_list2, fout, pickle.HIGHEST_PROTOCOL)
print("Saved new file")

print("number_deletes_variable_types: %d" % number_deletes_variable_types)
print("number_deletes_property_types: %d" % number_deletes_property_types)
print("number_deletes_array_lengths: %d" % number_deletes_array_lengths)

"""
with open("tester.pickle", 'wb') as fout:
    pickle.dump(state_list2, fout, pickle.HIGHEST_PROTOCOL)


with bz2.BZ2File("tester2.pickle.pbz2", "w") as fout:
    pickle.dump(state_list2, fout, pickle.HIGHEST_PROTOCOL)



show_current_usage("Before loading pickle")
with bz2.BZ2File("tester2.pickle.pbz2", 'r') as finput:
    state_list = pickle.load(finput)

show_current_usage("After loading compressed pickle")
"""