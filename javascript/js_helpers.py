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



# TODO: What is the difference between js.py and js_helpers.py => merge them?

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import native_code.speed_optimized_functions as speed_optimized_functions
import utils
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js


# TODO: I must get rid of this mapping and just use the real JS-names everywhere instead of lowercase ones
mapping_lower_datatype_to_real_datatype = dict()
mapping_lower_datatype_to_real_datatype["string"] = "String"
mapping_lower_datatype_to_real_datatype["array"] = "Array"
mapping_lower_datatype_to_real_datatype["int8array"] = "Int8Array"
mapping_lower_datatype_to_real_datatype["uint8array"] = "Uint8Array"
mapping_lower_datatype_to_real_datatype["uint8clampedarray"] = "Uint8ClampedArray"
mapping_lower_datatype_to_real_datatype["int16array"] = "Int16Array"
mapping_lower_datatype_to_real_datatype["uint16array"] = "Uint16Array"
mapping_lower_datatype_to_real_datatype["int32array"] = "Int32Array"
mapping_lower_datatype_to_real_datatype["uint32array"] = "Uint32Array"
mapping_lower_datatype_to_real_datatype["float32array"] = "Float32Array"
mapping_lower_datatype_to_real_datatype["float64array"] = "Float64Array"
mapping_lower_datatype_to_real_datatype["bigint64array"] = "BigInt64Array"
mapping_lower_datatype_to_real_datatype["biguint64array"] = "BigUint64Array"
mapping_lower_datatype_to_real_datatype["set"] = "Set"
mapping_lower_datatype_to_real_datatype["weakset"] = "WeakSet"
mapping_lower_datatype_to_real_datatype["map"] = "Map"
mapping_lower_datatype_to_real_datatype["weakmap"] = "WeakMap"
mapping_lower_datatype_to_real_datatype["regexp"] = "RegExp"
mapping_lower_datatype_to_real_datatype["arraybuffer"] = "ArrayBuffer"
mapping_lower_datatype_to_real_datatype["sharedarraybuffer"] = "SharedArrayBuffer"
mapping_lower_datatype_to_real_datatype["dataview"] = "DataView"
mapping_lower_datatype_to_real_datatype["promise"] = "Promise"
mapping_lower_datatype_to_real_datatype["intl.collator"] = "Intl.Collator"
mapping_lower_datatype_to_real_datatype["intl.datetimeformat"] = "Intl.DateTimeFormat"
mapping_lower_datatype_to_real_datatype["intl.listformat"] = "Intl.ListFormat"
mapping_lower_datatype_to_real_datatype["intl.numberformat"] = "Intl.NumberFormat"
mapping_lower_datatype_to_real_datatype["intl.pluralrules"] = "Intl.PluralRules"
mapping_lower_datatype_to_real_datatype["intl.relativetimeformat"] = "Intl.RelativeTimeFormat"
mapping_lower_datatype_to_real_datatype["intl.locale"] = "Intl.Locale"
mapping_lower_datatype_to_real_datatype["webassembly.module"] = "WebAssembly.Module"
mapping_lower_datatype_to_real_datatype["webassembly.instance"] = "WebAssembly.Instance"
mapping_lower_datatype_to_real_datatype["webassembly.memory"] = "WebAssembly.Memory"
mapping_lower_datatype_to_real_datatype["webassembly.table"] = "WebAssembly.Table"
mapping_lower_datatype_to_real_datatype["webassembly.compileerror"] = "WebAssembly.CompileError"
mapping_lower_datatype_to_real_datatype["webassembly.linkerror"] = "WebAssembly.LinkError"
mapping_lower_datatype_to_real_datatype["webassembly.runtimeerror"] = "WebAssembly.RuntimeError"
mapping_lower_datatype_to_real_datatype["urierror"] = "URIError"
mapping_lower_datatype_to_real_datatype["typeerror"] = "TypeError"
mapping_lower_datatype_to_real_datatype["syntaxerror"] = "SyntaxError"
mapping_lower_datatype_to_real_datatype["rangeerror"] = "RangeError"
mapping_lower_datatype_to_real_datatype["evalerror"] = "EvalError"
mapping_lower_datatype_to_real_datatype["referenceerror"] = "ReferenceError"
mapping_lower_datatype_to_real_datatype["error"] = "Error"
mapping_lower_datatype_to_real_datatype["date"] = "Date"
mapping_lower_datatype_to_real_datatype["null"] = "null"
mapping_lower_datatype_to_real_datatype["math"] = "Math"
mapping_lower_datatype_to_real_datatype["json"] = "JSON"
mapping_lower_datatype_to_real_datatype["reflect"] = "Reflect"
mapping_lower_datatype_to_real_datatype["globalThis"] = "globalThis"
mapping_lower_datatype_to_real_datatype["atomics"] = "Atomics"
mapping_lower_datatype_to_real_datatype["intl"] = "Intl"
mapping_lower_datatype_to_real_datatype["webassembly"] = "WebAssembly"
mapping_lower_datatype_to_real_datatype["object1"] = "Object"
mapping_lower_datatype_to_real_datatype["object2"] = "Object"
mapping_lower_datatype_to_real_datatype["unkown_object"] = "Object"
mapping_lower_datatype_to_real_datatype["real_number"] = "Number"
mapping_lower_datatype_to_real_datatype["special_number"] = "Number"
mapping_lower_datatype_to_real_datatype["function"] = "Function"
mapping_lower_datatype_to_real_datatype["boolean"] = "Boolean"
mapping_lower_datatype_to_real_datatype["symbol"] = "Symbol"
mapping_lower_datatype_to_real_datatype["undefined"] = "undefined"
mapping_lower_datatype_to_real_datatype["bigint"] = "BigInt"


# calculate the >all_variable_types_lower_case_which_I_can_currently_instantiate< variable
# The global variable >mapping_lower_datatype_to_real_datatype< stores a mapping of variable types
# The keys can be used to get available variable types
all_variable_types_lower_case_which_I_can_currently_instantiate = list(mapping_lower_datatype_to_real_datatype.keys())
# Data types which I currently don't have implemented
not_implemented_data_types = ["math", "json", "reflect", "globalThis", "atomics", "intl", "undefined", "null",
                              "error", "typeerror", "referenceerror", "rangeerror", "syntaxerror", "urierror",
                              "evalerror", "webassembly", "webassembly.runtimeerror", "webassembly.linkerror",
                              "webassembly.compileerror", "webassembly.table", "webassembly.memory",
                              "webassembly.instance", "webassembly.module"]

for entry in not_implemented_data_types:
    if entry in all_variable_types_lower_case_which_I_can_currently_instantiate:
        all_variable_types_lower_case_which_I_can_currently_instantiate.remove(entry)
# unkown_object + object1 + object2?
# => they are all handled the same way in my code (when I create variables myself), so I just return "object1"
if "unkown_object" in all_variable_types_lower_case_which_I_can_currently_instantiate:
    all_variable_types_lower_case_which_I_can_currently_instantiate.remove("unkown_object")
if "object2" in all_variable_types_lower_case_which_I_can_currently_instantiate:
    all_variable_types_lower_case_which_I_can_currently_instantiate.remove("object2")
# Same for special_number and real_number
# => my code handles them the same way, so I just keep real_number
if "special_number" in all_variable_types_lower_case_which_I_can_currently_instantiate:
    all_variable_types_lower_case_which_I_can_currently_instantiate.remove("special_number")


def get_all_variable_names_in_testcase(content):
    variable_names_to_rename = set()
    for line in content.split("\n"):
        line = line.strip()

        if "let " in line or "var " in line or "const " in line:
            # if line.startswith("let ") or line.startswith("var ") or line.startswith("const "):
            # right_side = line.replace('\t',' ').split(" ",1)[1]
            splitter = " "
            if "let " in line:
                splitter = "let "
            elif "var " in line:
                splitter = "var "
            elif "const " in line:
                splitter = "const "
            # print("Line: %s" % line)
            right_side = line.split(splitter, 1)[1]
            # print("Right side: %s" % right_side)
            # We must also handle cases with something like:
            # let { x: [y], } = { x: [45] };
            # Or:
            # let [...{ length }] = [1, 2, 3];
            # wtf, why is this valid code?

            variable_name = right_side
            variable_name = variable_name.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("{", "").replace("}", "").replace(".", "")

            # Handle cases like:
            # var [...[x, y, z]] = [3, 4, 5];
            test = variable_name.split("=")[0]
            # print("TEST IS: %s" % test)
            if "," in test:
                test3 = test.replace(';', ' ').replace(':', ' ')
                for x in test3.split(','):
                    x = x.strip()
                    # print("Variable2 name to add: %s" % x)
                    variable_names_to_rename.add(x)

                test4 = test.replace(';', ',').replace(':', ',')
                for x in test4.split(','):
                    x = x.strip()
                    # print("Variable2 name to add: %s" % x)
                    variable_names_to_rename.add(x)
            else:
                variable_name = variable_name.replace('=', ' ').replace(';', ' ').replace(':', ' ').strip()
                if variable_name == "":
                    continue
                variable_name = variable_name.split()[0]
                # print("Variable name to add: %s" % variable_name.strip())
                variable_names_to_rename.add(variable_name.strip())

        elif "=" in line:
            idx = line.index("=")
            try:
                symbol_afterwards = line[idx + 1]
            except:
                symbol_afterwards = None
            if symbol_afterwards in ["=", "!", ">"]:
                continue

            left_side = line.split("=")[0]
            left_side = left_side.strip()
            try:
                if left_side[0] == "(" and left_side[-1] == ")":
                    left_side = left_side[1:-1]         # remove the ( and )
                    left_side = left_side.strip()
                elif left_side[0] == "[" and left_side[-1] == "]":
                    left_side = left_side[1:-1]         # remove the [ and ]
                    left_side = left_side.strip()
                elif left_side[0] == "{" and left_side[-1] == "}":
                    left_side = left_side[1:-1]         # remove the { and }
                    left_side = left_side.strip()
            except:
                pass
            left_side = left_side.strip()

            if contains_only_valid_token_characters(left_side):
                variable_names_to_rename.add(left_side)

            test2 = left_side.replace("[", "").replace("]", "").replace("(", "").replace(")", "").replace("{", "").replace("}", "").replace(".", "")
            if "," in test2:
                test = test2.replace(';', ',').replace(':', ',')
                for x in test.split(','):
                    x = x.strip()
                    variable_names_to_rename.add(x)
        else:
            pass

    # Now filter out some "bad" cases with incorrect variable names
    tmp = set()
    for variable_name in variable_names_to_rename:
        # print(variable_name)
        # TODO: write the next line better...
        variable_name = variable_name.replace("[", "").replace("]", "").replace("{", "").replace("}", "").replace("/", "").replace(":", "").replace('"', "").replace("'", "").replace("(", "").replace(")", "")
        if len(variable_name) == 0:
            continue    # just a safety check
        elif variable_name.startswith("var_"):
            continue
        if variable_name.startswith("func_"):
            continue
        elif variable_name == "arguments":
            continue
        elif variable_name == "yield":
            continue
        elif variable_name == "new.target":
            continue
        if " " in variable_name:
            variable_name = variable_name.split(" ")[0]

        variable_name = variable_name.strip()
        if variable_name.isdigit():
            continue
        tmp.add(variable_name)
    variable_names_to_rename = list(tmp)

    # Hack for fuzzilli corpus input:
    # Fuzzilli names all variables like "v123", so I can try if such variables
    # are in the testcase and then add variable names which I didn't detect correctly
    content_test = get_content_without_special_chars(content)
    for i in range(0, 2500):     # longest testcases had something like 1200 variables
        token_name = "v%d" % i
        token_name_with_space = token_name + " "
        if token_name_with_space in content_test:
            if token_name not in variable_names_to_rename:
                variable_names_to_rename.append(token_name)
    return variable_names_to_rename


def get_variable_name_candidates(content):
    content = get_content_without_strings(content)  # ensure that variable_tokens are not taken from strings
    content = get_content_without_special_chars_exclude_dot(content, " ")
    parts = content.split(" ")

    allowed_words = ["function", "class", "object", "array", "set", "async", "await", "break", "case", "class", "catch", "const", "continue", "debugger", "default", "delete", "do", "else", "enum", "export", "extends", "finally", "for", "function", "if", "implements", "import", "in", "interface", "instanceof", "let", "new", "package", "private", "protected", "public", "return", "static", "super", "switch", "this", "throw", "try", "typeof", "var", "void", "while", "with", "yield", "Object", "Function", "Boolean", "Error", "Number", "Date", "String", "RegExp", "Array", "Map", "Set", "WeakMap", "WeakSet", "ArrayBuffer", "SharedArrayBuffer", "Intl.Collator", "Intl.DateTimeFormat", "Intl.ListFormat", "Intl.NumberFormat", "Intl.PluralRules", "Intl.RelativeTimeFormat", "Object",
                     "Function",
                     "Boolean",
                     "Error",
                     "EvalError",
                     "InternalError",
                     "RangeError",
                     "ReferenceError",
                     "SyntaxError",
                     "TypeError",
                     "URIError",
                     "Number",
                     "Date",
                     "String",
                     "RegExp",
                     "Array",
                     "Int8Array",
                     "Uint8Array",
                     "Uint8ClampedArray",
                     "Int16Array",
                     "Uint16Array",
                     "Int32Array",
                     "Uint32Array",
                     "Float32Array",
                     "Float64Array",
                     "BigUint64Array",
                     "BigInt64Array",
                     "Map",
                     "Set",
                     "WeakMap",
                     "WeakSet",
                     "ArrayBuffer",
                     "SharedArrayBuffer",
                     "Intl.Collator",
                     "Intl.DateTimeFormat",
                     "Intl.ListFormat",
                     "Intl.NumberFormat",
                     "Intl.PluralRules",
                     "Intl.RelativeTimeFormat",
                     "DataView",
                     "Proxy",
                     "Promise",
                     "Symbol",
                     "Intl.Locale",
                     "WebAssembly.Table",
                     "eval",
                     "isFinite",
                     "isNaN",
                     "parseFloat",
                     "parseInt",
                     "decodeURI",
                     "decodeURIComponent",
                     "encodeURI",
                     "encodeURIComponent",
                     "escape",
                     "unescape",
                     "Math",
                     "Atomics",
                     "JSON",
                     "Reflect",
                     "globalThis",
                     "Intl",
                     "BigInt",
                     "WebAssembly",
                     "Module",
                     "Instance",
                     "Memory",
                     "Table",
                     "CompileError",
                     "LinkError",
                     "RuntimeError",
                     "Infinity",
                     "NaN",
                     "Symbol",
                     "console",
                     "printErr",
                     "write",
                     "performance",
                     "setTimeout",
                     "Worker",
                     "optimizefunctiononnextcall",
                     "preparefunctionforoptimization",
                     "isconcurrentrecompilationsupported",
                     "clearfunctionfeedback",
                     "optimizeosr",
                     "undefined",
                     "true",
                     "false",
                     "arguments",
                     "constructor",
                     "arraybufferneuter",
                     "simulatenewspacefull",
                     "null",
                     "gc",
                     "print",
                     "isbeinginterpreted",
                     "of",
                     "arraybufferdetach",
                     "unblockconcurrentrecompilation",
                     "heapobjectverify",
                     "neveroptimizefunction",
                     "tostring",
                     "slow_sloppy_arguments_elements",
                     "valueof",
                     "then",
                     "getownpropertydescriptor",
                     "deleteproperty",
                     "setprototypeof",
                     "ownkeys",
                     "deoptimizenow",
                     "constructor",
                     "__proto__"]

    allowed_words2 = []
    for allowed_word in allowed_words:
        allowed_word = allowed_word.lower()
        if allowed_word not in allowed_words2:
            allowed_words2.append(allowed_word)
    allowed_words = allowed_words2

    tmp_ret = set()
    for part in parts:
        part = part.lower()
        if part == "":
            continue
        if "." in part:
            continue    # skip properties!
        if part in allowed_words:
            continue
        if part.startswith("var_") or part.startswith("func_") or part.startswith("cl_"):
            continue
        if part.isnumeric():
            continue
        if part.endswith("n"):
            part2 = part[:-1]
            if part2.isnumeric():
                continue
        if "e" in part:
            part2 = part.replace("e", "")
            if part2.isnumeric():
                continue
        if "0x" in part:
            part2 = part.replace("0x", "")
            part2 = part2.replace("a", "")
            part2 = part2.replace("b", "")
            part2 = part2.replace("c", "")
            part2 = part2.replace("d", "")
            part2 = part2.replace("e", "")
            part2 = part2.replace("f", "")
            part2 = part2.replace("n", "")   # they can also be big ints
            if part2.isnumeric() or part2 == "":
                continue
        if "0b" in part:
            part2 = part.replace("0b", "")
            part2 = part2.replace("n", "")   # they can also be big ints
            if part2.isnumeric():
                continue
        tmp_ret.add(part)

    return tmp_ret


def contains_only_valid_token_characters(token):
    for c in token:
        if c.isalnum() is False and c != "_":
            return False
    return True


def get_content_without_special_chars(content):
    # TODO: Note: I later added ' (single quot) and didn't test it afterwards
    # if it fails at some point it's maybe because of the added single quot!
    special_chars = "()\t,;={}[]/\\:.<@>!?&+-~'%$^*|\"`\n"   # important: Don't add "_" because "_" can also occur in a variable name
    # important: I replace special chars with a space instead of removing them to keep the same offsets
    content_test = content
    for char in special_chars:
        content_test = content_test.replace(char, " ")
    return content_test


# TODO: Combine this with get_content_without_special_chars()
def get_content_without_special_chars_exclude_dot(content, replace_char):
    special_chars = "()\t,;={}[]/\\:<@>'!?&+-~%$^*|\"`\n"   # important: Don't add "_" because "_" can also occur in a variable name
    # important: I replace special chars with a space instead of removing them to keep the same offsets
    content_test = content
    for char in special_chars:
        content_test = content_test.replace(char, replace_char)
    return content_test


def get_content_without_strings(content):
    for string_character in ['"', "'", "`"]:     # currently I don't try regex strings
        fixed_code = ""
        code_to_fix = content
        while True:
            index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code_to_fix, string_character)
            if index == -1:
                break
            rest = code_to_fix[index+1:]
            end_index = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, string_character)
            if end_index == -1:
                break
            fixed_code = fixed_code + code_to_fix[:index] + string_character+string_character
            code_to_fix = code_to_fix[index+1+1+end_index:]
        content = fixed_code + code_to_fix
    return content


# datatype string must start with capital letter
# e.g. "DataView" is correct but "dataview" or "Dataview" is not correct
def get_code_to_create_variable_of_datatype(datatype_string):
    if datatype_string == "DataView":
        return "new DataView(new ArrayBuffer)"
    elif datatype_string == "Proxy":
        return "new Proxy({},{})"
    elif datatype_string == "Worker":
        return "new Worker(\"\", {type: 'string'})"
    elif datatype_string == "BigInt":
        return "BigInt(0)"
    elif datatype_string == "Promise":
        return "new Promise(function() {})"
    elif datatype_string == "Symbol":
        return "Symbol.for('')"  # or: Symbol("")
    elif datatype_string == "Intl.Locale":
        return "new Intl.Locale('en-US')"
    elif datatype_string == "WebAssembly.Table":
        return "new WebAssembly.Table({element: \"anyfunc\", initial: 1})"
    elif datatype_string == "WebAssembly.Module":
        return "new WebAssembly.Module(new Uint8Array([0x00,0x61,0x73,0x6d,0x01,0x00,0x00,0x00]))"
    elif datatype_string == "WebAssembly.Instance":
        return "new WebAssembly.Instance(new WebAssembly.Module(new Uint8Array([0x00,0x61,0x73,0x6d,0x01,0x00,0x00,0x00])))"
    elif datatype_string == "WebAssembly.Memory":
        return "new WebAssembly.Memory({initial:10, maximum:100})"
    elif datatype_string == "null":
        return "null"
    elif datatype_string == "globalThis":
        return "globalThis"
    elif datatype_string == "Math":
        return "Math"
    elif datatype_string == "JSON":
        return "JSON"
    elif datatype_string == "Intl":
        return "Intl"
    elif datatype_string == "WebAssembly":
        return "WebAssembly"
    elif datatype_string == "Reflect":
        return "Reflect"
    elif datatype_string == "Atomics":
        return "Atomics"
    else:
        # All other variables don't need arguments to be instantiated!
        return "new %s" % datatype_string


# The following functions just search until they don't find a new variable
# This should be safe for all corpus files
# But e.g. if a testcase contains "var_1_" and "var_3_" but no "var_2_"
# The code would stop after "var_1_" and would just say there is only 1 variable
# This is OK if the function is used during corpus generation, but during fuzzing
# I'm using a safe version with "_all" added to the name, e.g.:
# get_number_variables_all()
# EDIT:
# As it turned out, it's always unsafe to use this version because it can happen
# that I have a testcase with "var_1_" and "var_3_" but not "var_2_"
# The testcase minimizer should ensure that this doesn't happen, but if renaming
# var_3_ to var_2_ leads to a testcase which doesn't trigger the required coverage anymore
# then renaming doesn't happen.
def get_number_variables(code):
    return get_number_token_occurrences("var_%d_", code)


def get_number_functions(code):
    return get_number_token_occurrences("func_%d_", code)


def get_number_classes(code):
    return get_number_token_occurrences("cl_%d_", code)


# Token must contain %d for the index
def get_number_token_occurrences(token, code):
    idx = 1
    while True:
        token_name = token % idx
        if token_name not in code:
            break
        idx += 1
    return idx-1


# If a testcase contains "var_1_" and "var_3_" and "var_4_" but no "var_2_"
# This version of the function would return 4 because "var_4_" is the last used variable
# Note: It doesn't return 3 although there are just 3 variables in use.
# But that's not a problem because the fuzzer can itself detect that there is no "var_2_" because
# there is no entry in the variable_types. So when the fuzzer later needs to create new variables
# it knows it can use "var_2_"
def get_number_variables_all(code):
    return get_number_token_occurrences_all("var_%d_", code)


def get_number_functions_all(code):
    return get_number_token_occurrences_all("func_%d_", code)


def get_number_classes_all(code):
    return get_number_token_occurrences_all("cl_%d_", code)


# Token must contain %d for the index
def get_number_token_occurrences_all(token, code):
    idx = 0
    last_found = 0
    current_attempt = 0
    max_attempts = 100
    while True:
        token_name = token % idx
        current_attempt += 1
        if token_name not in code:
            if current_attempt > max_attempts:
                break
        else:
            last_found = idx
            current_attempt = 0
        idx += 1
    return last_found



def convert_datatype_str_to_real_JS_datatype(datatype_str):
    global mapping_lower_datatype_to_real_datatype
    if datatype_str in mapping_lower_datatype_to_real_datatype:
        return mapping_lower_datatype_to_real_datatype[datatype_str]
    else:
        return None



def get_all_variable_types_lower_case_which_I_can_currently_instantiate():
    global all_variable_types_lower_case_which_I_can_currently_instantiate
    return all_variable_types_lower_case_which_I_can_currently_instantiate


def get_random_variable_type_lower_case_which_I_can_currently_instantiate():
    available_variable_types = get_all_variable_types_lower_case_which_I_can_currently_instantiate()
    random_data_type = utils.get_random_entry(available_variable_types)
    return random_data_type


# Note: This function creates a variable in a SAFE way
# It's intention is not to fuzz the variable creation
# Instead, the intention is that code with a very high success rate is created
# Other mutations require the creation of a variable of a specific data type
# and call therefore this function
# => I want to ensure here a high success rate so that other mutations also have a high success rate
# Maybe I will later add code which fuzzes variable creation (but I don't see a lot of use for this at the moment)
# My goal: Success rate of at least 95% when this function is invoked without other mutations on the testcase
def get_code_to_create_random_variable_with_datatype(datatype_lower_string, state, line_number):
    # datatype_string = js_helpers.convert_datatype_str_to_real_JS_datatype(datatype_lower_string)
    typed_arrays = ["int8array", "uint8array", "uint8clampedarray", "int16array", "uint16array", "int32array",
                    "uint32array", "float32array", "float64array", "bigint64array", "biguint64array"]

    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE1)

    if datatype_lower_string == "string":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_STRING)
        ret_string = js.get_str()
        return ret_string
    elif datatype_lower_string == "array":
        # TODO also make as array available with length.....
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_ARRAY)
        return js.get_array()
    elif datatype_lower_string == "symbol":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL)

        prefix_code = ""

        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL2)
        prefix_code = "Symbol.for("
        suffix_code = ")"

        # Edit: I removed this code which was executed 50% of the time instead of Symbol.for()
        # => This lead in 23% of cases to a timeout (I dont really know why)
        # tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL3)
        # prefix_code = "Symbol("
        # suffix_code = ")"
        selection = utils.get_random_int(1, 3)
        if selection == 1:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL4)
            available_symbols = ["Symbol.iterator", "Symbol.toPrimitive", "Symbol.species", "Symbol.hasInstance",
                                 "Symbol.asyncIterator", "Symbol.matchAll", "Symbol.toStringTag", "Symbol.split",
                                 "Symbol.search", "Symbol.replace", "Symbol.match", "Symbol.isConcatSpreadable",
                                 "Symbol.unscopables"]
            return utils.get_random_entry(available_symbols)
        elif selection == 2:
            # Maybe some interesting cases:

            # Symbol.for(-0) vs. Symbol.for(0)
            # => they are both the same

            # But: Symbol.for(-1) vs. Symbol.for(1)
            # => they are different
            # so maybe there is a bug if I'm using Symbol.for(-0) and Symbol.for(0)

            # And Symbol.for("-0") can create -0
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL5)
            available_symbols = ["true", "false", "Symbol", "-0", "0", "0n", '"0"', '"-0"', "null", "-null",
                                 "undefined", "Object", "Object.prototype"]
            random_entry = utils.get_random_entry(available_symbols)
            return prefix_code + random_entry + suffix_code
        elif selection == 3:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL6)
            available_variables = testcase_mutators_helpers.get_all_available_variables(state, line_number)
            random_code = js.get_random_js_thing(available_variables, state, line_number)
            return prefix_code + random_code + suffix_code

    elif datatype_lower_string in typed_arrays:
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY)
        datatype = convert_datatype_str_to_real_JS_datatype(datatype_lower_string)

        if utils.likely(0.05):
            # Create it from a typed array
            # This should not be too likely, otherwise It will lead to endless loops
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY2)
            other_typed_array_datatype_lower = utils.get_random_entry(typed_arrays)
            code_to_create_a_typed_array = get_code_to_create_random_variable_with_datatype(
                other_typed_array_datatype_lower, state, line_number)
            return "new %s(%s)" % (datatype, code_to_create_a_typed_array)

        selection = utils.get_random_int(1, 3)
        if selection == 1:
            # Create it from length
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY3)
            random_length = js.get_int_for_length_value()
            return "new %s(%s)" % (datatype, random_length)
        elif selection == 2:
            # Create it from an array buffer

            # Don't recursively add code to create array buffers:
            # Reason: Array buffer must have a specific length, otherwise it leads to an exception
            # code_to_create_array_buffer = get_code_to_create_random_variable_with_datatype("arraybuffer", state, line_number)
            random_length = str(
                int(js.get_int_for_length_value(), 10) * 8)  # multiple with 8 to ensure it's a valid length value
            code_to_create_array_buffer = "new ArrayBuffer(%s)" % random_length

            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY5)
            return "new %s(%s)" % (datatype, code_to_create_array_buffer)

            # With arguments I must carefully choose the args, otherwise it can quickly lead to exceptions
            # => I'm currently not supporting this
            # if utils.likely(0.5):
            #    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY4)
            #    # With 2 args
            #    arg1 = js.get_int_for_length_value()
            #    arg2 = js.get_int_for_length_value()
            #    return "new %s(%s,%s,%s)" % (datatype, code_to_create_array_buffer, arg1, arg2)
            # else:
            #    # Without args
            #    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY5)
            #    return "new %s(%s)" % (datatype, code_to_create_array_buffer)
        elif selection == 3:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY6)
            available_variables = testcase_mutators_helpers.get_all_available_variables(state, line_number)
            random_code = js.get_random_js_thing(available_variables, state, line_number)
            return "new %s(%s)" % (datatype, random_code)
        # TODO: Create it from an available typed array variable!
        # TODO: Create it from an available arraybuffer variable!
    elif datatype_lower_string == "set":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET)
        if utils.likely(0.3):
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET2)
            return "new Set()"
        else:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET3)
            code_to_create_array = get_code_to_create_random_variable_with_datatype("array", state, line_number)
            return "new Set(%s)" % code_to_create_array

    elif datatype_lower_string == "weakset":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_WEAKSET)
        return "new WeakSet()"

    elif datatype_lower_string == "map":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_MAP)
        # TODO: It would be possible to return something like:
        # new Map([['key1', 'value1'], ['key2', 'value2']])
        return "new Map()"

    elif datatype_lower_string == "weakmap":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_WEAKMAP)
        return "new WeakMap()"

    elif datatype_lower_string == "regexp":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REGEXP)
        return "new RegExp()"  # TODO

    elif datatype_lower_string == "arraybuffer":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_ARRAYBUFFER)
        random_length = js.get_int_for_length_value()
        return "new ArrayBuffer(%s)" % random_length

    elif datatype_lower_string == "sharedarraybuffer":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SHAREDARRAYBUFFER)
        random_length = js.get_int_for_length_value()
        return "new SharedArrayBuffer(%s)" % random_length

    elif datatype_lower_string == "dataview":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW)
        # DataView
        # TODO: I can also use an available variable of type arraybuffer or sharedarraybuffer if there is one in the target line
        selection = utils.get_random_int(1, 2)
        if selection == 1:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW2)
            arg_str = get_code_to_create_random_variable_with_datatype("arraybuffer", state, line_number)
        else:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW3)
            arg_str = get_code_to_create_random_variable_with_datatype("sharedarraybuffer", state, line_number)
        return "new DataView(%s)" % arg_str

    elif datatype_lower_string == "promise":
        # TODO: Later maybe return some other functions, but the functions should accept 2 arguments...
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_PROMISE)
        return "new Promise(function() {})"

    elif datatype_lower_string == "intl.collator":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR)
        language_codes = ["ar", "bg", "ca", "zh-Hans", "cs", "da", "de", "el", "en", "es", "fi", "fr", "he", "hu", "is",
                          "it", "ja", "ko", "nl", "no", "pl", "pt", "rm", "ro", "ru", "hr", "sk", "sq", "sv", "th",
                          "tr", "ur", "id", "uk", "be", "sl", "et", "lv", "lt", "tg", "fa", "vi", "hy", "az", "eu",
                          "hsb", "mk", "tn", "xh", "zu", "af", "ka", "fo", "hi", "mt", "se", "ga", "ms", "kk", "ky",
                          "sw", "tk", "uz", "tt", "bn", "pa", "gu", "or", "ta", "te", "kn", "ml", "as", "mr", "sa",
                          "mn", "bo", "cy", "km", "lo", "gl", "kok", "syr", "si", "iu", "am", "tzm", "ne", "fy", "ps",
                          "fil", "dv", "ha", "yo", "quz", "nso", "ba", "lb", "kl", "ig", "ii", "arn", "moh", "br", "ug",
                          "mi", "oc", "co", "gsw", "sah", "qut", "rw", "wo", "prs", "gd"]
        random_language = utils.get_random_entry(language_codes)

        if utils.likely(0.5):
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR2)
            # sometimes use the unicode extension
            co_values = ["big5han", "dict", "direct", "ducet", "gb2312", "phonebk", "phonetic", "pinyin", "reformed",
                         "searchjl", "stroke", "trad", "unihan"]
            kn_values = ["true", "false"]
            kf_values = ["upper", "lower", "false"]
            random_language += "-u-co-"
            random_language += utils.get_random_entry(co_values)
            random_language += "-kn-"
            random_language += utils.get_random_entry(kn_values)
            random_language += "-kf-"
            random_language += utils.get_random_entry(kf_values)

        arg = ""
        if utils.likely(0.5):
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR3)
            # add an objects object
            arg += ", {"
            localeMatcher_values = ["lookup", "best fit"]
            usage_values = ["sort", "search"]
            sensitivity_values = ["base", "accent", "case", "variant"]
            ignorePunctuation_values = ["true", "false"]
            numeric_values = ["true", "false"]
            caseFirst_values = ["upper", "lower", "false"]

            arg += "localeMatcher: '%s'," % utils.get_random_entry(localeMatcher_values)
            arg += "usage: '%s'," % utils.get_random_entry(usage_values)
            arg += "sensitivity: '%s'," % utils.get_random_entry(sensitivity_values)
            arg += "ignorePunctuation: %s," % utils.get_random_entry(ignorePunctuation_values)
            arg += "numeric: %s," % utils.get_random_entry(numeric_values)
            arg += "caseFirst: '%s'" % utils.get_random_entry(caseFirst_values)
            arg += " }"
        return "new Intl.Collator('%s'%s)" % (random_language, arg)

    elif datatype_lower_string == "intl.datetimeformat":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_DATETIMEFORMAT)
        return "new Intl.DateTimeFormat()"  # TODO

    elif datatype_lower_string == "intl.listformat":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_LISTFORMAT)
        return "new Intl.ListFormat()"  # TODO

    elif datatype_lower_string == "intl.numberformat":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_NUMBERFORMAT)
        return "new Intl.NumberFormat()"  # TODO

    elif datatype_lower_string == "intl.pluralrules":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_PLURALRULES)
        return "new Intl.PluralRules()"  # TODO

    elif datatype_lower_string == "intl.relativetimeformat":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_RELATIVETIMEFORMAT)
        return "new Intl.RelativeTimeFormat()"  # TODO

    elif datatype_lower_string == "intl.locale":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_LOCALE)
        language_codes = ["ar", "bg", "ca", "zh-Hans", "cs", "da", "de", "el", "en", "es", "fi", "fr", "he", "hu", "is",
                          "it", "ja", "ko", "nl", "no", "pl", "pt", "rm", "ro", "ru", "hr", "sk", "sq", "sv", "th",
                          "tr", "ur", "id", "uk", "be", "sl", "et", "lv", "lt", "tg", "fa", "vi", "hy", "az", "eu",
                          "hsb", "mk", "tn", "xh", "zu", "af", "ka", "fo", "hi", "mt", "se", "ga", "ms", "kk", "ky",
                          "sw", "tk", "uz", "tt", "bn", "pa", "gu", "or", "ta", "te", "kn", "ml", "as", "mr", "sa",
                          "mn", "bo", "cy", "km", "lo", "gl", "kok", "syr", "si", "iu", "am", "tzm", "ne", "fy", "ps",
                          "fil", "dv", "ha", "yo", "quz", "nso", "ba", "lb", "kl", "ig", "ii", "arn", "moh", "br", "ug",
                          "mi", "oc", "co", "gsw", "sah", "qut", "rw", "wo", "prs", "gd"]
        random_language = utils.get_random_entry(language_codes)
        return "new Intl.Locale('%s')" % random_language

    elif datatype_lower_string == "date":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATE)
        return "new Date()"

    elif datatype_lower_string == "object1":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT)
        # Object
        selection = utils.get_random_int(1, 3)
        if selection == 1:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT1)
            return "{}"
        elif selection == 2:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT2)
            global_objects = ["Math", "Atomics", "JSON", "Reflect", "globalThis", "Intl", "BigInt"]
            return utils.get_random_entry(global_objects)
        elif selection == 3:
            available_variables = testcase_mutators_helpers.get_all_available_variables(state, line_number)
            if len(available_variables) == 0:
                tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT3)
                return "{}"
            else:
                tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT4)
                return utils.get_random_entry(available_variables)
    elif datatype_lower_string == "real_number":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER)
        selection = utils.get_random_int(1, 3)
        if selection == 1:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER2)
            random_value = js.get_int()
        elif selection == 2:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER3)
            random_value = js.get_double()
        else:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER4)
            random_value = js.get_special_value()
        # if utils.likely(0.5):
        #    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER5)
        #    (random_value, prefix) = decompose_number(random_value)
        # TODO: => I currently don't support adding the prefix....
        return "new Number(%s)" % random_value
    elif datatype_lower_string == "function":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION)

        # TODO return something like Math.abs ,  ... ?
        # Return available functions in the current testcase
        # Return a variable of data type function...
        selection = utils.get_random_int(1, 2)
        if selection == 1:
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION2)
            return "new Function()"
        elif selection == 2:
            if state.number_functions == 0:
                tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION3)
                return "new Function()"
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION4)
            random_function_number = utils.get_random_int(1, state.number_functions)
            return "func_%d_" % random_function_number

    elif datatype_lower_string == "boolean":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BOOLEAN)
        # TODO: Implement some logic based on available variables combined with & | ! ...
        # including "instanceof" , "typeof", ...
        selection = utils.get_random_int(1, 2)
        if selection == 1:
            return "new Boolean(true)"
        else:
            return "new Boolean(false)"
    elif datatype_lower_string == "bigint":
        tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT)
        random_value = js.get_int()
        tmp = ""
        if utils.likely(0.5):
            # Return something like: BigInt(1337)

            # if utils.likely(0.5):
            #    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT2)
            #    (random_value, prefix) = decompose_number(random_value)
            #    TODO: I currently don't support the prefix
            # else:
            #    pass # don't decompose
            #    tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT3)
            #    print("2")
            tmp = "BigInt(%s)" % random_value
        else:
            # Return something like 1337n
            tagging.add_tag(Tag.GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT4)
            tmp = random_value + "n"
        return tmp
    else:
        utils.perror(
            "Error in get_code_to_create_random_variable_with_datatype(), data type: %s" % datatype_lower_string)
    utils.perror("This line should not be reached in get_code_to_create_random_variable_with_datatype()")
