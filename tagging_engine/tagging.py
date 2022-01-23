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



# This script supports tagging during fuzzing
# This is useful to detect flaws in my code. E.g.: I add tags at "important mutation code locations"
# When I start a new fuzzing iteration to create a testcase, all current tags are removed
# Then mutations and merging code add tags.
# After testcase execution I log all the used tags together with the execution result.
# After X iterations I dump the tagging results to a file.
# This allows to find flaws in the code or decide how to change the likelihood of specific mutation strategies
# Example:
# Tag17 resulted in:
#       0 testcases with new coverage
#       0 successful testcases
#     500 exception thrown
#       0 hangs
#       0 crashes
# => This means the code around tag17 (e.g.: a mutation strategy) is flawed because it just generates exceptions
# 
# This can also be used to detect mutation strategies which often lead to "hangs" (hangs are very time consuming)
# Or if some mutations are useful to detect crashes (so increase their likelihood)
#
# I use a similar idea to log testcases. For example, instead of a "tag" the same logic can be applied for a "testcase"
# E.g.: I merge several testcases to create new testcases. If one testcase always leads to a hang,
# I should start to avoid this testcase (=> I "permanently disable" these testcases)
# 
# TODO: Maybe implement similar code for code bricks (my operation database). But I have a lot of operations, so this
# maybe doesn't scale
# TODO: Currently I manually check the tags, but I should automatically adjust my fuzzer based on them
# (exception: disabling testcases; But I should maybe also adjust mutation strategies?)

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import utils
from native_code.executor import Execution_Status
import config as cfg
import csv
from enum import Enum
import sync_engine.gce_bucket_sync as gce_bucket_sync

tag_to_success_without_new_coverage = dict()
tag_to_success_with_new_coverage = dict()
tag_to_exception = dict()
tag_to_hang = dict()
tag_to_crash = dict()
tag_to_exception_crash = dict()

testcase_to_success_without_new_coverage = dict()
testcase_to_success_with_new_coverage = dict()
testcase_to_exception = dict()
testcase_to_hang = dict()
testcase_to_crash = dict()
testcase_to_exception_crash = dict()

extra_string_to_success_with_new_coverage = dict()
extra_string_to_success_without_new_coverage = dict()
extra_string_to_crash = dict()
extra_string_to_exception = dict()
extra_string_to_hang = dict()
extra_string_to_exception_crash = dict()

tag_id = 0

# use a list (and not a set() => e.g. if same mutation is executed multiple 
# times I can also see the order in the list; 
# e.g. when dumping current tags for new behavior files)
current_tags = []

current_testcases = []
extra_strings = []
all_extra_strings = set()
testcases_filenames = []


def set_testcase_filenames(filenames):
    global testcases_filenames
    testcases_filenames = filenames.copy()


def add_testcase_filename(filename):
    global testcases_filenames
    testcases_filenames.append(filename)


def next_tag_id():
    global tag_id
    tag_id += 1
    return tag_id


# TODO: Check if I can maybe write this code better...lol
# Maybe I just add a tag via a string and then perform a lookup when I store it?
# but is a string then slower because of the lookup?
# Tagging is done a lot during fuzzing, so it should really not be slow
class Tag(Enum):
    MAIN_FUZZER_LOOP = next_tag_id()
    MUTATE_TESTCASE_ONLY = next_tag_id()
    MUTATE_TEMPLATE_FILE = next_tag_id()
    MERGE_TESTCASE_INSERT1 = next_tag_id()
    MERGE_TESTCASE_INSERT2_SHOULD_NOT_OCCUR = next_tag_id()
    MERGE_TESTCASE_INSERT3_SHOULD_NOT_OCCUR = next_tag_id()

    MERGE_TESTCASE_APPEND1 = next_tag_id()
    RUNTIME_ENFORCE_MINIMUM = next_tag_id()
    RUNTIME_ENFORCE_MAXIMUM = next_tag_id()
    RUNTIME_DEFAULT_RUNTIME = next_tag_id()
    RUNTIME_SUCCESS_WITH_MINIMUM_ENFORCED = next_tag_id()
    RUNTIME_SUCCESS_WITH_MAXIMUM_ENFORCED = next_tag_id()
    RUNTIME_SUCCESS_WITH_DEFAULT_RUNTIME = next_tag_id()
    RUNTIME_HANG_WITH_MINIMUM_ENFORCED = next_tag_id()
    RUNTIME_HANG_WITH_MAXIMUM_ENFORCED = next_tag_id()
    RUNTIME_HANG_WITH_DEFAULT_RUNTIME = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION1 = next_tag_id()
    MUTATION_MOVE_OPERATION_AROUND1 = next_tag_id()
    MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING2 = next_tag_id()
    MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING3 = next_tag_id()
    MUTATION_MOVE_OPERATION_AROUND_DO_NOTHING4 = next_tag_id()
    CHECK_IF_VARIABLES_ARE_AVAILABLE_IN_LINE1 = next_tag_id()
    CHECK_IF_VARIABLES_ARE_AVAILABLE_IN_LINE2 = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE1 = next_tag_id()
    MUTATION_INSERT_MULTIPLE_RANDOM_OPERATIONS_FROM_DATABASE1 = next_tag_id()
    MUTATION_REMOVE_LINE1 = next_tag_id()
    MUTATION_DUPLICATE_LINE1 = next_tag_id()
    MUTATION_REPLACE_NUMBER1 = next_tag_id()
    MUTATION_REPLACE_STRING1 = next_tag_id()
    MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE1 = next_tag_id()
    MUTATION_MODIFY_NUMBER1 = next_tag_id()
    MUTATION_MODIFY_STRING1 = next_tag_id()
    MUTATION_IF_WRAP_LINE1 = next_tag_id()
    MUTATION_FOR_WRAP_LINE1 = next_tag_id()
    MUTATION_WHILE_WRAP_LINE1 = next_tag_id()
    MUTATION_MATERIALIZE_VALUE1 = next_tag_id()
    MUTATION_WRAP_VALUE_IN_FUNCTION1 = next_tag_id()
    MUTATION_WRAP_VALUE_IN_FUNCTION_ARGUMENT1 = next_tag_id()
    MUTATION_WRAP_STRING_IN_FUNCTION1 = next_tag_id()
    MUTATION_WRAP_STRING_IN_FUNCTION_ARGUMENT1 = next_tag_id()
    MUTATION_WRAP_VARIABLE_IN_FUNCTION1 = next_tag_id()
    MUTATION_WRAP_VARIABLE_IN_FUNCTION_ARGUMENT1 = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE1 = next_tag_id()
    MUTATION_CHANGE_PROTOTYPE1 = next_tag_id()
    MUTATION_CHANGE_PROTO1 = next_tag_id()
    MUTATION_FOR_WRAP_LINE2_DO_NOTHING = next_tag_id()
    MUTATION_MATERIALIZE_VALUE2_DO_NOTHING = next_tag_id()
    MUTATION_WHILE_WRAP_LINE2_DO_NOTHING = next_tag_id()
    MUTATION_IF_WRAP_LINE2_DO_NOTHING = next_tag_id()
    MUTATION_IF_WRAP_LINE3 = next_tag_id()
    MUTATION_IF_WRAP_LINE4 = next_tag_id()
    MUTATION_IF_WRAP_LINE5_MANY_EXCEPTIONS = next_tag_id()
    MUTATION_IF_WRAP_LINE6 = next_tag_id()
    MUTATION_MODIFY_STRING2_DO_NOTHING = next_tag_id()
    MUTATION_MODIFY_STRING3 = next_tag_id()
    MUTATION_MODIFY_STRING4 = next_tag_id()
    MUTATION_MODIFY_STRING5 = next_tag_id()
    MUTATION_MODIFY_STRING6 = next_tag_id()
    MUTATION_REPLACE_STRING2_DO_NOTHING = next_tag_id()
    MUTATION_REPLACE_STRING3_DO_NOTHING = next_tag_id()
    MUTATION_WRAP_STRING_IN_FUNCTION2_DO_NOTHING = next_tag_id()
    GET_PROTO_CHANGE_LHS1 = next_tag_id()
    GET_PROTO_CHANGE_LHS2 = next_tag_id()
    GET_PROTOTYPE_CHANGE_LHS1 = next_tag_id()
    GET_PROTOTYPE_CHANGE_LHS2 = next_tag_id()
    GET_PROTO_CHANGE_RHS1 = next_tag_id()
    GET_PROTO_CHANGE_RHS2 = next_tag_id()
    GET_PROTO_CHANGE_RHS3 = next_tag_id()
    GET_PROTO_CHANGE_RHS4 = next_tag_id()
    GET_PROTO_CHANGE_RHS5 = next_tag_id()
    GET_PROTO_CHANGE_RHS6 = next_tag_id()
    GET_PROTO_CHANGE_RHS7 = next_tag_id()
    GET_PROTO_CHANGE_RHS8 = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE2_DO_NOTHING = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE3_DO_NOTHING_SHOULD_NOT_OCCUR = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE4_DO_NOTHING_SHOULD_NOT_OCCUR = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE5 = next_tag_id()
    MUTATION_ENFORCE_CALL_NODE6 = next_tag_id()
    MUTATION_WRAP_VARIABLE_IN_FUNCTION2_DO_NOTHING = next_tag_id()
    MUTATION_WRAP_VALUE_IN_FUNCTION2_DO_NOTHING = next_tag_id()
    MUTATION_WRAP_VARIABLE_IN_FUNCTION_ARGUMENT2_DO_NOTHING = next_tag_id()
    MUTATION_WRAP_STRING_IN_FUNCTION_ARGUMENT2_DO_NOTHING = next_tag_id()
    MUTATION_WRAP_VALUE_IN_FUNCTION_ARGUMENT2_DO_NOTHING = next_tag_id()
    MUTATION_MODIFY_NUMBER2_DO_NOTHING = next_tag_id()
    MUTATION_MODIFY_NUMBER3 = next_tag_id()
    MUTATION_MODIFY_NUMBER4 = next_tag_id()
    MUTATION_MODIFY_NUMBER5 = next_tag_id()
    MUTATION_MODIFY_NUMBER6 = next_tag_id()
    MUTATION_MODIFY_NUMBER7 = next_tag_id()
    MUTATION_MODIFY_NUMBER8 = next_tag_id()
    MUTATION_REPLACE_NUMBER2_DO_NOTHING = next_tag_id()
    MUTATION_REPLACE_NUMBER3 = next_tag_id()
    MUTATION_REPLACE_NUMBER4 = next_tag_id()
    MUTATION_REPLACE_NUMBER5 = next_tag_id()
    MUTATION_REPLACE_NUMBER6 = next_tag_id()
    MUTATION_REPLACE_NUMBER7 = next_tag_id()
    MUTATION_REPLACE_NUMBER8 = next_tag_id()
    MUTATION_REPLACE_NUMBER9_SHOULD_NEVER_OCCUR = next_tag_id()
    DECOMPOSE_NUMBER1 = next_tag_id()
    DECOMPOSE_NUMBER2 = next_tag_id()
    DECOMPOSE_NUMBER3 = next_tag_id()
    DECOMPOSE_NUMBER4 = next_tag_id()
    DECOMPOSE_NUMBER5 = next_tag_id()
    DECOMPOSE_NUMBER6 = next_tag_id()
    DECOMPOSE_NUMBER7 = next_tag_id()
    DECOMPOSE_NUMBER8 = next_tag_id()
    DECOMPOSE_NUMBER9 = next_tag_id()
    DECOMPOSE_NUMBER10 = next_tag_id()
    DECOMPOSE_NUMBER11 = next_tag_id()
    DECOMPOSE_NUMBER12 = next_tag_id()
    DECOMPOSE_NUMBER13 = next_tag_id()
    DECOMPOSE_NUMBER14 = next_tag_id()
    DECOMPOSE_NUMBER15 = next_tag_id()
    DECOMPOSE_NUMBER16 = next_tag_id()
    DECOMPOSE_NUMBER17 = next_tag_id()
    DECOMPOSE_NUMBER18 = next_tag_id()
    DECOMPOSE_NUMBER19 = next_tag_id()
    DECOMPOSE_NUMBER20 = next_tag_id()
    DECOMPOSE_NUMBER21 = next_tag_id()
    DECOMPOSE_NUMBER22 = next_tag_id()
    DECOMPOSE_NUMBER23 = next_tag_id()
    DECOMPOSE_NUMBER24 = next_tag_id()
    DECOMPOSE_NUMBER25 = next_tag_id()
    DECOMPOSE_NUMBER26 = next_tag_id()
    DECOMPOSE_NUMBER27 = next_tag_id()
    DECOMPOSE_NUMBER28 = next_tag_id()
    DECOMPOSE_NUMBER29 = next_tag_id()
    DECOMPOSE_NUMBER30 = next_tag_id()
    DECOMPOSE_NUMBER31 = next_tag_id()
    MUTATION_DO_NOTHING1 = next_tag_id()
    GET_RANDOM_OPERATION1 = next_tag_id()
    GET_RANDOM_OPERATION2 = next_tag_id()
    GET_RANDOM_OPERATION3 = next_tag_id()
    GET_RANDOM_OPERATION4 = next_tag_id()
    GET_RANDOM_OPERATION5 = next_tag_id()
    MUTATION_STRESSTEST_TRANSITION_TREE1 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE1 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE2 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE3 = next_tag_id()
    GET_AVAILABLE_VARIABLES_WITH_DATATYPES1 = next_tag_id()
    GET_AVAILABLE_VARIABLES_WITH_DATATYPES2 = next_tag_id()
    GET_AVAILABLE_VARIABLES_WITH_DATATYPES3 = next_tag_id()
    GET_AVAILABLE_VARIABLES_WITH_DATATYPES4 = next_tag_id()
    GET_AVAILABLE_VARIABLES_WITH_DATATYPES5 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION1 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION2 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION3 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION4 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION5 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION6 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION6b = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION6c = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION7_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION8_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION9_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION10_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION11_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION12_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION13_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION14_TODO = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION15_TODO = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION16 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION17 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_string = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_int8array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_uint8array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_uint8clampedarray = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_int16array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_uint16array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_int32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_uint32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_float32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_float64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_bigint64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_biguint64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_set = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_weakset = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_map = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_weakmap = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_regexp = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_arraybuffer = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_sharedarraybuffer = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_dataview = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_promise = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_collator = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_datetimeformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_listformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_numberformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_pluralrules = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_relativetimeformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl_locale = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_module = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_instance = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_memory = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_table = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_compileerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_linkerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly_runtimeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_urierror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_typeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_syntaxerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_rangeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_evalerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_referenceerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_error = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_date = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_null = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_math = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_json = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_reflect = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_globalThis = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_atomics = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_intl = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_webassembly = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_object1 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_object2 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_unkown_object = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_real_number = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_special_number = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_function = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_boolean = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_symbol = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_undefined = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_bigint = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_MISSING_DATATYPE_TODO = next_tag_id()
    GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE1 = next_tag_id()
    GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE2 = next_tag_id()
    GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE3 = next_tag_id()
    GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE4 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE1 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE2 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE3 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE4 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE5 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE6 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE7 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE8 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE9 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE10 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE11 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE12 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE13 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE14 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE15 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE16 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE17 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE18 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE19 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE20 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE21 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE22 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE23 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE24 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE25 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE26 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE27 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE28 = next_tag_id()
    # GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE29 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE30 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE31 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE32 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_string = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int8array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint8array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint8clampedarray = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int16array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint16array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_float32array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_float64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_bigint64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_biguint64array = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_set = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_weakset = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_map = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_weakmap = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_regexp = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_arraybuffer = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_sharedarraybuffer = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_dataview = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_promise = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_collator = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_datetimeformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_listformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_numberformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_pluralrules = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_relativetimeformat = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_locale = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_module = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_instance = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_memory = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_table = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_compileerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_linkerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_runtimeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_urierror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_typeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_syntaxerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_rangeerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_evalerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_referenceerror = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_error = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_date = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_null = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_math = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_json = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_reflect = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_globalThis = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_atomics = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_object1 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_object2 = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_unkown_object = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_real_number = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_special_number = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_function = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_boolean = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_symbol = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_undefined = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_bigint = next_tag_id()
    GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_MISSING_DATATYPE_TODO = next_tag_id()
    MUTATION_FOR_WRAP_OPERATIONS1 = next_tag_id()
    MUTATION_IF_WRAP_OPERATIONS1 = next_tag_id()
    INSERT_RANDOM_ARRAY_OPERATION_AT_SPECIFIC_LINE1 = next_tag_id()
    INSERT_RANDOM_ARRAY_OPERATION_AT_SPECIFIC_LINE2_DO_NOTHING = next_tag_id()
    GET_START_AND_END_LINES_TO_WRAP1 = next_tag_id()
    GET_START_AND_END_LINES_TO_WRAP2_DO_NOTHING = next_tag_id()
    GET_START_AND_END_LINES_TO_WRAP3_DO_NOTHING = next_tag_id()
    GET_START_AND_END_LINES_TO_WRAP4_DO_NOTHING = next_tag_id()
    WRAP_CODELINES1 = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH1 = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH2_RARE = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH3 = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH4_RARE = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH5 = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH6_RARE = next_tag_id()
    GET_RANDOM_ARRAY_LENGTH7_RARE = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION1 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION2 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION3 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION4 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION5 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION6 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION7 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION8 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION9 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION10 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION11 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION12 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION13 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION14 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION15 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION16 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION17 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION18 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION19 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION20 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION21 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION22 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION23 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION24 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION25 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION26 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION27 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION28 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION29 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION30 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION31 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION32 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION33 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION34 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION35 = next_tag_id()
    GET_RANDOM_ARRAY_OPERATION36 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX1 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX2 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX3 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX4 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX5 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX6 = next_tag_id()
    GET_RANDOM_ARRAY_INDEX7 = next_tag_id()
    GET_RANDOM_ARRAY_ENTRY_VALUE1 = next_tag_id()
    GET_RANDOM_ARRAY_ENTRY_VALUE2 = next_tag_id()
    GET_RANDOM_ARRAY_ENTRY_VALUE3 = next_tag_id()
    GET_RANDOM_ARRAY_ENTRY_VALUE4 = next_tag_id()
    GET_RANDOM_ARRAY_ENTRY_VALUE5 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE1 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE2_FALLBACK = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE3 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE4 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE5 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE6 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE7 = next_tag_id()
    GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE8 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION1 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION2 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION3 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION4 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION5 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION6 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION7 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION8 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION9 = next_tag_id()
    GET_SPECIAL_RANDOM_OPERATION10 = next_tag_id()
    GET_START_AND_END_LINE_SYMBOLS_SEMICOLON = next_tag_id()
    GET_START_AND_END_LINE_SYMBOLS_END_COMA = next_tag_id()
    GET_START_AND_END_LINE_SYMBOLS_START_COMA = next_tag_id()
    MUTATION_ADD_VARIABLE1 = next_tag_id()
    MUTATION_ADD_VARIABLE2 = next_tag_id()
    MUTATION_ADD_VARIABLE3 = next_tag_id()
    JS_GET_STRING1 = next_tag_id()
    JS_GET_STRING2 = next_tag_id()
    JS_GET_STRING3 = next_tag_id()
    JS_GET_STRING4 = next_tag_id()
    JS_GET_STRING5 = next_tag_id()
    JS_GET_STRING6 = next_tag_id()
    JS_GET_STRING7 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE1 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_STRING = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_ARRAY = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL2 = next_tag_id()
    # GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL4 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL5 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SYMBOL6 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY3 = next_tag_id()
    # GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY4 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY5 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_ARRAY6 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_TYPED_SET3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_WEAKSET = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_MAP = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_WEAKMAP = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REGEXP = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_ARRAYBUFFER = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_SHAREDARRAYBUFFER = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATAVIEW3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_PROMISE = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_COLLATOR3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_DATETIMEFORMAT = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_LISTFORMAT = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_NUMBERFORMAT = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_PLURALRULES = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_RELATIVETIMEFORMAT = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_INTL_LOCALE = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_DATE = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT1 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_OBJECT4 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER4 = next_tag_id()
    # GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_REAL_NUMBER5 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION2 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_FUNCTION4 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BOOLEAN = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT = next_tag_id()
    # GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT2 = next_tag_id()
    # GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT3 = next_tag_id()
    GET_CODE_TO_CREATE_RANDOM_VARIABLE_WITH_DATATYPE_BIGINT4 = next_tag_id()
    TESTCASE_CONTAINS_CONST_VARIABLE = next_tag_id()
    TESTCASE_DOES_NOT_CONTAIN_CONST_VARIABLE = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_AT_SPECIFIC_LINE1 = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE1 = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE2_DO_NOTHING = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE3 = next_tag_id()
    MUTATION_INSERT_RANDOM_OPERATION_FROM_DATABASE_AT_SPECIFIC_LINE4 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE1 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE2 = next_tag_id()
    GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE3 = next_tag_id()
    # GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE4 = next_tag_id()
    # GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE5 = next_tag_id()
    # GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE6 = next_tag_id()
    # GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE7 = next_tag_id()
    # GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE8 = next_tag_id()
    MUTATION_DUPLICATE_LINE2 = next_tag_id()
    MUTATION_DUPLICATE_LINE3 = next_tag_id()
    MUTATION_DUPLICATE_LINE4_DO_NOTHING = next_tag_id()
    MUTATION_DUPLICATE_LINE5_DO_NOTHING_RARE = next_tag_id()
    MUTATION_DUPLICATE_LINE6 = next_tag_id()
    MUTATION_DUPLICATE_LINE7 = next_tag_id()
    MUTATION_DUPLICATE_LINE8 = next_tag_id()
    MUTATION_DUPLICATE_LINE9_DO_NOTHING = next_tag_id()
    MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE2_DO_NOTHING = next_tag_id()
    MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE3 = next_tag_id()
    MUTATION_CHANGE_TWO_VARIABLES_OF_SAME_TYPE4 = next_tag_id()
    MUTATION_REMOVE_SPECIFIC_LINE1 = next_tag_id()
    MUTATION_REMOVE_LINE2 = next_tag_id()
    MUTATION_REMOVE_LINE3 = next_tag_id()
    MUTATION_REMOVE_LINE4 = next_tag_id()
    MUTATION_REMOVE_LINE5_DO_NOTHING = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE1 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE2 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE3 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE4 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE5 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE6 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE7 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE8 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE9 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE10 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE11 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE12 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE13 = next_tag_id()
    ADAPT_SECOND_TESTCASE_TO_FIRST_TESTCASE14 = next_tag_id()
    STATE_UPDATE_LINE_NUMBER_LIST_WITH_SECOND_TESTCASE1 = next_tag_id()
    STATE_UPDATE_LINE_NUMBER_LIST_WITH_SECOND_TESTCASE2 = next_tag_id()

    STATE_UPDATE_ALL_LINE_NUMBERS1 = next_tag_id()
    MERGE_TESTCASE2_INTO_TESTCASE1_AT_LINE1 = next_tag_id()
    MERGE_TESTCASE_INTO_JIT_COMPILED_FUNCTION1 = next_tag_id()
    STATE_INSERT_LINE1 = next_tag_id()
    STATE_REMOVE_LINE1 = next_tag_id()


all_tag_values = [e.value for e in Tag]


def add_tag(tag_number):
    global current_tags
    if cfg.tagging_enabled is False:
        return
    current_tags.append(tag_number.value)


def add_testcase(testcase_name):
    global current_testcases
    if cfg.tagging_enabled is False:
        return
    current_testcases.append(testcase_name)


def add_extra_string(extra_string):
    # Mainly used for debugging when I want to tag/log extra locations...
    global extra_strings
    if cfg.tagging_enabled is False:
        return
    extra_strings.append(extra_string)
    all_extra_strings.add(extra_string)


def check_if_tag_is_in_current_tags(tag_number):
    global current_tags
    if tag_number.value in current_tags:
        return True
    else:
        return False


def get_testcase_stats(testcase_name):
    global testcase_to_success_without_new_coverage, testcase_to_exception, testcase_to_hang
    # I'm using this function to decide if I should disable a testcase (e.g. stop fuzzing it)
    # => if the testcase results very often in exceptions or hangs, it doesn't make sense to continue
    # fuzzing it

    # => I'm just returning the success, exception and hangs stats
    # Theoretically I could also return the other stats (new coverage, crashes, exception crashes)
    # but that are rare events and the lookup during fuzzing doesn't justify it
    number_success = 0
    number_exception = 0
    number_hang = 0
    if testcase_name in testcase_to_success_without_new_coverage:
        number_success = testcase_to_success_without_new_coverage[testcase_name]
    if testcase_name in testcase_to_exception:
        number_exception = testcase_to_exception[testcase_name]
    if testcase_name in testcase_to_hang:
        number_hang = testcase_to_hang[testcase_name]
    return number_success, number_exception, number_hang


def execution_finished(result):
    global current_tags, current_testcases
    global tag_to_success_with_new_coverage, tag_to_success_without_new_coverage, tag_to_crash, tag_to_exception, tag_to_hang, tag_to_exception_crash
    global testcase_to_success_with_new_coverage, testcase_to_success_without_new_coverage, testcase_to_crash, testcase_to_exception, testcase_to_hang, testcase_to_exception_crash
    global extra_string_to_success_with_new_coverage
    global extra_string_to_success_without_new_coverage
    global extra_string_to_crash
    global extra_string_to_exception
    global extra_string_to_hang
    global extra_string_to_exception_crash

    if cfg.tagging_enabled is False:
        return

    if result.status == Execution_Status.SUCCESS:
        if result.num_new_edges > 0:
            dict_to_use = tag_to_success_with_new_coverage
            testcase_dict_to_use = testcase_to_success_with_new_coverage
            extra_strings_dict_to_use = extra_string_to_success_with_new_coverage
        else:
            dict_to_use = tag_to_success_without_new_coverage
            testcase_dict_to_use = testcase_to_success_without_new_coverage
            extra_strings_dict_to_use = extra_string_to_success_without_new_coverage
    elif result.status == Execution_Status.CRASH:
        dict_to_use = tag_to_crash
        testcase_dict_to_use = testcase_to_crash
        extra_strings_dict_to_use = extra_string_to_crash
    elif result.status == Execution_Status.EXCEPTION_THROWN:
        dict_to_use = tag_to_exception
        testcase_dict_to_use = testcase_to_exception
        extra_strings_dict_to_use = extra_string_to_exception
    elif result.status == Execution_Status.TIMEOUT:
        dict_to_use = tag_to_hang
        testcase_dict_to_use = testcase_to_hang
        extra_strings_dict_to_use = extra_string_to_hang
    elif result.status == Execution_Status.EXCEPTION_CRASH:
        dict_to_use = tag_to_exception_crash
        testcase_dict_to_use = testcase_to_exception_crash
        extra_strings_dict_to_use = extra_string_to_exception_crash
    else:
        utils.perror("Unkown execution status result: %s, stopping..." % str(result.status))

    for tag in current_tags:
        if tag not in dict_to_use:
            dict_to_use[tag] = 0
        dict_to_use[tag] += 1   # count the result

    for testcase_name in current_testcases:
        if testcase_name not in testcase_dict_to_use:
            testcase_dict_to_use[testcase_name] = 0
        testcase_dict_to_use[testcase_name] += 1    # count the result for testcases

    for extra_string in extra_strings:
        if extra_string not in extra_strings_dict_to_use:
            extra_strings_dict_to_use[extra_string] = 0
        extra_strings_dict_to_use[extra_string] += 1    # count the extra string


def clear_current_tags():
    global current_tags, current_testcases, extra_strings
    current_tags.clear()   # Reset tags for next execution
    current_testcases.clear()
    extra_strings.clear()


def dump_current_tags_to_file(filepath):
    output = get_current_tags()
    with open(filepath, "w") as fobj:
        fobj.write(output)
    return output


def get_current_tags():
    global current_tags

    output = ""
    for tag_idx in current_tags:
        tag_name = str(Tag(tag_idx))
        output += tag_name + "\n"
        
    for testcase_name in current_testcases:
        output += testcase_name + "\n"

    for extra_string in extra_strings:
        output += extra_string + "\n"

    return output


def dump_current_tagging_results(tagging_output_filepath):
    global tag_to_success_with_new_coverage, tag_to_success_without_new_coverage, tag_to_crash, tag_to_exception, tag_to_hang, tag_to_exception_crash
    global testcase_to_success_with_new_coverage, testcase_to_success_without_new_coverage, testcase_to_crash, testcase_to_exception, testcase_to_hang, testcase_to_exception_crash
    global extra_string_to_success_with_new_coverage
    global extra_string_to_success_without_new_coverage
    global extra_string_to_crash
    global extra_string_to_exception
    global extra_string_to_hang
    global extra_string_to_exception_crash
    global extra_strings
    global all_extra_strings
    global all_tag_values, testcases_filenames

    if cfg.tagging_enabled is False:
        return

    utils.msg("[i] Dumping tagging results")
    
    with open(tagging_output_filepath, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(["Tag", "Total executions", "Success", "Success %", "New Coverage", "New Coverage %", "Exceptions", "Exceptions %", "Hangs", "Hangs %", "Crashes", "Crashes %", "Exception Crashes", "Exception Crashes %", ])

        for tag_idx in all_tag_values:

            tag_name = str(Tag(tag_idx))
            # fobj.write("Tag: %s\n" % tag_name)
            
            number_success_without_new_coverage = tag_to_success_without_new_coverage.get(tag_idx, 0)
            number_success_with_new_coverage = tag_to_success_with_new_coverage.get(tag_idx, 0)
            number_exception = tag_to_exception.get(tag_idx, 0)
            number_hang = tag_to_hang.get(tag_idx, 0)
            number_crash = tag_to_crash.get(tag_idx, 0)
            number_exception_crashes = tag_to_exception_crash.get(tag_idx, 0)

            total_executions_of_tag = number_success_without_new_coverage + number_success_with_new_coverage + number_exception + number_hang + number_crash
            if total_executions_of_tag == 0:
                number_success_without_new_coverage_relative = "0.0"
                number_success_with_new_coverage_relative = "0.0"
                number_exception_relative = "0.0"
                number_hang_relative = "0.0"
                number_crash_relative = "0.0"
                number_exception_crashes_relative = "0.0"
            else:
                number_success_without_new_coverage_relative = "%.2f" % (100*float(number_success_without_new_coverage) / float(total_executions_of_tag))
                number_success_with_new_coverage_relative = "%.2f" % (100*float(number_success_with_new_coverage) / float(total_executions_of_tag))
                number_exception_relative = "%.2f" % (100*float(number_exception) / float(total_executions_of_tag))
                number_hang_relative = "%.2f" % (100*float(number_hang) / float(total_executions_of_tag))
                number_crash_relative = "%.2f" % (100*float(number_crash) / float(total_executions_of_tag))
                number_exception_crashes_relative = "%.2f" % (100*float(number_exception_crashes) / float(total_executions_of_tag))

            writer.writerow([tag_name, total_executions_of_tag,
                            number_success_without_new_coverage,
                            number_success_without_new_coverage_relative,
                            number_success_with_new_coverage,
                            number_success_with_new_coverage_relative,
                            number_exception,
                            number_exception_relative,
                            number_hang,
                            number_hang_relative,
                            number_crash,
                            number_crash_relative,
                            number_exception_crashes,
                            number_exception_crashes_relative
                             ])

        for testcase_filename in testcases_filenames:
            
            number_success_without_new_coverage = testcase_to_success_without_new_coverage.get(testcase_filename, 0)
            number_success_with_new_coverage = testcase_to_success_with_new_coverage.get(testcase_filename, 0)
            number_exception = testcase_to_exception.get(testcase_filename, 0)
            number_hang = testcase_to_hang.get(testcase_filename, 0)
            number_crash = testcase_to_crash.get(testcase_filename, 0)
            number_exception_crashes = testcase_to_exception_crash.get(tag_idx, 0)

            total_executions_of_tag = number_success_without_new_coverage + number_success_with_new_coverage + number_exception + number_hang + number_crash
            if total_executions_of_tag == 0:
                number_success_without_new_coverage_relative = "0.0"
                number_success_with_new_coverage_relative = "0.0"
                number_exception_relative = "0.0"
                number_hang_relative = "0.0"
                number_crash_relative = "0.0"
                number_exception_crashes_relative = "0.0"
            else:
                number_success_without_new_coverage_relative = "%.2f" % (100*float(number_success_without_new_coverage) / float(total_executions_of_tag))
                number_success_with_new_coverage_relative = "%.2f" % (100*float(number_success_with_new_coverage) / float(total_executions_of_tag))
                number_exception_relative = "%.2f" % (100*float(number_exception) / float(total_executions_of_tag))
                number_hang_relative = "%.2f" % (100*float(number_hang) / float(total_executions_of_tag))
                number_crash_relative = "%.2f" % (100*float(number_crash) / float(total_executions_of_tag))
                number_exception_crashes_relative = "%.2f" % (100*float(number_exception_crashes) / float(total_executions_of_tag))

            writer.writerow([testcase_filename, total_executions_of_tag, 
                            number_success_without_new_coverage,
                            number_success_without_new_coverage_relative,
                            number_success_with_new_coverage,
                            number_success_with_new_coverage_relative,
                            number_exception,
                            number_exception_relative,
                            number_hang,
                            number_hang_relative,
                            number_crash,
                            number_crash_relative,
                            number_exception_crashes,
                            number_exception_crashes_relative
                             ])

        for extra_string in all_extra_strings:
            number_success_without_new_coverage = extra_string_to_success_without_new_coverage.get(extra_string, 0)
            number_success_with_new_coverage = extra_string_to_success_with_new_coverage.get(extra_string, 0)
            number_exception = extra_string_to_exception.get(extra_string, 0)
            number_hang = extra_string_to_hang.get(extra_string, 0)
            number_crash = extra_string_to_crash.get(extra_string, 0)
            number_exception_crashes = extra_string_to_exception_crash.get(tag_idx, 0)

            total_executions_of_tag = number_success_without_new_coverage + number_success_with_new_coverage + number_exception + number_hang + number_crash
            if total_executions_of_tag == 0:
                number_success_without_new_coverage_relative = "0.0"
                number_success_with_new_coverage_relative = "0.0"
                number_exception_relative = "0.0"
                number_hang_relative = "0.0"
                number_crash_relative = "0.0"
                number_exception_crashes_relative = "0.0"
            else:
                number_success_without_new_coverage_relative = "%.2f" % (100*float(number_success_without_new_coverage) / float(total_executions_of_tag))
                number_success_with_new_coverage_relative = "%.2f" % (100*float(number_success_with_new_coverage) / float(total_executions_of_tag))
                number_exception_relative = "%.2f" % (100*float(number_exception) / float(total_executions_of_tag))
                number_hang_relative = "%.2f" % (100*float(number_hang) / float(total_executions_of_tag))
                number_crash_relative = "%.2f" % (100*float(number_crash) / float(total_executions_of_tag))
                number_exception_crashes_relative = "%.2f" % (100*float(number_exception_crashes) / float(total_executions_of_tag))

            writer.writerow([extra_string, total_executions_of_tag, 
                            number_success_without_new_coverage,
                            number_success_without_new_coverage_relative,
                            number_success_with_new_coverage,
                            number_success_with_new_coverage_relative,
                            number_exception,
                            number_exception_relative,
                            number_hang,
                            number_hang_relative,
                            number_crash,
                            number_crash_relative,
                            number_exception_crashes,
                            number_exception_crashes_relative
                             ])

    output_filename = os.path.basename(tagging_output_filepath)
    with open(tagging_output_filepath, "r") as fobj:
        stats_content = fobj.read()
    gce_bucket_sync.save_stats(output_filename, stats_content)
