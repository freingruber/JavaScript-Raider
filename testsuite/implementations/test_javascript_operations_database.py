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



# This script checks if my variable operations database contains all operations
# which are required to trigger different CVEs
# It can be used to measure the "quality" of my database
# E.g. if some operations which are required for a CVE are not found in the database
# the fuzzer can likely not reproduce the CVE PoC code
# (That's not 100% true because I'm also using different techniques than operations from the database
# but it means that I need to enhance my database because something is missing)
# Note: I don't need to have 100% of all tested operations in the database
# I just need to know which operations are not stored in it (and why they are not stored in the database/corpus)
# => Then I can write mutation strategies which trigger these operations manually

# I'm also using this script to compare different versions of my create database script
# E.g.: after doing some optimizations => does the new database still contain the important operations?

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import pickle
import config as cfg
import utils
from testsuite.testcases_for_corpus_quality import expected_operations_in_database


database_generic_operations = None
database_variable_operations = None
database_variable_other_operations = None
database_variable_operations_list = None
database_variable_operations_states_list = None

number_hits_main_database = 0
number_hits_other_database = 0


def test_javascript_operations_database_quality():
    utils.msg("\n")
    utils.msg("[i] " + "-" * 100)
    utils.msg("[i] Going to start javascript operations database quality tests...")

    if load_databases() is False:
        utils.msg("[!] Operations databases could not be loaded! You first need to create them via data_extractors\\create_pickle_database_for_variable_operations.py! Skipping tests..")
        return      # skip tests

    number_successful_tests = 0
    number_of_tests = 0

    # Check the variable operations:
    for entry in expected_operations_in_database:
        (required_operation_code, variable_datatype) = entry
        number_of_tests += 1

        is_code_in_database = False
        if variable_datatype == "any":
            is_code_in_database = is_operation_in_any_database(required_operation_code)
        else:
            is_code_in_database = is_variable_operation_in_database(required_operation_code, variable_datatype)

        if is_code_in_database:
            number_successful_tests += 1

    utils.msg("[i] Variable operations: In the >main< database %d operations were found, in the >others< database %d operations were found." % (
        number_hits_main_database,
        number_hits_other_database))

    if number_of_tests == number_successful_tests:
        utils.msg("[+] JS database quality result: All %d performed checks were passed!" % number_of_tests)
    else:
        success_rate = (float(number_successful_tests) / number_of_tests) * 100.0

        utils.msg("[!] JS database quality result: %d of %d tests were successful (%.2f %%)!" % (number_successful_tests, number_of_tests, success_rate))

    utils.msg("[i] " + "-" * 100)


def load_databases():
    global database_generic_operations, database_variable_operations, database_variable_other_operations
    global database_variable_operations_list, database_variable_operations_states_list

    if os.path.isfile(cfg.pickle_database_generic_operations) is False:
        return False    # Database doesn't exist

    if os.path.isfile(cfg.pickle_database_variable_operations) is False:
        return False    # Database doesn't exist

    if os.path.isfile(cfg.pickle_database_variable_operations_others) is False:
        return False    # Database doesn't exist

    if os.path.isfile(cfg.pickle_database_variable_operations_list) is False:
        return False    # Database doesn't exist

    if os.path.isfile(cfg.pickle_database_variable_operations_states_list) is False:
        return False    # Database doesn't exist

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

    return True     # all databases loaded


def is_operation_in_any_database(variable_operation_code):
    global database_generic_operations, database_variable_operations, database_variable_operations_list
    global database_variable_other_operations

    # Check the generic operations:
    for entry in database_generic_operations:
        (operation, state) = entry
        if variable_operation_code in operation:
            return True

    # Check the variable operations for all variable types:
    for variable_datatype in database_variable_operations.keys():
        for entry in database_variable_operations[variable_datatype]:
            (operation_index, state_index) = entry
            operation = database_variable_operations_list[operation_index]
            if variable_operation_code in operation:
                return True     # operation was found

    # Check the other operations for all variable types:
    for variable_datatype in database_variable_other_operations.keys():
        for entry in database_variable_other_operations[variable_datatype]:
            (operation_index, state_index) = entry
            operation = database_variable_operations_list[operation_index]
            if variable_operation_code in operation:
                return True  # operation was found

    return False


def is_variable_operation_in_database(variable_operation_code, variable_datatype):
    global database_variable_operations, database_variable_operations_list
    global number_hits_main_database, number_hits_other_database
    global database_variable_other_operations

    if variable_datatype == "any":
        utils.perror("Internal coding error, this should never occur")

    # Check the main operations database:
    for entry in database_variable_operations[variable_datatype]:
        (operation_index, state_index) = entry
        operation = database_variable_operations_list[operation_index]
        if variable_operation_code in operation:
            number_hits_main_database += 1
            return True     # operation was found

    # Check the "others" operations database:
    for entry in database_variable_other_operations[variable_datatype]:
        (operation_index, state_index) = entry
        operation = database_variable_operations_list[operation_index]
        if variable_operation_code in operation:
            number_hits_other_database += 1
            return True  # operation was found

    return False
