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



# JavaScript related functions used for fuzzing.
# TODO: Refactor code

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import utils
import config as cfg
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import pickle
import random

import mutators.database_operations as database_operations
import javascript.js_helpers as js_helpers


# Don't remove these 3 variables, they are in-use
# TODO: They are used by the helper functions which are not in this script.. I must really refactor this code
global_properties = dict()
global_methods = dict()
global_not_accessible_properties = dict()


mapping_variable_to_type = dict()
database_strings = []
database_numbers = []
instanceable_objects_list = []

# Number of occurrences in this list determines how often the operator is used
# e.g. "**" is not used too often
js_math_operations = ["+", "-", "*", "/", "%", "<<", ">>", "&&", "||", ">>>", "&", "|", "^", "+", "-", "*", "/", "%",
                      "<<", ">>", "&&", "||", ">>>", "&", "|", "^", "+", "-", "*", "/", "%", "<<", ">>", "&&", "||",
                      ">>>", "&", "|", "^", "**"]
js_math_assignment_operations = ["+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "&&=", "||=", "^=", ">>>=",
                                 "+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "&&=", "||=", "^=", ">>>=",
                                 "+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "&&=", "||=", "^=", ">>>=",
                                 "**="]
js_boolean_operators = ["||", "&&", "^", "&", "|", "+", "-", "<", ">", ">>", "<<", ">>>"]

# Hint: Don't add "+" or "-" here
# Reason: at the moment I add them also multiple times sometimes
# which is valid for "!" and "~", e.g. "!!!~!!~~~!false" is valid code
# and "+true" is valid, but "++true" is not valid!
js_boolean_single_operators = ["!", "~"]


possible_chars_without_whitespace = ["1", "A", "a", "ß", "#", "ı",
                                     '\u1d2e',
                                     '\ufb03',
                                     '\ufb06',
                                     '\u212A',
                                     "İ",
                                     '\uff1f',
                                     "?",
                                     '\uff06',
                                     '\u017f',  # calling .toUpperCase results in "S"
                                     '\uff0f',  # unicode forward slash /
                                     '\uff89',  # unicode forward slash /
                                     '\u2032',  # unicode ' character
                                     '\u03c3',  # unicode sigma becomes small s
                                     '\ufe64',  # unicode becomes <   => e.g. maybe I can use it for <script> ?
                                     '\ufffd',  # unicode
                                     '\ufffc',  # according to alex this can lead to a crash
                                     '\u0390',  # symbol which takes 3x more space when converted to upper case
                                     '\ufdfa',  # symbol which takes 18x more space when converted to upper case
                                     "▓",
                                     ".",

                                     "N̯̱̣͇̖̦̦̣ͥͮͩͪ̐͑͂̈̅ͦ͋̆̔͆̀̆̀̚̚̕",  # from raviramesh.info/mindset.html

                                     "﷽",  # from raviramesh.info/mindset.html
                                     "𒐫",  # from raviramesh.info/mindset.html
                                     "జ్ఞా",  # from raviramesh.info/mindset.html
                                     ]


# Hint: Don't add as whitespace character "\x0d" !
# This will lead to a lot of exceptions when a new string gets added because the 0x0d symbol will remove all
# previous code which means the creation code of a string will be flawed, e.g. instead of:
# var var_1_ = "someString*\x0d*blabla"
# This code will be created:
# blabla"
# => which leads to an exception
possible_chars_whitespace = ["\x20", '\u200b', '\u115f', '\u3000', '\u2004', '\u3164', "\x09", "\u180E", '\u202e']
# "\x00" => TODO For the moment I removed the null-byte because the Python->C code can't handle a null-byte.. (or I don't know how to do this?)
# "\x0a" => TODO: In a string this is bad because it would wrap the string value to the next line which breaks my current logic (e.g: when I duplicate a line to the next line I get invalid code)
possible_chars_all = possible_chars_without_whitespace + possible_chars_whitespace


possible_interesting_integers = [
    -0, 0, 1,
    0xff, 0xff - 1, 0x400, 0x400 - 1, 0x1000, 0x1000 - 1, 0x10000, 0x10000 - 1,
    -2147483648,  # int32_t min
    2147483647,  # int32_t max
    4294967295,  # uint32_t max
    9007199254740991,  # Number.MAX_SAFE_INTEGER
    -9007199254740991,  # Number.MIN_SAFE_INTEGER
    2147483648,  # var FLT_SIGNBIT  = 0b10000000000000000000000000000000;
    2139095040,  # var FLT_EXPONENT = 0b01111111100000000000000000000000;
    8388607,  # var FLT_MANTISSA = 0B00000000011111111111111111111111;
]

possible_interesting_floating_points = ["0.2", "0.4", "1.23e+5", "123.456",
                                        "2.3023e-320",  # CVE-2018-0953
                                        "-5.3049894784e-314",  # CVE-2018-0953
                                        "3.54484805889626e-310",
                                        "2130562.5098039214",  # CVE-2019-8506
                                        "Number.EPSILON",
                                        "Math.PI",
                                        "Number.MAX_VALUE",
                                        "Number.MAX_VALUE*-1",
                                        "Number.MIN_VALUE",
                                        "Number.MIN_VALUE*-1",
                                        "Math.E",
                                        "Math.E*-1",
                                        "Math.LN10",
                                        "Math.LOG2E",
                                        ]

possible_interesting_special_values = ["null",
                                       "undefined",
                                       "Number.NaN",
                                       "Number.MIN_VALUE",
                                       "Number.MAX_VALUE",
                                       "Number.MAX_VALUE*-1",
                                       "Number.MIN_VALUE*-1",
                                       "Number.POSITIVE_INFINITY",
                                       "Number.NEGATIVE_INFINITY",
                                       "NaN",
                                       "Infinity",
                                       "Number.EPSILON",
                                       "Number.MAX_SAFE_INTEGER",
                                       "Number.MIN_SAFE_INTEGER",
                                       "Math.PI",
                                       "-s_0b",  # different form of writing NaN
                                       "Infinity/(Infinity/Infinity | 1-1)",  # Infinity
                                       "Infinity/(Infinity/Infinity | 1-2)",  # -Infinity
                                       "Math.abs(-1.7976931348623158e+308)",
                                       # result will be: 1.7976931348623157e+308 AND NOT 1.7976931348623158e+308
                                       "1.7976931348623158e+308",  # same for this=> 1.7976931348623157e+308
                                       "(+Infinity+-Infinity)",
                                       # two integer types added together result in a non-integer type NaN
                                       "(-Infinity- -Infinity)",  # results in NaN
                                       "(-Infinity* -0)",  # results in NaN
                                       "(Infinity*0)",  # results in NaN
                                       "-2147483648/-1",
                                       "-9223372036854775808/-1",
                                       ]


# Some other ways can also be found in the "decompose_number()" function
possibilities_to_write_minus_zero = [
    "-new Number(-new Number(+new Number(-new Number(0-0))))",  # different form of writing -0
    "Math.round(-0.1)",
    "Math.ceil(-0.1)",
    "Math.expm1(-0)",
    "Math.trunc(-0)",
    "Math.sign(-0)",
    "Math.sin(-0)",
    "Math.asin(-0)",
    "Math.asinh(-0)",
    "Math.atan(-0)",
    "Math.atanh(-0)",
    "Math.sqrt(-0)",
    "Math.atan2(-0,1)",
    "Math.atan2(-2, +Infinity)",
    "Math.floor(-0)",
    "Math.cbrt(-0)",
    "Math.fround(-0)",
    "Math.max(-0,-0)",
    "Math.min(-0,-0)",
    "Math.pow(-0,1)",
    "Math.log1p(-0)",
    "Number.parseInt(\"-0\")",
    "-(NaN >>> 0)",
    "-(-0>>>1)",
    "new Number(-0).valueOf()",
    "Number.parseFloat(\"-0\")",
    "Number(\"-0\")",
    "-0.0e+0",
    "-0.0e+1337",
    "-0x0_0",
    "-0b0_0_0_0",
    "-(((0)))",
    "(-0-0)",
    "-(30 & -0)",
    "-(+30 & +0)",
    "0*-1",
    "1/-Infinity",
    "-1/Infinity",
    "Math.PI/(Infinity*-Infinity)",
    "-((Infinity*-Infinity) << Infinity)",
    "(NaN >>> NaN)*-1",
    "-(-1-0+1)-0",
    "(-0/1)",
    "(-0)**3",
    "(-Infinity)**-1",
    "-null",
    "-00",  # represented as octal
    "-0+-0",
    "-~(~undefined)",
    "1/(-0)**(-1)",
    "(-0 % 5)",
    "(-0 % Infinity)",
    "(-0 % -Infinity)",
    "((_ = -0) && -1*(_-1))",
    "((_ = -0) - -1*(_-1))",
    "((_ = -0) && (_ -= 0))",
    "((_ = -(1-1)) && (_ *= -0))",
    "(true ? -0: 1)",
    "(false ? 1: -0)",
    "(_ = _ = -0)",
    "-0.00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000001",
    "-1e-400",
    "(() => -0)()",
    "(await (async () => {return -0})())",
    "-~(5.6789 | 0xffffffff)",
    "(_ = 1, _ = 2, _ = -0)",
    "(_=[-0], _[0])"
    "(Math = -0)",
    "(Infinity = -0)",
    "(null ?? -0)",
    "(undefined ?? -0)",
    "(undefined||-0)",
    "(null||-0)",
    "(NaN = NaN = NaN = -0)",
    "[-0].pop()",
    "[-0].shift()",
    "[-0].reduce((a,b) => a+b)",
    "[-0].reduce(Object.valueOf)",
    "[-0].reduceRight(Object.valueOf)",
    "[-0].values().next().value",
    "(x=[-0],x[0])",
    "(function(){return -0})()",
    "(function(_){return _})(-0)",
    "(function foo(){return foo.arguments[0]})(-0)",
    "(Object.defineProperty(Math.pow, \"length\", {value: -0,writable: true}), Math.pow.length)",
    "(tmp=null,tmp||=-0)",  # some new functionality
    "(tmp=null,tmp??=-0)",  # some new functionality
    "(tmp=true,tmp&&=-0)",  # some new functionality
    "-0.0_0",  # some new functionality
    "-parseInt(-0n)",  # maybe they think "-" and "-" can't result in a negative number?
    "-Number(-0n)",  # maybe they think "-" and "-" can't result in a negative number?
    "(-~(~(-0)))",  # maybe they think "-" and "-" can't result in a negative number?
    "(parseInt=-0,parseInt)",
    "(1,-0)",
]
possible_interesting_special_values.extend(possibilities_to_write_minus_zero)

possible_length_values = []
for i in range(1, 14 + 1):
    possible_length_values.append(2 ** i)
    possible_length_values.append((2 ** i) - 1)

possible_length_values_short = []
for i in range(1, 9 + 1):
    possible_length_values_short.append(2 ** i)
    possible_length_values_short.append((2 ** i) - 1)

possible_boundary_values = []
for i in range(1, 14 + 1):
    possible_boundary_values.append(2 ** i)

possible_big_boundary_values = []
for i in range(14 + 1, 18 + 1):
    possible_big_boundary_values.append(2 ** i)


# Return value is of type str and not a float (to not have precision problems because of python)
def get_interesting_floating_point():
    tmp = random.choice(possible_interesting_floating_points)
    return tmp


def get_max_js_number():
    return 9007199254740991


def get_min_js_number():
    return -9007199254740991


def get_interesting_integer():
    return random.choice(possible_interesting_integers)


def get_random_str(max_len=0, whitespace_allowed=True):
    while True:
        str_len = random.choice(possible_length_values)
        if max_len == 0:
            break  # no max length
        if str_len <= max_len:
            break  # strlen is good
    return get_random_str_with_length(str_len, whitespace_allowed)


# max 512 length
def get_random_str_short(whitespace_allowed=True):
    if utils.get_random_bool():
        str_len = random.choice(possible_length_values_short)
    else:
        str_len = utils.get_random_int(1, 512)
    return get_random_str_with_length(str_len, whitespace_allowed)


def get_random_str_with_length(str_len, whitespace_allowed=True):
    if whitespace_allowed:
        chars_to_use = possible_chars_all
    else:
        chars_to_use = possible_chars_without_whitespace

    char = random.choice(chars_to_use)

    if utils.get_random_bool():
        ret = char * str_len
    else:
        if str_len < 1000:  # for smaller than 1000 I create
            ret = ""
            ret_len = 0
            while ret_len != str_len:
                ret += random.choice(chars_to_use)
                ret_len += 1
        else:
            # randomly change some bytes
            number_modifications = utils.get_random_int(1, 20)
            ret = list(char * str_len)
            for i in range(number_modifications):
                random_idx = utils.get_random_int(0, str_len - 1)
                ret[random_idx] = random.choice(chars_to_use)
            ret = ''.join(ret)
    return ret


def load_pickle_databases():
    global database_strings, database_numbers

    if os.path.exists(cfg.pickle_database_path_strings) is False:
        utils.perror("[-] Strings pickle database file (%s) does not exist. Create it first by starting the fuzzer with the --extract_data numbers_and_strings argument!" % cfg.pickle_database_path_strings)
    if os.path.exists(cfg.pickle_database_path_numbers) is False:
        utils.perror("[-] Numbers pickle database file (%s) does not exist. Create it first by starting the fuzzer with the --extract_data numbers_and_strings argument!" % cfg.pickle_database_path_numbers)

    with open(cfg.pickle_database_path_strings, 'rb') as finput:
        database_strings = pickle.load(finput)
        database_strings = list(database_strings)
    with open(cfg.pickle_database_path_numbers, 'rb') as finput:
        database_numbers = pickle.load(finput)
        database_numbers = list(database_numbers)
    utils.msg("[i] Loaded %d numbers and %d strings from pickle database for fuzzing" % (len(database_numbers), len(database_strings)))


def get_random_number_from_database():
    global database_numbers
    if len(database_numbers) == 0:
        utils.perror("Number database is empty - this should never occur")
    return utils.get_random_entry(database_numbers)


def get_random_string_from_database():
    global database_strings
    if len(database_strings) == 0:
        utils.perror("String database is empty - this should never occur")
    return utils.get_random_entry(database_strings)


def get_str():
    # This function resulted in 18% of cases in an exception, so I'm tagging it to detect the problem
    tagging.add_tag(Tag.JS_GET_STRING1)

    if utils.likely(0.7):
        possible_chars = ["'", '"']  # "`"
        # todo maybe embed some variables in the template string with ` ?
        # todo: We can also create variables with 0x41 via str/string?
        content = get_random_str_short()
        char = random.choice(possible_chars)

        if char == "'":
            tagging.add_tag(Tag.JS_GET_STRING2)
        elif char == '"':
            tagging.add_tag(Tag.JS_GET_STRING3)
        else:
            tagging.add_tag(Tag.JS_GET_STRING4)

        if utils.likely(0.1):
            tagging.add_tag(Tag.JS_GET_STRING5)
            return "new String(" + char + content + char + ")"
        else:
            tagging.add_tag(Tag.JS_GET_STRING6)
            return char + content + char
    else:
        tagging.add_tag(Tag.JS_GET_STRING7)
        return get_random_string_from_database()


def set_possible_instanceable_objects(list_of_objs):
    global instanceable_objects_list
    instanceable_objects_list = list_of_objs


# Returns something like "+=" or "*="
def get_random_js_math_assignment_operation():
    global js_math_assignment_operations
    random_math_operation = utils.get_random_entry(js_math_assignment_operations)
    return random_math_operation


# Returns something like "+" or ">>>"
def get_random_js_math_operation():
    global js_math_operations
    random_math_operation = utils.get_random_entry(js_math_operations)
    return random_math_operation


def get_random_boolean_value(state, line_number):
    possibilities = ["new Boolean(true)", "new Boolean(false)", "true", "false"]
    for i in range(0, 10):
        possibilities.append("formula")

    selection = utils.get_random_entry(possibilities)
    if selection == "formula":
        return get_boolean_formula(state, line_number)
    else:
        return selection


def get_boolean_formula(state, line_number):
    available_variables = state.get_available_variables_in_line_with_datatypes(line_number, exclude_undefined=True)

    boolean_variables = set()
    number_variables = set()
    for variable_name in available_variables:
        variable_types = available_variables[variable_name]
        for variable_type in variable_types:
            if variable_type == "boolean":
                boolean_variables.add(variable_name)
            elif variable_type == "real_number" or variable_type == "special_number":
                number_variables.add(variable_name)

    if len(boolean_variables) != 0 and utils.likely(0.4):
        random_boolean_variable = utils.get_random_entry(boolean_variables)
        return random_boolean_variable

    if len(number_variables) != 0 and utils.likely(0.5):
        random_number_variable = utils.get_random_entry(number_variables)
        return random_number_variable

    # TODO create some random int / bool and create a formula with it?
    # TODO stuff like "x in array" ?
    return get_random_complex_boolean_formula(state, line_number, boolean_variables)


# Will return something like "&&" or "||"
def get_random_boolean_operator():
    global js_boolean_operators
    random_boolean_operator = utils.get_random_entry(js_boolean_operators)
    return random_boolean_operator


# Will return something like "!" or "~"
def get_random_single_boolean_operator():
    global js_boolean_single_operators
    random_boolean_single_operator = utils.get_random_entry(js_boolean_single_operators)
    return random_boolean_single_operator


def get_random_complex_boolean_formula(state, line_number, boolean_variables):
    number_of_operations = utils.get_random_int(1, 5)
    number_of_variables = utils.get_random_int(1, 2)

    operands = [""] * (number_of_operations + 1)  # if I have 1 operation I need 1+1=2 operands
    operators = [""] * number_of_operations

    if len(boolean_variables) != 0:
        for idx in range(0, number_of_variables):
            random_index = utils.get_random_int(0, number_of_operations)
            operands[random_index] = utils.get_random_entry(boolean_variables)

    for idx in range(0, number_of_operations + 1):
        if idx != number_of_operations:
            operators[idx] = get_random_boolean_operator()
        if operands[idx] is None:
            if utils.likely(0.5):
                operands[idx] = "true"
            else:
                operands[idx] = "false"

    # TODO: also add somewhere "(" and ")"?
    tmp_result = ""
    tmp_result += operands[0]
    for idx in range(0, number_of_operations):
        tmp_result += operators[idx]

        if utils.likely(0.3):
            # also add a single operator
            tmp_result += get_random_single_boolean_operator()
            if utils.likely(0.3):
                tmp_result += get_random_single_boolean_operator()
                if utils.likely(0.3):
                    tmp_result += get_random_single_boolean_operator()
        tmp_result += operands[idx + 1]

    return tmp_result


# Can return a str, obj, null, number, variable, ... anything
# TODO: When I call this function I have to always call get_all_available_variables() first to get >other_variables<
# => I should move this call into this function and just call it when it's really required...
def get_random_js_thing(other_variables, state, line_number):
    # TODO: Should I also return something like "super"? (>arguments< can already be returned via other_variables)

    # Please note that this function can also return obj properties:
    # e.g. if I assign "var_1_.abc = " then this function should also return var_1_.abc
    # => This is already implemented because >other_variables< now contains used properties or array entries

    # I'm using a list and not a random value between a range
    # because in the list I can add entries multiple times to increase likelihood
    tmp = [1, 2, 3, 4, 5, 6, 7, 7, 7, 8, 9, 10, 11]
    random_value = utils.get_random_entry(tmp)
    if random_value == 1:
        return get_str()
    elif random_value == 2:
        return get_int()
    elif random_value == 3:
        return get_double()
    elif random_value == 4:
        return get_special_value()
    elif random_value == 5:
        return get_array()
    elif random_value == 6:
        x = get_all_values_of_basic_types()
        y = utils.get_random_entry(x)
        if "PRINT_ID" in y:
            return get_int()  # don't return callback objects
        else:
            return y
    elif random_value == 7:
        # Return a variable
        if len(other_variables) == 0:
            return "null"
        else:
            return utils.get_random_entry(other_variables)
    elif random_value == 8:
        # Return a property of a variable

        # Example:
        # https://github.com/tunz/js-vuln-db/blob/master/v8/CVE-2016-5172.md
        # if (a1.length == a2) { b = "CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCAAAA"; }
        # The fuzzer should be able to return via "js.get_random_js_thing()" a code like the
        # "a1.length"

        # TODO maybe just call get_random_variable_operation() ?

        if utils.likely(0.7):
            if "this" in other_variables:
                other_variables.remove("this")
        if len(other_variables) == 0:
            return "null"
        else:
            random_variable = utils.get_random_entry(other_variables)

            if random_variable not in state.variable_types:
                return random_variable

            for entry in state.variable_types[random_variable]:
                (entry_line_number, variable_type) = entry
                if entry_line_number == line_number:
                    # I just take first entry here, however, a variable could have multiple data types in a line
                    # TODO maybe add code to handle this here
                    variable_type = js_helpers.convert_datatype_str_to_real_JS_datatype(variable_type)
                    # print("Variable type: %s" % variable_type)
                    if variable_type is None or variable_type not in database_operations.obj_properties:
                        return random_variable  # e.g. for datatypes like real_number, ..
                    properties = list(database_operations.obj_properties[variable_type])
                    properties_not_readable = list(database_operations.obj_not_accessible_properties[variable_type])

                    if utils.likely(0.8):  # proto is too common, so remove it sometimes
                        if "__proto__" in properties:
                            properties.remove("__proto__")

                    if len(properties) == 0 and len(properties_not_readable) == 0:
                        return random_variable
                    if utils.likely(0.1) and len(properties_not_readable) != 0:
                        random_property = utils.get_random_entry(properties_not_readable)
                    else:
                        if len(properties) == 0:
                            return random_variable
                        random_property = utils.get_random_entry(properties)
                    to_return = "%s.%s" % (random_variable, random_property)
                    return to_return
    elif random_value == 9:
        # random big int
        return "71748523475265n - 16n"  # TODO implement more complex versions
    elif random_value == 10:
        # return an object
        if utils.likely(0.2):
            return "this"  # ensure that "this" will also get returned
        else:
            if utils.likely(0.5):
                if utils.likely(0.8):
                    return "{length: %s}" % get_int()
                else:
                    # from https://github.com/tunz/js-vuln-db/blob/master/v8/CVE-2013-6632.md
                    return "{length: 0x24924925}"
            else:
                if utils.likely(0.5):
                    return "new Object()"
                else:
                    return "{}"
    elif random_value == 11:
        # random builtin classname
        builtin_classname = utils.get_random_entry(instanceable_objects_list)
        if builtin_classname == "DataView":
            return "new DataView(new ArrayBuffer)"
        elif builtin_classname == "Proxy":
            return "new Proxy({},{})"
        elif builtin_classname == "Worker":
            # No workers: They spawn a 2nd v8 process!
            # return "new Worker(\"\", {type: 'string'})"
            return "true"
        elif builtin_classname == "BigInt":
            return "BigInt(%s)" % get_int()
        else:
            return "new %s()" % builtin_classname
    else:
        # TODO also implement a function call or something similar?
        # maybe also a function call on a an available object in other_variables?
        # or a state modification?
        utils.perror("TODO implement")


def get_int_as_number():
    if utils.likely(0.65):
        if utils.likely(0.5):
            num = utils.get_random_int(-1, 100)  # a small value
        else:
            num = get_interesting_integer()
    else:
        if utils.likely(0.85):
            # create a boundary value like (2**10)-1
            if utils.likely(0.95):
                random_boundary_value = utils.get_random_entry(possible_boundary_values)
            else:
                # They can lead to very long loops and therefore I don't use the big values too often
                random_boundary_value = utils.get_random_entry(possible_big_boundary_values)
            random_offset = utils.get_random_entry(range(-20, 20, 1))
            num = random_boundary_value + random_offset
        else:
            # get a full random value
            if utils.likely(0.5):
                num = utils.get_random_int(-1, 100)  # a small value
            else:
                num = utils.get_random_int(get_min_js_number(), get_max_js_number())
    return num


def get_int():
    if utils.likely(0.9):
        num = get_int_as_number()
        return "%d" % num
    else:
        return get_random_number_from_database()


def get_int_for_length_value():
    if utils.likely(0.7):
        # Small length value
        num = utils.get_random_int(0, 10)
    else:
        # Bigger length value
        num = utils.get_random_int(11, 1024)
    return "%d" % num


def get_int_not_negative():
    random_int = get_int()
    if random_int.startswith("-"):
        random_int = random_int[1:]
    return random_int


def get_double():
    if utils.likely(0.8):
        val = get_interesting_floating_point()
    elif utils.likely(0.5):
        if utils.likely(0.2):
            # the next code is not 100% correct because min/max are from integers and not floats
            val = utils.get_random_float_as_str(get_min_js_number(), get_max_js_number())
        else:
            # The problem of the above if-true branch is that it creates so big values
            # that the stuff after the . is not used
            # e.g. stuff like -2868963459833638.00000000000000000000
            # Where everything after the dot is zero
            # I therefore use here smaller ranges and also more frequently
            # Because this should not execute so many iterations....
            val = utils.get_random_float_as_str(-2 ** 16, 2 ** 16)
    else:
        if utils.get_random_bool():
            val1 = get_interesting_floating_point()
        else:
            val1 = utils.get_random_float_as_str(get_min_js_number(), get_max_js_number())
        if utils.get_random_bool():
            val2 = get_interesting_floating_point()
        else:
            val2 = utils.get_random_float_as_str(get_min_js_number(), get_max_js_number())

        val = "parseInt(Math.round(Math.floor(%s/%s))) * %s" % (val1, val2, val2)
        # todo implement here other alternatives
    return val


def get_array():
    # TODO: maybe make the length of the array random?
    variation = utils.get_random_int(1, 21)
    if variation == 1:
        return '[1,2,3,4]'
    elif variation == 2:
        return '[1,,3,4]'  # holey
    elif variation == 3:
        return '[]'
    elif variation == 4:
        return '[{},{},{}]'
    elif variation == 5:
        return '[{},{},,{}]'
    elif variation == 6:
        return '[Math, JSON]'
    elif variation == 7:
        return '[1.1, 2.2, 3.3, 4.4, 5.5, 6.6, 7.7]'
    elif variation == 8:
        return '[1.1,, 3.3, 4.4, 5.5, 6.6, 7.7]'
    elif variation == 9:
        return '[1.1, 5, "foo", Math, {}, 5.5]'
    elif variation == 10:
        return '[[],[]]'
    elif variation == 11:
        return '[[],[],,[]]'
    elif variation == 12:
        return '[[],[],,{}]'
    elif variation == 13:
        return '[%s,%s]' % (get_int(), get_int())
    elif variation == 14:
        return '[%s,,%s]' % (get_int(), get_int())
    elif variation == 15:
        return '[%s,%s]' % (get_str(), get_str())
    elif variation == 16:
        return '[%s,,%s]' % (get_str(), get_str())
    elif variation == 17:
        return '[%s,%s]' % (get_double(), get_double())
    elif variation == 18:
        return '[%s,,%s]' % (get_double(), get_double())
    elif variation == 19:
        return '[%s,%s]' % (get_special_value(), get_special_value())
    elif variation == 20:
        return '[%s,,%s]' % (get_special_value(), get_special_value())
    elif variation == 21:
        # recursive call and add spread operator
        # e.g: [1,2,3,4] can be rewritten as [...[1,2,3,4]]
        return "[..." + get_array() + "]"
    else:
        utils.perror("internal error")


def get_special_value():
    # global possible_interesting_special_values
    return random.choice(possible_interesting_special_values)


def get_variable_prefix():
    return ["var ", "let ", "const ", ""]  # static


def get_values_of_basic_types():
    tmp = []
    tmp += ['', '0', '1', '-1', "'x'", 'true', '{}', '[]', 'undefined', "this", "new ArrayBuffer(10)"]
    tmp += ["function() {%s}" % get_js_print_identifier()]
    return tmp


def get_values_of_basic_types_with_callback_objs():
    tmp = []
    tmp += get_values_of_basic_types()
    tmp += [get_js_objs_with_callback_functions()[0], ]  # just the first object, otherwise we get too many entries
    return tmp


def get_js_objs_with_callback_functions():
    function_names = ["valueOf", "toJSON", "toISOString", "toArray", "toPrecision", "toFixed", "toExponential",
                      "isArray", "isInteger", "isNan", "toDateString", "toGMTString", "toLocaleDateString",
                      "toLocaleFormat", "toLocaleString", "toLocaleTimeString", "toSource", "toTimeString",
                      "toUTCString",
                      "get", "set", "has", "is", "values", "assign", "deleteProperty", "construct", "apply", "ownKeys",
                      "getOwnPropertyDescriptor",
                      "defineProperty", "getPrototypeOf", "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable",
                      "keys",
                      "setPrototypeOf", "isExtensible", "preventExtensions"]

    property_names = ["name", "length", "__proto__", "constructor"]
    code_print_identifier = get_js_print_identifier()

    objs = []
    # Don't change the order here! Keep this as the first object in the list (other code depends on this!)
    obj = "{\n"
    obj += """    toString: function () { 
            %s;
            return 42;
        },\n""".replace("%s", code_print_identifier)
    # toString returns a different objects, otherwise we could end up in an endless loop later (when I replace return value with tmpFuzzer)
    for function_name in function_names:
        obj += """    """ + function_name + """: function () { 
            %s;
            return "";
        },\n""".replace("%s", code_print_identifier)
    for property_name in property_names:
        obj += """    get """ + property_name + """() { 
            %s;
            return "";
        },\n""".replace("%s", code_print_identifier)
    obj += """    tmpFuzzer : 1337,\n"""  # This will later be replaced
    obj += "}"

    objs.append(obj)
    copy_of_obj = obj
    obj = obj.replace('return ""', "return this.tmpFuzzer")  # Now let's return the tmp property
    # And now lets modify the tmp property to be again an object with callback functions
    obj = obj.replace("1337", copy_of_obj)
    objs.append(obj)

    # https://www.ecma-international.org/ecma-262/#sec-well-known-symbols
    obj = "{\n"
    obj += """    [Symbol.toPrimitive](var_1_) { 
            if(var_1_ == "number") {
                %s;
                return 1;
            }
            else if (var_1_ == "string") {
                %s;
                return 1;
            }
            else {
                %s;
                return 1;
            }
        },
        [Symbol.hasInstance](var_2_) {
            %s;
            return true;
        },
        * [Symbol.matchAll](var_3_) {
            %s;
            yield 1;
            %s;
            yield 2;
            %s;
            yield 3;
            %s;
        },
        [Symbol.replace](var_4_) {
            %s;
            return 1;
        },
        [Symbol.search](var_5_) {
            %s;
            return 1;
        },
        [Symbol.species]() {
            %s;
            return Array;
        },
        [Symbol.split](var_6_) {
            %s;
            return 1;
        },
        get [Symbol.toStringTag]() {
            %s;
            return 1;    
        },
        * [Symbol.iterator]() {
            %s;
            yield 1;
            %s;
            yield 2;
            %s;
            yield 3;
            %s;
        },
        async* [Symbol.asyncIterator]() {
                %s;
                yield 1;
                %s;
                yield 2;
                %s;
                yield 3;
                %s;
                return 1;
            },\n""".replace("%s", code_print_identifier)
    for property_name in property_names:
        obj += """    get """ + property_name + """() { 
            %s;
            return "";
        },\n""".replace("%s", code_print_identifier)
    obj += """    tmpFuzzer : 1337,\n"""  # This will later be replaced
    obj += "}"

    objs.append(obj)
    copy_of_obj_with_symbols = obj
    obj = obj.replace('return ""', "return this.tmpFuzzer")  # Now let's return the tmp property
    obj = obj.replace('return 1', "return this.tmpFuzzer")  # Now let's return the tmp property
    obj = obj.replace('yield 1', "yield this.tmpFuzzer")  # Now let's return the tmp property
    # And now lets modify the tmp property to be again an object with callback functions
    obj = obj.replace("1337", copy_of_obj_with_symbols)
    objs.append(obj)

    # Now one which just yields another value the 2nd time
    obj = copy_of_obj_with_symbols
    obj = obj.replace('yield 2', "yield this.tmpFuzzer")
    obj = obj.replace("1337", copy_of_obj_with_symbols)
    objs.append(obj)

    # Now one which returns the first object with normal callbacks (without symbols)
    obj = copy_of_obj_with_symbols
    obj = obj.replace('return ""', "return this.tmpFuzzer")
    obj = obj.replace('return 1', "return this.tmpFuzzer")
    obj = obj.replace('yield 1', "yield this.tmpFuzzer")
    obj = obj.replace("1337", copy_of_obj)
    objs.append(obj)

    # And now one without symbols which returns one with symbols
    obj = copy_of_obj
    obj = obj.replace('return ""', "return this.tmpFuzzer")
    obj = obj.replace("1337", copy_of_obj_with_symbols)
    objs.append(obj)

    obj = copy_of_obj
    obj = obj.replace('return ""', "return this.tmpFuzzer")
    obj = obj.replace('return 42', "return this.tmpFuzzer")
    obj = obj.replace("1337", copy_of_obj_with_symbols)
    objs.append(obj)

    return objs


def get_all_values_of_basic_types():
    tmp = []
    tmp += ["1", "-1", "0", "-0"]  # Numbers
    tmp += ["1.1", "9007199254740992", "9007199254740993"]  # 9007199254740993 will be represented as 9007199254740992
    tmp += ["0b0101101", "0b0101012", "050", "0xf"]
    tmp += ["[]", "{}"]  # objects
    tmp += ["[[[]],[[[]]]", "[[[]],,[[[]]]"]
    tmp += ["true", "false"]
    tmp += ["new ArrayBuffer(10)", ]
    tmp += ['']
    tmp += ["'x'", '"x"']
    tmp += ["this", "this.source"]
    tmp += ["`x`", """`x${this}y`"""]
    tmp += [
        "function() {%s}" % get_js_print_identifier()]  # Just using get_js_print_identifier() print here without wrapping it inside a function would spray the corpus
    # tmp += specials
    # possible_interesting_special_values
    tmp += [get_js_objs_with_callback_functions()[0], ]
    tmp += ["-1e12", "-1e9", "-1e6", "-1e3", "-5.0", "-4.0", "-3.0", "-2.0", "-1.0"]
    tmp += ["-0.0", "0.0", "1.0", "2.0", "1e3", "1e6", "1e9", "1e12"]
    return tmp


def get_other():
    tmp = []
    tmp += ["delete this", "gc()", "try {} catch (e) {}", '"use asm"', '"use strict"', 'eval("")']
    return tmp


def get_js_print_identifier():
    # Should be something like:
    # fuzzilli('FUZZILLI_PRINT', '_PRINT_ID_')
    return cfg.v8_print_js_codeline


def get_code_to_extract_globals():
    tmp = ""
    tmp += "var var_1_ = Object.getOwnPropertyNames(this);\n"
    tmp += get_js_code_to_print("(JSON.stringify({globals: var_1_}))")
    return tmp


def get_js_code_to_print(variable_to_print):
    tmp = "%s('%s', %s);" % (cfg.v8_fuzzcommand, cfg.v8_print_command, variable_to_print)
    return tmp


def get_code_to_query_functions_and_properties_of_variables(variables):
    code = """
var variables = [""" + variables + """]

var allPropertyNames = "";
var allMethodNames = "";
var propertyNames = new Set();
var methodNames = new Set();

allProperties = {};
allMethods = {};
allNotAccessibleProperties = {};

function enumerate(obj, name, followPrototypeChain) {
    allProperties[name] = "";
    allMethods[name] = "";
    allNotAccessibleProperties[name] = "";
    while (obj !== null) {
        for (p of Object.getOwnPropertyNames(obj)) {
            var prop;
            try {
                prop = obj[p];
            } catch (e) { 
                allNotAccessibleProperties[name] += p+";";
                continue; 
            }
            if (typeof(prop) === 'function') {
                allMethods[name] += p+";";
            }
            allProperties[name] += p+";";
        }
        if (!followPrototypeChain)
            break;
        obj = Object.getPrototypeOf(obj);
    }
    allMethodNames += "\\n"
    allPropertyNames += "\\n"
}
for (name of variables) {
    if(name.includes(".") == false) {
        var builtin = this[name];
    } else {
        let parts = name.split(".")
        var builtin = this[parts[0]][parts[1]];
    }
    if(builtin == undefined) {continue;}
    enumerate(builtin, name);
}
/*
TODO: Something is wrong with the below code.
If I use it I get e.g. for 'Array' functions like 'fill', but:
Array.fill()
=> is not a function
But:
Object.getOwnPropertyNames((this["Array"].prototype))
=> Returns .fill()
That means the fuzzer could add code like:
(this["Array"].prototype).fill()
=> But currently it just adds Array.fill() which leads to an exception
I therefore just comment the code here out (for the moment and fix it later!)

for (name of variables) {
    if(name.includes(".") == false) {
        var builtin = this[name];
    } else {
        let parts = name.split(".")
        var builtin = this[parts[0]][parts[1]];
    }
    if(builtin == undefined) {continue;}
    if (!builtin.hasOwnProperty('prototype'))
        continue
    enumerate(builtin.prototype, name + '.prototype', true);
}
*/
all = {}
all["properties"] = allProperties;
all["methods"] = allMethods;
all["notAccessibleProperties"] = allNotAccessibleProperties;
""" + get_js_code_to_print("JSON.stringify(all)")
    return code


# This function just works with one instantiated object
def get_code_to_query_functions_and_properties_of_an_object(code_to_instantiate):
    code = """
allProperties = "";
allMethods = "";
allNotAccessibleProperties = "";
function enumerate(obj) {
    while (obj !== null) {
        for (p of Object.getOwnPropertyNames(obj)) {
            var prop;
            try {
                prop = obj[p];
            } catch (e) {
                allNotAccessibleProperties += p+";";
                continue;
            }

            if (typeof(prop) === 'function') {
                allMethods += p+";";
            }
            allProperties += p+";";
        }
        obj = Object.getPrototypeOf(obj);
    }
}
enumerate(__code_to_instantiate__);

all = {}
all["properties"] = allProperties;
all["methods"] = allMethods;
all["notAccessibleProperties"] = allNotAccessibleProperties;
""".replace("__code_to_instantiate__", code_to_instantiate) + get_js_code_to_print("JSON.stringify(all)")
    return code


def get_js_keywords():
    return ["async", "await", "break", "case", "class", "catch", "const", "continue", "debugger", "default", "delete",
            "do", "else", "enum", "export", "extends", "finally", "for", "function", "if", "implements", "import", "in",
            "interface", "instanceof", "let", "new", "package", "private", "protected", "public", "return", "static",
            "super", "switch", "this", "throw", "try", "typeof", "var", "void", "while", "with", "yield"]


def get_instanceable_builtin_objects_short_list():
    # "Short_list" because:
    # I just use here one Error entry
    # I just use here one Array entry
    return ["Object", "Function", "Boolean", "Error", "Number", "Date", "String", "RegExp", "Array", "Map", "Set",
            "WeakMap", "WeakSet", "ArrayBuffer", "SharedArrayBuffer", "Intl.Collator", "Intl.DateTimeFormat",
            "Intl.ListFormat", "Intl.NumberFormat", "Intl.PluralRules", "Intl.RelativeTimeFormat", ]


def get_instanceable_builtin_objects_full_list():
    return ["Object",
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
            ]


def get_NOT_instanceable_builtin_objects_full_list():
    return ["eval",
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
            "BigInt", ]


def get_not_handled_builtin_objects():
    # for the moment I ignore WebAssembly
    # and some other stuff which can't be instantiated
    return ["WebAssembly",
            "WebAssembly.Module",
            "WebAssembly.Instance",
            "WebAssembly.Memory",
            "WebAssembly.Table",
            "WebAssembly.CompileError",
            "WebAssembly.LinkError",
            "WebAssembly.RuntimeError",
            "Infinity",
            "NaN",
            "Symbol",
            "console",
            "printErr",
            "write",
            "performance",
            "setTimeout",
            "Worker"  # workers create a 2nd v8 process! don't handle them
            ]


def get_all_globals():
    tmp = set()
    tmp.update(get_instanceable_builtin_objects_full_list())
    tmp.update(get_NOT_instanceable_builtin_objects_full_list())
    tmp.update(get_not_handled_builtin_objects())
    return list(tmp)
