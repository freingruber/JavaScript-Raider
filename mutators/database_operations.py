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



# The fuzzer uses various databases for things like:
# *) Global available tokens, variables, functions, ...
# *) Variable or generic operations extracted from the corpus
# *) Extracted numbers or strings from the corpus
# This code loads these databases and makes them available

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import utils
import config as cfg
import tagging_engine.tagging as tagging
from tagging_engine.tagging import Tag
import pickle
import mutators.testcase_mutators_helpers as testcase_mutators_helpers
import javascript.js as js
import javascript.js_runtime_extraction_code as js_runtime_extraction_code
import javascript.js_helpers as js_helpers
import mutators.testcase_mutator as testcase_mutator

class_methods = None
class_properties = None
class_not_accessible_properties = None
obj_methods = None
obj_properties = None
obj_not_accessible_properties = None

possible_instanceable_objects = []
all_global_available_obj_names = []

database_generic_operations = []
database_generic_operations_single_operation = []

database_variable_operations = dict()
database_variable_operations_single_operation = dict()

database_variable_other_operations = dict()
database_variable_other_operations_single_operation = dict()

database_variable_operations_list = []
database_variable_operations_states_list = []


def initialize():
    load_globals()
    loading_successful = load_operations_database()
    if loading_successful is False:
        testcase_mutator.disable_database_based_mutations()


def load_operations_database():
    global database_generic_operations, database_variable_operations, database_variable_other_operations
    global database_generic_operations_single_operation, database_variable_operations_single_operation, database_variable_other_operations_single_operation
    global database_variable_operations_list, database_variable_operations_states_list

    problem_msg = "[!] Problem: Operations database %s doesn't exist. "
    problem_msg += "You can create the databases via the \"--extract_data operations\" argument!"
    database_paths = [cfg.pickle_database_generic_operations,
                      cfg.pickle_database_variable_operations,
                      cfg.pickle_database_variable_operations_others,
                      cfg.pickle_database_variable_operations_list,
                      cfg.pickle_database_variable_operations_states_list]

    for database_path in database_paths:
        if os.path.exists(database_path) is False:
            utils.msg(problem_msg % cfg.pickle_database_generic_operations)
            return False

    with open(cfg.pickle_database_generic_operations, 'rb') as finput:
        database_generic_operations = pickle.load(finput)
    with open(cfg.pickle_database_variable_operations, 'rb') as finput:
        database_variable_operations = pickle.load(finput)
    with open(cfg.pickle_database_variable_operations_others, 'rb') as finput:
        database_variable_other_operations = pickle.load(finput)
    with open(cfg.pickle_database_variable_operations_list, 'rb') as finput:
        database_variable_operations_list = pickle.load(finput)
    with open(cfg.pickle_database_variable_operations_states_list, 'rb') as finput:
        database_variable_operations_states_list = pickle.load(finput)

    # Calculate single operations
    # This is required because if a line must end with "," then I can't add in this line multiple operations
    # which also end with ";"
    # Maybe I can wrap them in a block like {operation1;operation2}
    # EDIT: No that's not possible, but what's working is operation1 || operation2
    # or wrapping it inside an immediately invoked function
    # Also try-finally wrapping is not possible

    # Currently I extract single line operations by checking if an operation has just 1 LoC
    # or if it doesn't contain a ";"
    # This is important because many operations are something like this:
    # var_TARGET_.indexOf(Number.MAX_SAFE_INTEGER
    # )
    # => the ")" will always be in a separated line and therefore the operation will has 2 lines
    for entry in database_generic_operations:
        (operation, state) = entry
        lines_of_code = len(operation.strip().split("\n"))
        operation_column_stripped = operation.rstrip(";")
        if lines_of_code == 1 or operation_column_stripped.count(";") == 0:
            # state = state.deep_copy()
            # Note: copying the state should not be required here because states are copied
            # when the I apply it during mutation => it saves some RAM
            database_generic_operations_single_operation.append((operation, state))

    for variable_type in database_variable_operations:
        database_variable_operations_single_operation[variable_type] = []
        for entry in database_variable_operations[variable_type]:
            (operation_index, state_index) = entry
            operation = database_variable_operations_list[operation_index]
            operation_column_stripped = operation.rstrip(";")
            lines_of_code = len(operation.strip().split("\n"))
            if lines_of_code == 1 or operation_column_stripped.count(";") == 0:
                database_variable_operations_single_operation[variable_type].append((operation_index, state_index))

    for variable_type in database_variable_other_operations:
        database_variable_other_operations_single_operation[variable_type] = []
        for entry in database_variable_other_operations[variable_type]:
            (operation_index, state_index) = entry
            operation = database_variable_operations_list[operation_index]
            operation_column_stripped = operation.rstrip(";")
            lines_of_code = len(operation.strip().split("\n"))
            if lines_of_code == 1 or operation_column_stripped.count(";") == 0:
                database_variable_other_operations_single_operation[variable_type].append(
                    (operation_index, state_index))

    utils.msg("[i] Successfully loaded pickle databases with operations...")
    utils.msg("[i] Generic operations: %d" % len(database_generic_operations))
    utils.msg("[i] Unique variable operations: %d" % len(database_variable_operations_list))


def load_globals():
    global class_methods, class_properties, class_not_accessible_properties, obj_methods, obj_properties, obj_not_accessible_properties
    global possible_instanceable_objects, all_global_available_obj_names

    # utils.dbg_msg("Loading pickle files...")
    js.load_pickle_databases()

    if cfg.fuzzer_arguments.recalculate_globals is False and (cfg.load_cached_globals and os.path.isfile(cfg.pickle_database_globals)):
        utils.msg("[i] Loading globals from pickle cache: %s" % cfg.pickle_database_globals)
        with open(cfg.pickle_database_globals, 'rb') as finput:
            data = pickle.load(finput)
    else:
        utils.msg("[i] Loading from runtime...")
        data = js_runtime_extraction_code.extract_data_of_all_globals(cfg.exec_engine)
        with open(cfg.pickle_database_globals, 'wb') as fout:
            pickle.dump(data, fout, pickle.HIGHEST_PROTOCOL)
    (class_methods, class_properties, class_not_accessible_properties, obj_methods, obj_properties, obj_not_accessible_properties) = data

    if "globalThis" in class_methods:
        if "quit" in class_methods["globalThis"]:
            class_methods["globalThis"].remove("quit")

    if "d8" in class_methods:
        del class_methods["d8"]
    if "d8" in class_properties:
        del class_properties["d8"]
    if "d8" in class_not_accessible_properties:
        del class_not_accessible_properties["d8"]

    x = set()
    for global_variable in obj_methods:
        x.add(global_variable)
    for global_variable in obj_properties:
        x.add(global_variable)
    for global_variable in obj_not_accessible_properties:
        x.add(global_variable)
    possible_instanceable_objects = list(x)
    js.set_possible_instanceable_objects(possible_instanceable_objects)  # make it also available for the JS module

    x = set()
    for global_variable in class_methods:
        x.add(global_variable)
    for global_variable in class_properties:
        x.add(global_variable)
    for global_variable in class_not_accessible_properties:
        x.add(global_variable)
    all_global_available_obj_names = list(x)



def get_random_operation_without_a_variable(content, state, line_number):
    global all_global_available_obj_names, class_methods, class_properties, class_not_accessible_properties
    tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE1)

    possibilities = []
    # TODO precalculate this list and don't calculate it at every call
    for possible_name in all_global_available_obj_names:
        if possible_name in content:  # check if it's used in the testcase, e.g. is "Math" somewhere used? is "Array" somewhere?
            possibilities.append(possible_name)

    if "globalThis" in possibilities:
        possibilities.remove("globalThis")

    if len(possibilities) == 0:
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE2_FALLBACK)
        return testcase_mutators_helpers.get_special_random_operation(content, state, line_number)
    random_possibility = utils.get_random_entry(possibilities)

    merged_class_properties = class_properties.copy()
    merged_class_properties.update(class_not_accessible_properties)

    if utils.likely(0.1) or (len(class_methods[random_possibility]) == 0 and len(merged_class_properties[random_possibility]) == 0):
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE3)
        return testcase_mutators_helpers.get_special_random_operation(content, state, line_number)

    call_method = False
    if random_possibility in class_methods and random_possibility in merged_class_properties and len(
            class_methods[random_possibility]) != 0 and len(merged_class_properties[random_possibility]) != 0:
        # Available in both, so let random decide what to do
        if utils.likely(0.5):
            call_method = True
        else:
            call_method = False
    elif random_possibility in class_methods and len(class_methods[random_possibility]) != 0:
        call_method = True
    elif random_possibility in merged_class_properties and len(merged_class_properties[random_possibility]) != 0:
        call_method = False
    else:
        utils.perror("Logic flaw, should not occur. In get_random_operation_without_a_variable()")

    possible_other_variables = testcase_mutators_helpers.get_all_available_variables(state, line_number)

    line_to_return = ""
    if call_method:
        # Call at a method on a global object such as Math / Array / JSON / ...

        # TODO: This code leads in 35% of cases in an exception
        # Maybe avoid some functions which throw an exception when an incorrect argument is passed?

        # Edit:
        # I think this is now "fixed". The problem was that I also extracted functions from the prototype of a variable
        # e.g.: Object.getOwnPropertyNames((this["Array"].prototype))
        # returned ".fill()" as function
        # Then this code tried to add code like: Array.fill()
        # which is not available
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE4)
        number_args = utils.get_random_int(1, 5)
        args = ""
        for i in range(number_args):
            args += js.get_random_js_thing(possible_other_variables, state, line_number) + ","
        args = args[:-1]  # remove last ","
        random_method_name = utils.get_random_entry(list(class_methods[random_possibility]))
        line_to_return = "%s.%s(%s);" % (random_possibility, random_method_name, args)
    else:
        # Access (write) to a property of a global object such as Math / Array / JSON / ...

        random_property_name = utils.get_random_entry(list(merged_class_properties[random_possibility]))
        # Modify property
        if utils.likely(0.05):
            # just access property
            tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE5)
            line_to_return = "%s.%s;" % (random_possibility, random_property_name)
        else:
            # modify property
            tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE6)
            random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
            line_to_return = "%s.%s = %s;" % (random_possibility, random_property_name, random_value)

    (start_line_with, end_line_with) = testcase_mutators_helpers.get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE7)
        pass  # nothing to change
    else:
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_WITHOUT_A_VARIABLE8)
        line_to_return = start_line_with + testcase_mutators_helpers.iife_wrap(line_to_return) + end_line_with

    return line_to_return


def get_random_operation_from_database_without_a_variable(content, state, line_number):
    global database_generic_operations
    global database_generic_operations_single_operation

    database_to_use = database_generic_operations
    (operation, operation_state) = utils.get_random_entry(database_to_use)
    # important: don't call .strip() on operation, otherwise it could occur that the state is not correct (different number of lines)
    # I assume that this doesn't occur because I should have already called .strip() before adding it to the database
    # but just to get sure don't call it here again
    operation_state = operation_state.deep_copy()

    (start_line_with, end_line_with) = testcase_mutators_helpers.get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE1)

        # check if the line already ends with ";" => if not add a ";"
        if operation.endswith(";") is False:
            # In this case a ";" must be added
            tagging.add_tag(Tag.GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE2)
            operation = operation + ";"
    else:
        tagging.add_tag(Tag.GET_RANDOM_OPERATION_FROM_DATABASE_WITHOUT_A_VARIABLE3)
        # Important: The iife_wrap must not add a newline, otherwise the operation_state would be incorrect for the operation!
        operation = start_line_with + testcase_mutators_helpers.iife_wrap(operation) + end_line_with
        # TODO: Maybe if it's a single line operation I could avoid the "iife"? But does this really change anything?

    return operation, operation_state, None  # 3rd entry would be a variable name which must be renamed => it's a generic operation and therefore no variable name


def get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables, line_number,
                                                                   variable_name, variable_type):
    global obj_properties, obj_methods, obj_not_accessible_properties

    properties = None
    methods = None
    properties_not_readable = None

    if variable_type in obj_properties:
        properties = list(obj_properties[variable_type])

    if variable_type in obj_methods:
        methods = list(obj_methods[variable_type])

    if variable_type in obj_not_accessible_properties:
        properties_not_readable = list(obj_not_accessible_properties[variable_type])

    if properties is None and methods is None and properties_not_readable is None:
        utils.perror(
            "Does this really occur? Inside get_random_variable_property_or_method_operation_for_data_type() for data type: %s" % variable_type)

    if methods is None or utils.likely(float(len(properties)) / (len(properties) + len(methods))):
        # Perform property operation
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE1)
        if properties is None or (utils.likely(0.1) and len(properties_not_readable) != 0):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE2)
            random_property = utils.get_random_entry(properties_not_readable)
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE3)
            random_property = utils.get_random_entry(properties)
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "%s.%s = %s;" % (variable_name, random_property, random_value)
    else:
        # perform method call
        # TODO: Method call leads in 65% to an exception, property assignment just in 80%
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE4)
        random_method = utils.get_random_entry(methods)
        number_arguments = utils.get_random_int(1, 4)
        tmp_argument_str = ""
        for i in range(number_arguments):
            tmp_argument_str += js.get_random_js_thing(possible_other_variables, state, line_number) + ","
        tmp_argument_str = tmp_argument_str[:-1]  # remove last ","
        line_to_add = "%s.%s(%s);" % (variable_name, random_method, tmp_argument_str)
    return line_to_add


def get_random_variable_operation(content, state, line_number, variable_name, variable_types):
    global obj_methods, obj_properties

    tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION1)

    possible_other_variables = testcase_mutators_helpers.get_all_available_variables(state, line_number)
    # possible_variables = state.get_available_variables_in_line(line_number)

    protection_prefix = ""
    protection_suffix = ""
    if len(variable_types) > 1:
        # The variable has in this codeline different data types and therefore the operation must be protected
        # e.g. if the operation is called when the data type is different, then an exception would occur
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION2)

        protection_prefix = "try { "
        protection_suffix = "} catch { };"
        # TODO also implement other protections like "typeof" or a global counter variable
        # but they must be single-line! multi-line operations are here not allowed
        variable_type = utils.get_random_entry(list(variable_types))
    else:
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION3)
        variable_type = next(iter(variable_types))  # get the element

    variable_type_lower = variable_type
    variable_type = js_helpers.convert_datatype_str_to_real_JS_datatype(variable_type)

    if variable_type_lower == "string":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_string)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "int8array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_int8array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "uint8array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_uint8array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "uint8clampedarray":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_uint8clampedarray)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "int16array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_int16array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "uint16array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_uint16array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "int32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_int32array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "uint32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_uint32array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "float32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_float32array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "float64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_float64array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "bigint64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_bigint64array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "biguint64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_biguint64array)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "set":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_set)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "weakset":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_weakset)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "map":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_map)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "weakmap":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_weakmap)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "regexp":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_regexp)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "arraybuffer":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_arraybuffer)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "sharedarraybuffer":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_sharedarraybuffer)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "dataview":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_dataview)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "promise":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_promise)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.collator":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_collator)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.datetimeformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_datetimeformat)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.listformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_listformat)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.numberformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_numberformat)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.pluralrules":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_pluralrules)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.relativetimeformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_relativetimeformat)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "intl.locale":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl_locale)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "urierror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_urierror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "typeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_typeerror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "syntaxerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_syntaxerror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "rangeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_rangeerror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "evalerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_evalerror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "referenceerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_referenceerror)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "error":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_error)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "date":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_date)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "function":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_function)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "boolean":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_boolean)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "bigint":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_bigint)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)

    elif variable_type_lower == "object1":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_object1)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "object2":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_object2)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "unkown_object":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_unkown_object)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)

    elif variable_type_lower == "real_number":
        # Both are "Number" objects
        # TODO implement manual object operations
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_real_number)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)
    elif variable_type_lower == "special_number":
        # Both are "Number" objects
        # TODO implement manual object operations
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_special_number)
        line_to_add = get_random_variable_property_or_method_operation_for_data_type(state, possible_other_variables,
                                                                                     line_number, variable_name,
                                                                                     variable_type)

    # Everything below here are class operations because the objects can't be instantiated
    elif variable_type_lower == "globalThis":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_globalThis)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "symbol":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_symbol)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "math":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_math)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "json":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_json)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "reflect":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_reflect)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "atomics":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_atomics)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "intl":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_intl)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "webassembly":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)
    elif variable_type_lower == "webassembly.table":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_table)
        line_to_add = get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables,
                                                                                      line_number, variable_name,
                                                                                      variable_type)

    # Not implemented yet:
    elif variable_type_lower == "null":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_null)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "undefined":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_undefined)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.compileerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_compileerror)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.linkerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_linkerror)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.runtimeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_runtimeerror)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.module":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_module)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.instance":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_instance)
        return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type_lower == "webassembly.memory":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_webassembly_memory)
        return get_random_operation_without_a_variable(content, state, line_number)
    else:
        utils.perror("Missing data type in get_random_variable_operation(): %s" % variable_type_lower)
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_MISSING_DATATYPE_TODO)

    # TODO operations for number!
    # Operations for boolean variables ! flip the value!
    # HUGE TODO!!!!!!!!!!
    # utils.dbg_msg("variable_type: %s" % variable_type)
    """
    if variable_type != None and variable_type in obj_properties:
        properties = list(obj_properties[variable_type])
        methods = list(obj_methods[variable_type])
        properties_not_readable = list(obj_not_accessible_properties[variable_type])

        if utils.likely(float(len(properties)) / (len(properties) + len(methods))):
            # Perform property operation
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION4)
            if utils.likely(0.1) and len(properties_not_readable) != 0:
                random_property = utils.get_random_entry(properties_not_readable)
            else:
                random_property = utils.get_random_entry(properties)
            random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
            line_to_add = "%s.%s = %s;" % (variable_name, random_property, random_value)
        else:
            # perform method call
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION5)
            random_method = utils.get_random_entry(methods)
            number_arguments = utils.get_random_int(1,4)
            tmp_argument_str = ""
            for i in range(number_arguments):
                tmp_argument_str += js.get_random_js_thing(possible_other_variables, state, line_number) + ","
            tmp_argument_str = tmp_argument_str[:-1]    # remove last ","
            line_to_add = "%s.%s(%s);" % (variable_name, random_method, tmp_argument_str)
    elif variable_type == "undefined":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION6)
        if variable_name == "this" or variable_name == "new.target":
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION6b)
            # assignment to them are not allowed
            return get_random_operation_without_a_variable(content, state, line_number)
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION6c)
        random_js_code = js.get_random_js_thing(possible_other_variables, state, line_number)

        # TODO: This often results in an exception => maybe try-catch wrap it?
        # Does this code then lead to an exception or later code which tries to define the variable?
        line_to_add = "%s = %s;" % (variable_name, random_js_code)
    elif variable_type == "Number":
        print("TODO IMPLEMENT VARIABLE TYPE NUMBER")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION7_TODO)
        #sys.exit(-1)
        # TODO: This code gets never executed? Is the data type really correct?????
        return "todo1"
    elif variable_type == "Boolean":
        print("TODO IMPLEMENT VARIABLE TYPE Boolean")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION8_TODO)
        # TODO: This code gets never executed? Is the data type really correct?????
        #sys.exit(-1)
        return "todo2"
    elif variable_type == "globalThis":
        #utils.dbg_msg("[!] Should never occur because globalThis was removed")
        print("TODO IMPLEMENT VARIABLE TYPE globalThis")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION9_TODO)
        return "todo3"
        #return get_random_operation_without_a_variable(content, state, line_number)
    elif variable_type == "null":
        print("TODO IMPLEMENT VARIABLE TYPE null")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION10_TODO)
        return "todo4"
    elif variable_type == "Promise":
        print("TODO IMPLEMENT VARIABLE TYPE Promise")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION11_TODO)
        # TODO: Code is never executed!
        return "todo5"
    elif variable_type == "Symbol":
        print("TODO IMPLEMENT VARIABLE TYPE Symbol")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION12_TODO)
        return "todo6"
    elif variable_type == "Intl.Locale":
        print("TODO IMPLEMENT VARIABLE TYPE Intl.Locale")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION13_TODO)
        # TODO: Code is never executed!
        return "todo7"
    elif variable_type == "WebAssembly.Table":
        print("TODO IMPLEMENT VARIABLE TYPE WebAssembly.Table")
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION14_TODO)
        return "todo8"
    #tmp["array"] = "Array" ???
    else:
        # TODO: "globalThis"
        print("TODO: Variable type >%s< is not yet implemented!" % variable_type)
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION15_TODO)
        #for x in obj_properties:
        #    print(x)
        #sys.exit(-1)
        return "todo4"


    """
    line_to_add = protection_prefix + line_to_add + protection_suffix

    (start_line_with, end_line_with) = testcase_mutators_helpers.get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION16)
        pass  # nothing to change
    else:
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION17)
        line_to_add = start_line_with + testcase_mutators_helpers.iife_wrap(line_to_add) + end_line_with
    return line_to_add


def get_random_variable_property_or_method_operation_for_class_type(state, possible_other_variables, line_number,
                                                                    variable_name, variable_type):
    global class_properties, class_methods, class_not_accessible_properties

    properties = None
    methods = None
    properties_not_readable = None

    if variable_type in class_properties:
        properties = list(class_properties[variable_type])

    if variable_type in class_methods:
        methods = list(class_methods[variable_type])

    if variable_type in class_not_accessible_properties:
        properties_not_readable = list(class_not_accessible_properties[variable_type])

    if properties is None and methods is None and properties_not_readable is None:
        utils.perror(
            "Does this really occur? Inside get_random_variable_property_or_method_operation_for_class_type() for data type: %s" % variable_type)

    if methods is None or utils.likely(float(len(properties)) / (len(properties) + len(methods))):
        # Perform property operation
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE1)
        if properties is None or (utils.likely(0.1) and len(properties_not_readable) != 0):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE2)
            random_property = utils.get_random_entry(properties_not_readable)
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE3)
            random_property = utils.get_random_entry(properties)
        random_value = js.get_random_js_thing(possible_other_variables, state, line_number)
        line_to_add = "%s.%s = %s;" % (variable_name, random_property, random_value)
    else:
        # perform method call
        # TODO: Method call leads in 65% to an exception, property assignment just in 80%
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_PROPERTY_OR_METHOD_OPERATION_FOR_DATA_TYPE4)
        random_method = utils.get_random_entry(methods)
        number_arguments = utils.get_random_int(1, 4)
        tmp_argument_str = ""
        for i in range(number_arguments):
            tmp_argument_str += js.get_random_js_thing(possible_other_variables, state, line_number) + ","
        tmp_argument_str = tmp_argument_str[:-1]  # remove last ","
        line_to_add = "%s.%s(%s);" % (variable_name, random_method, tmp_argument_str)
    return line_to_add


# TODO: It doesn't make any sense to pass >variable_name< as parameter and return it
# both (parameter and return value) can be returned
def get_random_variable_operation_from_database(content, state, line_number, variable_name, variable_types):
    global database_variable_operations_list, database_variable_operations_states_list
    global database_variable_operations, database_variable_operations_single_operation, database_variable_other_operations, database_variable_other_operations_single_operation

    tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE1)

    protection_prefix = ""
    protection_suffix = ""
    if len(variable_types) > 1:
        # The variable has in this codeline different data types and therefore the operation must be protected
        # e.g. if the operation is called when the data type is different, then an exception would occur

        # TODO: This is incorrect! I can't insert try-finally at every possible location
        # e.g.:
        # var x = [1,2,
        # try { console.log("FOOBAR") } finally { },
        # 3];
        # => Throws an exception, but without try-finally it works!

        # TODO: This code is not very often executed 7200 times out of 2 million executions
        # And it results in 16% of cases still in an exception!

        # edit: Now I'm using try-catch instead (for some random reason I used try-finally lol?)
        # I think I had some reasons for this in the state creation code, but I can't remember why
        # I now fixed it to try-catch and I will later compare numbers if this leads to less exceptions (it obviously should)!
        # Numbers with "finally" and array properties + items: 28.49 % exceptions
        # Numbers with "catch" and array properties + items: TODO

        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE2)
        protection_prefix = "try { "
        protection_suffix = "} catch { };"
        variable_type = utils.get_random_entry(list(variable_types))
    else:
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE3)
        variable_type = next(iter(variable_types))  # get the element

    # variable_type is a lower-case variable type like "array" (and not "Array")

    if variable_type == "string":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_string)
    elif variable_type == "array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_array)
    elif variable_type == "int8array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int8array)
    elif variable_type == "uint8array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint8array)
    elif variable_type == "uint8clampedarray":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint8clampedarray)
    elif variable_type == "int16array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int16array)
    elif variable_type == "uint16array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint16array)
    elif variable_type == "int32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_int32array)
    elif variable_type == "uint32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_uint32array)
    elif variable_type == "float32array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_float32array)
    elif variable_type == "float64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_float64array)
    elif variable_type == "bigint64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_bigint64array)
    elif variable_type == "biguint64array":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_biguint64array)
    elif variable_type == "set":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_set)
    elif variable_type == "weakset":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_weakset)
    elif variable_type == "map":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_map)
    elif variable_type == "weakmap":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_weakmap)
    elif variable_type == "regexp":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_regexp)
    elif variable_type == "arraybuffer":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_arraybuffer)
    elif variable_type == "sharedarraybuffer":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_sharedarraybuffer)
    elif variable_type == "dataview":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_dataview)
    elif variable_type == "promise":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_promise)
    elif variable_type == "intl.collator":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_collator)
    elif variable_type == "intl.datetimeformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_datetimeformat)
    elif variable_type == "intl.listformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_listformat)
    elif variable_type == "intl.numberformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_numberformat)
    elif variable_type == "intl.pluralrules":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_pluralrules)
    elif variable_type == "intl.relativetimeformat":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_relativetimeformat)
    elif variable_type == "intl.locale":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl_locale)
    elif variable_type == "webassembly.module":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_module)
    elif variable_type == "webassembly.instance":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_instance)
    elif variable_type == "webassembly.memory":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_memory)
    elif variable_type == "webassembly.table":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_table)
    elif variable_type == "webassembly.compileerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_compileerror)
    elif variable_type == "webassembly.linkerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_linkerror)
    elif variable_type == "webassembly.runtimeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly_runtimeerror)
    elif variable_type == "urierror":
        # Operations on urierror lead in 6% of cases in a hang which is bad
        # But they are really not common, so therefore I can maybe keep them?
        # => TODO: Later when I add a mutation strategy which creates new variables
        # I must take care to not create too often a urierror
        # => otherwise I will get a lot of hangs which slows down fuzzing
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_urierror)
    elif variable_type == "typeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_typeerror)
    elif variable_type == "syntaxerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_syntaxerror)
    elif variable_type == "rangeerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_rangeerror)
    elif variable_type == "evalerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_evalerror)
    elif variable_type == "referenceerror":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_referenceerror)
    elif variable_type == "error":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_error)
    elif variable_type == "date":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_date)
    elif variable_type == "null":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_null)
    elif variable_type == "math":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_math)
        # TODO: Math operations lead to 88% exception rate!
        # That's the only data type with such a high error rate in the operations!
    elif variable_type == "json":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_json)
    elif variable_type == "reflect":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_reflect)
    elif variable_type == "globalThis":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_globalThis)
    elif variable_type == "atomics":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_atomics)
    elif variable_type == "intl":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_intl)
    elif variable_type == "webassembly":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_webassembly)
    elif variable_type == "object1":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_object1)
    elif variable_type == "object2":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_object2)
    elif variable_type == "unkown_object":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_unkown_object)
    elif variable_type == "real_number":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_real_number)
    elif variable_type == "special_number":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_special_number)
    elif variable_type == "function":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_function)
    elif variable_type == "boolean":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_boolean)
    elif variable_type == "symbol":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_symbol)
    elif variable_type == "undefined":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_undefined)
    elif variable_type == "bigint":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_bigint)
    else:
        utils.msg("[-] Missing data type in get_random_variable_operation_from_database(): %s" % variable_type)
        # TODO: This data type is also missing in the function which converts lower case to upper case data type
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE_MISSING_DATATYPE_TODO)

    database_to_use = None

    if variable_type not in database_variable_operations:
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE4)
        if variable_type not in database_variable_other_operations:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE5)
            # Note: This can happen if the used corpus is very small
            # => however, since I assume I'm just using good input corpus files to generate the databases
            # I want to see if this really happens (that I don't have variable operations for a specific data type)

            # utils.perror("Logic flaw! Database doesn't contain variable operation for data type: %s" % variable_type)

            # TODO:
            # "Logic flaw! Database doesn't contain variable operation for data type:  typeof real_variable;"
            # This really happens and for very strange entries like "typeof real_variable;"
            # When I have more time I should fix this, but since this is not common
            # I currently just add a generic operation instead

            # Hm, it occurred 1 time in 20 000 executions.... that's more common than I expected
            # maybe a state of a testcase is incorrect?

            # Edit: This mainly just occurs currently for type: evalerror
            # utils.msg("[-] PROBLEM! Database doesn't contain variable operation for data type: %s (variable name: %s)" % (variable_type, variable_name))
            return get_random_operation_from_database_without_a_variable(content, state, line_number)
        else:
            # Use the other operations database
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE6)
            database_to_use = database_variable_other_operations
    else:
        # There are entries for the data type in "database_variable_operations"
        if len(database_variable_operations[variable_type]) == 0:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE7)
            database_to_use = database_variable_other_operations
        elif len(database_variable_operations[variable_type]) <= 10 and utils.likely(0.9):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE8)
            database_to_use = database_variable_other_operations
        elif 100 >= len(database_variable_operations[variable_type]) > 10 and utils.likely(0.7):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE9)
            database_to_use = database_variable_other_operations
        elif utils.likely(0.9):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE10)
            database_to_use = database_variable_operations
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE11)
            database_to_use = database_variable_other_operations

    """
    # OLD CODE
    if end_line_with == ",":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE23)
        # single line operations must be used because multi line operations don't work in this context
        if database_to_use == database_variable_operations:
            database_to_use = database_variable_operations_single_operation
            if len(database_to_use[variable_type]) == 0:
                database_to_use = database_variable_other_operations_single_operation
                if len(database_to_use[variable_type]) == 0:
                    tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE24)
                    return get_random_operation_from_database_without_a_variable(content, state, line_number)
                else:
                    tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE25)
                    pass
            elif len(database_to_use[variable_type]) <= 10 and utils.likely(0.6):
                database_to_use = database_variable_other_operations_single_operation
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE26)
            elif len(database_to_use[variable_type]) <= 100 and len(database_to_use[variable_type]) > 10 and utils.likely(0.4):
                database_to_use = database_variable_other_operations_single_operation
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE27)
            else:
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE28)
                pass    # do nothing
        elif database_to_use == database_variable_other_operations:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE29)
            database_to_use = database_variable_other_operations_single_operation
        else:
            utils.perror("Logic flaw, should not occur (get_random_variable_operation_from_database())")
    """

    """
    # Old code (which likely contains a logic flaw)
    # TODO: I think I can remove this code when I see it again
    # TODO: Code is completely wrong because it doesn't access [variable_type] in the database when length is checked!
    if end_line_with == ",":
        # single line operations must be used because multi line operations maybe don't end with "," in the first line
        if len(database_variable_operations_single_operation) == 0:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE4)
            database_to_use = database_variable_other_operations_single_operation
        elif len(database_variable_operations_single_operation) <= 10 and utils.likely(0.9):
            # There are just a few operations in the database and therefore I use more frequently
            # operations from the other database
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE5)
            database_to_use = database_variable_other_operations_single_operation
        elif len(database_variable_operations_single_operation) <= 100 and len(database_variable_operations_single_operation) > 10 and utils.likely(0.7):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE6)
            database_to_use = database_variable_other_operations_single_operation
        elif utils.likely(0.9):   # 90% use the normal variable operations
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE7)
            database_to_use = database_variable_operations_single_operation
        else:   
            # 10% use "other" variable operations.
            # This are operations which were found for other data types but which also work for the current data type
            # for example: "var_TARGET_ instanceof Object"
            # => "var_TARGET_" can be an object of any type
            # => Since this are "generic" operations I don't add them too often
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE8)
            database_to_use = database_variable_other_operations_single_operation
    else:
        # multi line operations can be used
        if len(database_variable_operations) == 0:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE9)
            database_to_use = database_variable_other_operations
        elif len(database_variable_operations) <= 10 and utils.likely(0.9):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE10)
            database_to_use = database_variable_other_operations
        elif len(database_variable_operations) <= 100 and len(database_variable_operations) > 10 and utils.likely(0.5):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE11)
            database_to_use = database_variable_other_operations
        elif utils.likely(0.9):
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE12)
            database_to_use = database_variable_operations
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE13)
            database_to_use = database_variable_other_operations
    """

    database_to_use = database_to_use[variable_type]

    (operation_index, state_index) = utils.get_random_entry(database_to_use)
    operation = database_variable_operations_list[operation_index]
    operation_state = database_variable_operations_states_list[state_index]

    operation = protection_prefix + operation + protection_suffix

    (start_line_with, end_line_with) = testcase_mutators_helpers.get_start_and_end_line_symbols(state, line_number, content)
    if end_line_with == ";":
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE30)
        if operation.endswith(";") is False:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE31)
            operation = operation + ";"
    else:
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE32)
        operation = start_line_with + testcase_mutators_helpers.iife_wrap(operation) + end_line_with

    """
    # Old Code:
    if protection_prefix == "":
        if end_line_with == ",":
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE12)
            if operation.endswith(";"):
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE13)
                operation = operation.rstrip(";") + ","
            elif operation.endswith(","):
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE14)
                pass    # nothing to do
            else:
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE15)
                operation = operation + ","
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE16)
            # end_line_with == ";"
            if operation.endswith(","):
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE17)
                operation = operation.rstrip(",") + ";"
            elif operation.endswith(";"):
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE18)
                pass    # nothing to do
            else:
                tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE19)
                operation = operation + ";"
    else:
        if end_line_with == ",":
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE20)
            pass    # don't remove the pass
        else:
            tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE21)
            pass    # don't remove the pass
        operation = protection_prefix + operation + protection_suffix + end_line_with
    """

    operation_state = operation_state.deep_copy()  # create a copy, otherwise we would destroy the state of the operation during mutations

    # utils.msg("[i] Variable Operation for %s is: >%s<" % (variable_name, operation))

    # Important: Don't replace here "var_TARGET_" with >variable_name<
    # The operation must first be merged into the testcase before I rename the variable
    # otherwise the merging would again rename it.
    # Moreover: If variable_name is e.g. var_2_, it can happen that the operation itself also
    # uses var_2_. Therefore don't rename it here

    if "return " in operation:
        # some operations contain a "return" and if the current line is not in a function context
        # this will result in an exception.
        # I want to measure how often this occurs

        # edit: it occurs 58 365 in 2 million executions and exceptions are not that common
        # instead if 93% success rate I get ~88% success rate
        tagging.add_tag(Tag.GET_RANDOM_VARIABLE_OPERATION_FROM_DATABASE22)
        pass  # don't remove the pass => maybe I later automatically comment out all tagging.add_tag() lines

    # Debugging code
    # if variable_type == "real_number":
    #    print("Operation is:")
    #    print(operation)
    #    print("------------")

    return operation, operation_state, variable_name
