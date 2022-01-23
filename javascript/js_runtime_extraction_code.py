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



import javascript.js as js
import config as cfg
import javascript.js_helpers as js_helpers
import json


def extract_data_of_all_globals(exec_engine):
    class_methods = dict()
    class_properties = dict()
    class_not_accessible_properties = dict()

    obj_methods = dict()
    obj_properties = dict()
    obj_not_accessible_properties = dict()

    result = exec_engine.execute_once(js.get_code_to_extract_globals(), is_query=True)
    global_variables = json.loads(result.output)['globals']

    global_variables = set(global_variables)
    global_variables.update(set(js.get_instanceable_builtin_objects_full_list()))

    global_variables_filtered = [x for x in global_variables if x not in cfg.v8_globals_to_ignore]
    global_variables_str = ','.join(['"{}"'.format(value) for value in global_variables_filtered])

    # Extract the class properties / methods:
    code = js.get_code_to_query_functions_and_properties_of_variables(global_variables_str)
    result = exec_engine.execute_once(code, is_query=True)
    tmp_global_properties = json.loads(result.output)['properties']
    tmp_global_methods = json.loads(result.output)['methods']
    tmp_global_not_accessible_properties = json.loads(result.output)['notAccessibleProperties']
    for global_variable in tmp_global_properties:
        js.global_properties[global_variable] = tmp_global_properties[global_variable].split(";")
    for global_variable in tmp_global_methods:
        js.global_methods[global_variable] = tmp_global_methods[global_variable].split(";")
    for global_variable in tmp_global_not_accessible_properties:
        js.global_not_accessible_properties[global_variable] = tmp_global_not_accessible_properties[global_variable].split(";")
    # not accessible properties can't be read, but they can be re-assigned
    # E.g.:
    # "x = Map.prototype.size" => exception
    # vs. "Map.prototype.size = 1" => no exception

    for global_variable in js.global_methods:    # key is the global variable name, value is the list of methods
        if global_variable.endswith(".prototype"):
            global_variable_to_use = global_variable[:-10]
        else:
            global_variable_to_use = global_variable

        if global_variable_to_use not in class_methods:
            class_methods[global_variable_to_use] = set()
        for method_name in js.global_methods[global_variable]:
            method_name = method_name.strip()
            if method_name == "":
                continue

            class_methods[global_variable_to_use].add(method_name)

    for global_variable in js.global_properties:    # key is the global variable name, value is the list of properties
        if global_variable.endswith(".prototype"):
            global_variable_to_use = global_variable[:-10]
        else:
            global_variable_to_use = global_variable
        if global_variable_to_use not in class_properties:
            class_properties[global_variable_to_use] = set()
        for property_name in js.global_properties[global_variable]:
            property_name = property_name.strip()
            if property_name == "":
                continue

            if property_name not in class_methods[global_variable_to_use]:
                # if it's not a method it's really just a property
                class_properties[global_variable_to_use].add(property_name)

    for global_variable in js.global_not_accessible_properties:    # key is the global variable name, value is the list of properties
        if global_variable.endswith(".prototype"):
            global_variable_to_use = global_variable[:-10]
        else:
            global_variable_to_use = global_variable
        if global_variable_to_use not in class_not_accessible_properties:
            class_not_accessible_properties[global_variable_to_use] = set()
        for property_name in js.global_not_accessible_properties[global_variable]:
            property_name = property_name.strip()
            if property_name == "":
                continue

            if property_name not in class_methods[global_variable_to_use]:
                if property_name not in class_properties[global_variable_to_use]:
                    class_not_accessible_properties[global_variable_to_use].add(property_name)

    # Now extract the object properties/methods!
    not_instanceable_objects = js.get_NOT_instanceable_builtin_objects_full_list()
    not_instanceable_objects += js.get_not_handled_builtin_objects()

    not_instanceable_objects.remove("BigInt")   # we can create a bigInt but without the "new" word.

    for global_variable in global_variables:
        if global_variable in cfg.v8_globals_to_ignore:
            continue
        if global_variable in not_instanceable_objects:
            continue

        code_to_instantiate_obj = js_helpers.get_code_to_create_variable_of_datatype(global_variable)

        code = js.get_code_to_query_functions_and_properties_of_an_object(code_to_instantiate_obj)
        result = exec_engine.execute_once(code, is_query=True)
        if len(result.output) == 0:
            continue    # this happens when the global_variable is not available in the engine. E.g.: "InternalError" in v8
        tmp_global_properties = json.loads(result.output)['properties']
        tmp_global_methods = json.loads(result.output)['methods']
        tmp_global_not_accessible_properties = json.loads(result.output)['notAccessibleProperties']

        obj_methods[global_variable] = set()
        obj_properties[global_variable] = set()
        obj_not_accessible_properties[global_variable] = set()

        for method in tmp_global_methods.split(";"):
            method = method.strip()
            if method == "":
                continue
            obj_methods[global_variable].add(method)
        for prop in tmp_global_properties.split(";"):
            prop = prop.strip()
            if prop == "":
                continue
            if prop not in obj_methods[global_variable]:
                obj_properties[global_variable].add(prop)

        for prop in tmp_global_not_accessible_properties.split(";"):
            prop = prop.strip()
            if prop == "":
                continue
            if prop not in obj_methods[global_variable]:
                if prop not in obj_properties[global_variable]:
                    obj_not_accessible_properties[global_variable].add(prop)

    return class_methods, class_properties, class_not_accessible_properties, obj_methods, obj_properties, obj_not_accessible_properties
