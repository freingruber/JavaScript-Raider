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


# This script extracts variable operations from a JavaScript corpus
# All extracted operations are executed in a JS engine to ensure that they don't throw an exception
# TODO: Script must heavily be refactored and improved
# Basically, the whole script should completely be rewritten
# (maybe with a 3rd party JS parsing library; or I need to develop better JS parsing code).
# At the current moment, I highly advise against using the script...
# The extracted operations are partial not really useful and other important operations are missed
# There is a lot of room for improvements in this script.


# Script runtime 1-3 days with a corpus of ~13 000 files with 49 MB
# (just JS files; size was calculated with "du -ach *.js")
# Other data: Corpus with 10 000 files with 42 MB took ~18 hours to process.


# TODO: Ensure that permanently disabled functions (like all the Web Assembly stuff)
# are not inserted into the database? Also no native functions

# TODO: Currently I don't use coverage feedback here, but I should adapt this

# TODO: Currently, the resulting database still contains a lot of "useless" entries
# => I need filter them better. For example, it's possible that a "variable operation" looks like:
# 1,5,"foobar",var_TARGET_,8
# =>
# This is obviously not a real variable operation, but the database contains entries like this (a lot of entries!)



import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import pickle
from native_code.executor import Execution_Status

import utils
import state_creation.create_state_file as create_state_file
import javascript.js_renaming as js_renaming
import javascript.js_helpers as js_helpers
import testcase_helpers
import config as cfg
import data_extractors.extract_operations.extract_helpers as extract_helpers
import data_extractors.extract_operations.testcase_operations_extractor as testcase_operations_extractor

# I store the hashes of extracted operations in these variables to skip
# Operations which are the same. The hashes are not just hashes of the operation
# (otherwise I could just use a set() to store the operations), instead, they are
# the hashes of normalized operations (e.g.: with removed strings or numbers).
all_variable_operations_hashes = dict()
all_generic_operations_hashes = set()
all_variable_operations_others_hashes = dict()


# I store in a list all states and just store the list index together with the operation
# e.g. if operation1 can be applied to datatype1 and datatype2, then I don't need to store 2 states for operation1
# (and more important: I don't need to calculate 2 states!)
# Instead, I store it in this list, e.g. at position 43
# And then I store for the operation (for both data types) the state ID 43. Later I can immediately access the state using index 43.
# I can also do the same for the "operations" code to not store the code multiple times.
# This is important because the operation database must be in memory during fuzzing and I'm limited to 1 GB RAM per fuzzer
# when I want to keep machine cost on GCE small..
# Edit: Later I changed to a bigger GCE machine, but the operation database is still huge. This optimization is important
# to keep the memory usage low.
# It also helps especially for the "other variable operations" database. => The operations in this database are shared between
# multiple data types which means a lot of state creations can be skipped.
variable_operations_states_list_global = []        # stores the states
variable_operations_list_global = []               # stores the operations code

mapping_operation_hash_to_state_index = dict()
mapping_operation_hash_to_operation_index = dict()

# If I have one operation and it contains var_TARGET_,
# then in most cases the calculated state should be the same when
# the operation is possible for datatype1 and datatype2
# e.g. If I assign var_TARGET_ datatype1 and calculate the state
# and I do the same for again and assign var_TARGET_ datatype2,
# then both states should be similar (e.g. variable types of other variables should be the same)
# However, that's not always the case.
# if for example the operation is:
# let var_2_ = (1 == 1 ? var_TARGET_  : .......)
# Then var_2_ would become the same data type as var_TARGET_
# So in most cases I don't have to calculate the state again (and store it again), but in some cases
# I must do this.
# My solution: I'm storing operation states two times, one time for datatype1 and one time for datatype2
# If both are the same, I then mark the operation as "stable state" and don't calculate the state again for datatype3, datatype4, ...
mapping_operation_hash_to_stable_state = dict()
mapping_operation_hash_to_enhanced_operation = dict()
mapping_operation_hash_to_datatype_for_which_state_was_calculated = dict()


test_cache = dict()


# This function will create a database of operations extracted from the corpus
# Pre-requirement: The corpus must already be loaded and stored in cfg.corpus_js_snippets
# and the execution engine must be initialized and stored in cfg.exec_engine
def create_database():
    # Extract a base-set of operations from the corpus:
    utils.msg("[i] Going to extract operations from testcases...")
    testcase_operations_extractor.clear_extracted_operations()
    for testcase_entry in cfg.corpus_js_snippets.corpus_iterator():
        (tc_content, tc_state, filename) = testcase_entry
        utils.msg("[i] Going to handle file: %s" % filename)
        testcase_operations_extractor.extract_operations_from_testcase(tc_content, tc_state)

    (all_variable_operations, all_generic_operations) = testcase_operations_extractor.get_extracted_operations()
    utils.msg("[i] Finished extraction of operations.")

    print_extracted_operations("Initially extracted operations:", all_generic_operations, all_variable_operations, None)

    # Remove duplicates:
    (all_variable_operations, all_generic_operations) = remove_duplicates_from_identified_operations_statically(
        all_variable_operations,
        all_generic_operations
    )
    print_extracted_operations("Operations after removing duplicates:", all_generic_operations, all_variable_operations, None)

    # Calculate the "other" variable operations (opposite to the >main< variable operations)
    # "Other" variable operations are operations which were found for data type X in the corpus,
    # but which also work (don't throw an exception) for data type Y.
    # Example: the database contains the operation "var_1_ instanceof Array" and var_1_ is an Array.
    utils.msg("[i] Going to calculate >other< variable operations")
    all_variable_operations_others = calculate_other_variable_operations(all_variable_operations)

    print_extracted_operations("Operations with other variables:", all_generic_operations, all_variable_operations, all_variable_operations_others)

    # The three output variables which store the databases are:
    # *) all_generic_operations
    # *) all_variable_operations
    # *) all_variable_operations_others
    # => If execution of the script takes too long, you can save here the content of the variables
    # to pickle files and then skip the first function calls and start at this point by loading
    # the pickle databases.
    save_data_snapshot("snapshot1", all_generic_operations, all_variable_operations, all_variable_operations_others)
    (all_generic_operations, all_variable_operations, all_variable_operations_others) = load_data_snapshot("snapshot1")

    # Now check if the identified operations are correct and don't throw an exception (or timeout or crash)
    # This is done dynamically by executing the operations (which is time consuming).
    utils.msg("[i] Going to check if the identified operations are valid...")
    (all_generic_operations_working,
     all_variable_operations_working,
     all_variable_operations_others_working,
     all_generic_operations_exception,
     all_variable_operations_exception,
     all_variable_operations_others_exception) = \
        check_if_identified_operations_are_valid(all_generic_operations, all_variable_operations, all_variable_operations_others)
    utils.msg("[i] Finished checking if operations are valid.")

    print_extracted_operations("Operations working:", all_generic_operations_working, all_variable_operations_working, all_variable_operations_others_working)
    # print_extracted_operations("Operations not working:", all_generic_operations_exception, all_variable_operations_exception, all_variable_operations_others_exception)

    save_data_snapshot("snapshot2", all_generic_operations_working, all_variable_operations_working, all_variable_operations_others_working)
    save_data_snapshot("snapshot2_exception_operations", all_generic_operations_exception, all_variable_operations_exception, all_variable_operations_others_exception)
    (all_generic_operations_working, all_variable_operations_working, all_variable_operations_others_working) = load_data_snapshot("snapshot2")


    # Now calculate the states for the generic operations.
    # (the operations for generic and variable operations are split into 2 function calls to make snapshots
    # in between because state creation is time consuming).
    # Before state calculation, the operations are first "enhanced"
    # (e.g.: variable tokens are renamed or function results are stored in new variables).
    all_generic_operations_with_state = enhance_and_calculate_states_for_generic_operations(all_generic_operations_working)
    all_generic_operations_with_state = fix_generic_operations(all_generic_operations_with_state)   # Remove operations which can't be combined with other testcases:

    # Save the first result database (generic operations):
    with open(cfg.pickle_database_generic_operations, 'wb') as fout:
        pickle.dump(all_generic_operations_with_state, fout, pickle.HIGHEST_PROTOCOL)
    utils.msg("[+] Successfully saved calculated generic operations database at: %s" % all_generic_operations_with_state)

    # Now do the same for variable operations:
    (all_variable_operations_with_state,
     all_variable_operations_others_with_state,
     variable_operations_states_list,
     variable_operations_list) = \
        enhance_and_calculate_states_for_variable_operations(all_variable_operations_working, all_variable_operations_others_working)

    (all_variable_operations_with_state,
     all_variable_operations_others_with_state,
     variable_operations_states_list,
     variable_operations_list) = fix_variable_operations(all_variable_operations_with_state,
                                                         all_variable_operations_others_with_state,
                                                         variable_operations_states_list,
                                                         variable_operations_list)

    # Save the results:
    with open(cfg.pickle_database_variable_operations, 'wb') as fout:
        pickle.dump(all_variable_operations_with_state, fout, pickle.HIGHEST_PROTOCOL)
    with open(cfg.pickle_database_variable_operations_others, 'wb') as fout:
        pickle.dump(all_variable_operations_others_with_state, fout, pickle.HIGHEST_PROTOCOL)
    with open(cfg.pickle_database_variable_operations_states_list, 'wb') as fout:
        pickle.dump(variable_operations_states_list, fout, pickle.HIGHEST_PROTOCOL)
    with open(cfg.pickle_database_variable_operations_list, 'wb') as fout:
        pickle.dump(variable_operations_list, fout, pickle.HIGHEST_PROTOCOL)
    utils.msg("[+] Finished extraction of operations! All databases were saved.")


def save_data_snapshot(snapshot_name, generic_operations, variable_operations, variable_operations_others):
    tmp_folder_path = os.path.join(cfg.output_dir, "tmp")
    if os.path.exists(tmp_folder_path) is False:
        os.makedirs(tmp_folder_path)
    # TODO: What is with the "_hashes" variables? I should also snapshot them
    filepath_generic_operations = os.path.join(tmp_folder_path, "%s_database_generic_operations.pickle" % snapshot_name)
    filepath_variable_operations = os.path.join(tmp_folder_path, "%s_database_variable_operations.pickle" % snapshot_name)
    filepath_variable_operations_others = os.path.join(tmp_folder_path, "%s_database_variable_operations_others.pickle" % snapshot_name)
    with open(filepath_generic_operations, 'wb') as fout:
        pickle.dump(generic_operations, fout, pickle.HIGHEST_PROTOCOL)
    with open(filepath_variable_operations, 'wb') as fout:
        pickle.dump(variable_operations, fout, pickle.HIGHEST_PROTOCOL)
    with open(filepath_variable_operations_others, 'wb') as fout:
        pickle.dump(variable_operations_others, fout, pickle.HIGHEST_PROTOCOL)


def load_data_snapshot(snapshot_name):
    tmp_folder_path = os.path.join(cfg.output_dir, "tmp")
    filepath_generic_operations = os.path.join(tmp_folder_path, "%s_database_generic_operations.pickle" % snapshot_name)
    filepath_variable_operations = os.path.join(tmp_folder_path, "%s_database_variable_operations.pickle" % snapshot_name)
    filepath_variable_operations_others = os.path.join(tmp_folder_path, "%s_database_variable_operations_others.pickle" % snapshot_name)
    with open(filepath_generic_operations, 'rb') as finput:
        generic_operations = pickle.load(finput)
    with open(filepath_variable_operations, 'rb') as finput:
        variable_operations = pickle.load(finput)
    with open(filepath_variable_operations_others, 'rb') as finput:
        variable_operations_others = pickle.load(finput)
    return generic_operations, variable_operations, variable_operations_others


def calculate_other_variable_operations(all_variable_operations):
    # also try the operations from other data types for variables of different data type:
    # e.g. if data type array has code like : "var_TARGET_ instanceof XYZ"
    # Then I can also use this operation for strings for example...
    # This function calculates the required operations
    global all_variable_operations_hashes
    global all_variable_operations_others_hashes

    all_variable_operations_others = dict()

    for variable_type in all_variable_operations:
        new_operations = set()
        new_operations_hashes = set()
        for variable_type2 in all_variable_operations:
            if variable_type == variable_type2:
                # skip operations for the correct data type, they are already stored in >all_variable_operations<
                continue
            if variable_type2 == "function" or variable_type2 == "array" or variable_type2 == "real_number" or variable_type2 == "string":
                # they have a lot of operations which would make the list of other operations very very long
                continue    

            for operation in all_variable_operations[variable_type2]:
                operation_hash = extract_helpers.get_hash_of_normalized_operation(operation)
                if operation_hash not in new_operations_hashes and operation_hash not in all_variable_operations_hashes[variable_type]:
                    # not previously seen => it's a "new" operation
                    new_operations.add(operation)
                    new_operations_hashes.add(operation_hash)
        all_variable_operations_others[variable_type] = new_operations      # save results
        all_variable_operations_others_hashes[variable_type] = new_operations_hashes
    return all_variable_operations_others


# It's likely that the operations database contains similar operations which just use different data
# Example: "var_TARGET_.length = 5" and "var_TARGET_.length = 12"
# => in this case the fuzzer should just store one of the operations because both are the same (only the data is different).
# Currently I do this by calculating a hash over the operation (and skipping the data), but
# later I can measure code coverage feedback to detect duplicates.
# TODO: Implement code coverage feedback to detect duplicates
def remove_duplicates_from_identified_operations_statically(all_variable_operations, all_generic_operations):
    global all_variable_operations_hashes, all_generic_operations_hashes

    # e.g. if an operation is:
    # var_TARGET_.length = 5
    # 
    # and another operation is:
    # var_TARGET_.length = 12
    # 
    # Then I should just add one of these operations.
    # I identify such "duplicates" by removing all numbers from the operation and then calculating the hash
    # if the hash is already known, the operation must not be added (because it's a duplicate)
    # another such operation is an array access with different indexes.
    # 
    # A similar logic can be used to remove strings, for example:
    # parseInt("12")
    # and
    # parseInt("53")
    # => both operations are the same and this can be identified by rewriting the operation to
    # parseInt("")
    # (the string was replaced by an empty string)
    # => then calculate the hash and check if the hash was already seen
    # Note: This would already be found by removing numbers, but the same idea can also be applied to string-arguments

    # Fix generic operations:
    new_all_generic_operations = set()
    new_all_generic_operations_hashes = set()
    for operation in all_generic_operations:
        operation_hash = extract_helpers.get_hash_of_normalized_operation(operation)
        if operation_hash not in new_all_generic_operations_hashes:
            # not previously seen => it's a "new" operation
            new_all_generic_operations.add(operation)
            new_all_generic_operations_hashes.add(operation_hash)
    all_generic_operations = new_all_generic_operations         # save results
    all_generic_operations_hashes = new_all_generic_operations_hashes

    # Fix variable operations:
    for variable_type in all_variable_operations:
        new_operations = set()
        new_operations_hashes = set()
        for operation in all_variable_operations[variable_type]:
            operation_hash = extract_helpers.get_hash_of_normalized_operation(operation)
            if operation_hash not in new_operations_hashes:
                # not previously seen => it's a "new" operation
                new_operations.add(operation)
                new_operations_hashes.add(operation_hash)
        all_variable_operations[variable_type] = new_operations         # save results
        all_variable_operations_hashes[variable_type] = new_operations_hashes
    return all_variable_operations, all_generic_operations


def try_to_fix_testcase(code):
    # it can happen that some operations contain incorrect code
    # This occurs because the code to add dependencies (or to identify instructions)
    # is pretty hacky.
    # For example: tc7759.js
    # It contains this code line (as an operation):
    # const var_4_ = var_5_.unshift(var_3_);
    # 
    # This requires that "var_3_" gets added as a dependency, which is defined one line before:
    # for (let var_3_ = 0; var_3_ < 3; var_3_++) {
    # => this leads to the following code:
    # 
    # for (let var_1_ = 0; var_1_ < 3; var_1_++) {
    # var_TARGET_.unshift(var_1_)
    # 
    # => the problem is that the "{" from the for loop is never closed.
    # I could add code in "add_dependency" to also add all other code until the "}" occurs
    # however, this would likely add also "useless" code lines which are not connected to the operation
    # And it could lead to problems if "(" and ")" is used instead of "{" and "}" (in function invocations)
    #
    # => The simplest approach is to just add a "}" at the end myself+
    # This is exactly what this function attempts. If an operation fails, this code tries
    # to add the correct amount of ")", "]" and "}" symbols at the end (in the correct order)

    # Note: currently I try to keep it simple and just fix "most of the testcases" but not all
    # so currently I dont consider "(" symbols in strings and so on... (this does not occur too often)

    current_brackets = ""
    fixed_code = ""
    for symbol in code:
        if symbol == "(":
            current_brackets += "("
        elif symbol == "[":
            current_brackets += "["
        elif symbol == "{":
            current_brackets += "{"
        elif symbol == ")":
            while True:
                if len(current_brackets) != 0:
                    prev_bracket = current_brackets[-1]
                    if prev_bracket == "(":
                        # that's the good case and everything is fine
                        # no need to modify the symbol
                        current_brackets = current_brackets[:-1]    # remove the last "(" symbol
                        break
                    elif prev_bracket == "{":
                        # bad case, a "}" is missing
                        symbol = "\n}" + symbol   # add a "}" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "{" symbol
                        continue
                    elif prev_bracket == "[":
                        # bad case, a "]" is missing
                        symbol = "\n]" + symbol   # add a "]" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "[" symbol
                        continue
                else:
                    # in this case was no opening "(" symbol, so just add it
                    symbol = symbol[:-1] + "\n()"
                    break
        elif symbol == "]":
            while True:
                if len(current_brackets) != 0:
                    prev_bracket = current_brackets[-1]
                    if prev_bracket == "[":
                        # that's the good case and everything is fine
                        # no need to modify the symbol
                        current_brackets = current_brackets[:-1]    # remove the last "[" symbol
                        break
                    elif prev_bracket == "{":
                        # bad case, a "}" is missing
                        symbol = "\n}" + symbol   # add a "}" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "{" symbol
                        continue
                    elif prev_bracket == "(":
                        # bad case, a ")" is missing
                        symbol = "\n)" + symbol   # add a ")" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "(" symbol
                        continue
                else:
                    # in this case was no opening "[" symbol, so just add it
                    symbol = symbol[:-1] + "\n[]"
                    break
        elif symbol == "}":
            while True:
                if len(current_brackets) != 0:
                    prev_bracket = current_brackets[-1]
                    if prev_bracket == "{":
                        # that's the good case and everything is fine
                        # no need to modify the symbol
                        current_brackets = current_brackets[:-1]    # remove the last "{" symbol
                        break
                    elif prev_bracket == "(":
                        # bad case, a ")" is missing
                        symbol = "\n)" + symbol   # add a ")" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "(" symbol
                        continue
                    elif prev_bracket == "[":
                        # bad case, a "]" is missing
                        symbol = "\n]" + symbol   # add a "]" before the symbol to fix the code
                        current_brackets = current_brackets[:-1]    # remove the last "[" symbol
                        continue
                else:
                    # in this case was no opening "(" symbol, so just add it
                    symbol = symbol[:-1] + "\n{}"
                    break
        else:
            pass    # nothing to do

        fixed_code += symbol

    while len(current_brackets) != 0:
        symbol = current_brackets[-1]
        current_brackets = current_brackets[:-1]    # remove the last symbol
        if symbol == "(":
            fixed_code += "\n)"
        elif symbol == "[":
            fixed_code += "\n]"
        elif symbol == "{":
            fixed_code += "\n}"
        else:
            utils.perror("Internal logic flaw")
    
    return fixed_code


def get_operation_and_state_indexes(operation, variable_type):
    global mapping_operation_hash_to_operation_index
    global mapping_operation_hash_to_state_index
    global variable_operations_list_global
    global variable_operations_states_list_global
    global mapping_operation_hash_to_enhanced_operation
    global mapping_operation_hash_to_datatype_for_which_state_was_calculated
    global mapping_operation_hash_to_stable_state

    original_operation_code = operation

    # Store operation / get operation index
    operation_hash = utils.calc_hash(operation)
    if operation_hash in mapping_operation_hash_to_operation_index:
        operation_index = mapping_operation_hash_to_operation_index[operation_hash]
        operation = variable_operations_list_global[operation_index]   # get the maybe enhanced version of the operation
        
        utils.msg("[i] Loaded cached operation for hash %s and data type %s : \n>>%s<<" % (operation_hash, variable_type, operation))
        utils.msg("[i] Original (not enhanced) code was: \n>>%s<<" % original_operation_code)

        # this is required if the state must be recalculated and the cached one can't be used (e.g. because it's unstable)
    else:
        # operation is not stored yet, so store it...
        utils.msg("[i] Before enhancing: \n>>%s<<" % operation)
        operation = enhance_operation(operation, variable_type)   # first enhance it (variable renaming, ...)

        variable_operations_list_global.append(operation)
        operation_index = len(variable_operations_list_global) - 1
        utils.msg("[i] Storing at idx %d operation hash %s for data type %s the operation: \n>>%s<<" % (operation_index, operation_hash, variable_type, operation))
        mapping_operation_hash_to_operation_index[operation_hash] = operation_index
        mapping_operation_hash_to_enhanced_operation[operation_hash] = operation

    state_must_be_calculated = False
    first_state_calculation = False

    # Get or calculate the state
    if operation_hash in mapping_operation_hash_to_state_index:
        state_index = mapping_operation_hash_to_state_index[operation_hash]
        first_state_calculation = False
        previous_datatype = mapping_operation_hash_to_datatype_for_which_state_was_calculated[operation_hash]
        utils.msg("[i] State file for %s is already cached for data type %s" % (operation_hash, previous_datatype))

        if previous_datatype == variable_type:
            # The same operation was already calculated for the same data type
            # This can occur when an operation is stored in the normal operations list
            # and in the "others" operation list
            # In this case I can skip the operation because I don't want an operation in the "others" list
            # when it's already in the normal operations list
            utils.msg("[i] Data types are the same, so don't store the operation again because it's already stored\n\n")
            utils.msg("[i] END2 of get_operation_and_state_indexes()\n\n")
            return None, None

        is_stable = mapping_operation_hash_to_stable_state[operation_hash]
        utils.msg("[i] Operation hash %s is_stable is: %s" % (operation_hash, is_stable))
        if is_stable == "unkown":
            state_must_be_calculated = True     # this occurs in the 2nd state calculation for an operation (with a different datatype) =>
        elif is_stable == "unstable":
            state_must_be_calculated = True     # state is unstable and must therefore always be recalculated
        elif is_stable == "stable":
            state_must_be_calculated = False    # state is stable and the previous calculation result can be taken
        else:
            utils.perror("Logic flaw in is_stable code, should not occur")
    else:
        # state must be calculated because it was not calculated yet for this operation
        state_must_be_calculated = True
        first_state_calculation = True

    if state_must_be_calculated:
        utils.msg("[i] State must be calculated!")
        # Important don't add a newline after the prefix code
        # => this ensures that line-numbers are correct in the final testcase
        prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type)
        code = prefix_code + operation
        state = create_state_file.create_state_file_safe(code)

        if first_state_calculation:
            utils.msg("[i] New (not cached) operation (first_state_calculation == True)")
            variable_operations_states_list_global.append(state)
            state_index = len(variable_operations_states_list_global) - 1

            mapping_operation_hash_to_state_index[operation_hash] = state_index

            mapping_operation_hash_to_datatype_for_which_state_was_calculated[operation_hash] = variable_type
            mapping_operation_hash_to_stable_state[operation_hash] = "unkown"
        else:
            utils.msg("[i] There is already a cached operation but, so check the is_stable status...")
            # It's not the first calculation
            # This means "is_stable" must be "unstable" or "unkown"
            # If it's "unstable" nothing must be done
            if is_stable == "unkown":
                previous_state_index = mapping_operation_hash_to_state_index[operation_hash]
                previous_state = variable_operations_states_list_global[previous_state_index]

                if "var_TARGET_" not in operation:
                    utils.msg("[i] Error: Incorrect operation: >>>%s<<<" % operation)      # log it so that I can manually check if the states are really unstable
                    utils.msg("[i] operation_hash: %s" % operation_hash)
                    utils.msg("[i] Original operation: %s" % original_operation_code)
                    utils.msg("[i] Datatype: %s" % variable_type)
                    sys.exit(-1)

                # The two states "previous_state" and "state" must now be compared
                # This especially means that the data types of variables must be compared
                # If the code in the operation contained something like:
                # var var_1_ = var_TARGET_;
                # 
                # => The state would be unstable because for datatype1 the variable var_1_ would have datatype1
                # and for datatype2 for var_TARGET_ it would have datatype2...
                # This means the state must be re-calculated per datatype
                # On the other hand: If the datatype of var_TARGET_ is not assigned to another available variable
                # then the state is stable and must not be calculated for every data type and can be cached ("stable" state)
                # The following code checks if the state is stable by comparing two state calculations from different data types

                if state.compare_state(previous_state):
                    states_are_the_same = True
                else:
                    states_are_the_same = False

                """
                # TODO: Maybe move the code which compares the two states into the testcase_state.py class?
                
                # Check variable data types
                for variable_name in previous_state.variable_types:
                    entries_previous_state = previous_state.variable_types[variable_name]
                    if variable_name not in state.variable_types:
                        utils.msg("[i] states_are_the_same False1")
                        states_are_the_same = False
                        break
                    for current_entry in state.variable_types[variable_name]:
                        if current_entry in entries_previous_state:
                            continue
                        # If this point is reached there is an entry with a different datatype/line number
                        # => the states are not the same
                        utils.msg("[i] states_are_the_same False2")
                        states_are_the_same = False
                        break
                    if states_are_the_same == False:
                        break
                
                # Also check items of arrays and properties
                if states_are_the_same == True:
                    for variable_name in previous_state.array_items_or_properties:
                        entries_previous_state = previous_state.array_items_or_properties[variable_name]
                        if variable_name not in state.array_items_or_properties:
                            utils.msg("[i] states_are_the_same False3")
                            states_are_the_same = False
                            break
                        for current_entry in state.array_items_or_properties[variable_name]:
                            if current_entry in entries_previous_state:
                                continue
                            # If this point is reached there is an entry with a different datatype/line number
                            # => the states are not the same
                            utils.msg("[i] states_are_the_same False4")
                            states_are_the_same = False
                            break
                        if states_are_the_same == False:
                            break
                """
                
                if states_are_the_same:
                    utils.msg("[i] Result is a stable state")
                    mapping_operation_hash_to_stable_state[operation_hash] = "stable"
                    # The "state_index" from the previous calculation can be used
                else:
                    utils.msg("[i] Result is an unstable state: >>>%s<<<" % operation)  # log it so that I can manually check if the states are really unstable
                    utils.msg("[i] Unstable operation_hash: %s" % operation_hash)
                    utils.msg("[i] Original operation: %s" % original_operation_code)
                    utils.msg("[i] Datatype: %s" % variable_type)
                    # utils.msg("[i] Previous state:\n%s" % previous_state)
                    # utils.msg("[i] Current state:\n%s" % state)

                    mapping_operation_hash_to_stable_state[operation_hash] = "unstable"

                    # The new state is different and must therefore be stored and used
                    variable_operations_states_list_global.append(state)
                    state_index = len(variable_operations_states_list_global) - 1
            
    utils.msg("[i] END of get_operation_and_state_indexes()\n\n")
    return operation_index, state_index


# TODO: Function must be called after hashing so that it's modified for all operations
def enhance_operation(operation_code, variable_type=None):
    # This function does the following
    # First it tries to rename all variable tokens which are not var_1_ and so on yet
    # This can occur because the operation was within a big testcase where variable renaming didn't work
    # Next it tries to just use variable ID's which are contiguous and which start at 1
    # e.g. it can occur that a variable operation is:
    # var_3_ = 123;
    # var_TARGET_.someOperation(var_3_)
    # => Then it tries to rename var_3_ to var_1_

    # Moreover, the script tries to assign results to variables
    # For example, an operation can be
    # var_TARGET_.someFunction() < 5
    # 
    # This operation occurs because operations are also extracted from if() or for() loop headers
    # In this case it makes sense to rewrite the operation to:
    # var var_1_ = var_TARGET_.someFunction() < 5

    # Then the state-creation() can detect that var_1_ is a boolean value and the fuzzer can use it in if- or for-headers

    prefix_code = ""
    if variable_type is not None:
        prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type)

    # This check is not really required, however, I just want to get sure that the
    # code is valid when I start to enhance it.
    # I think I have some not working operations in my database (?)
    # if cfg.exec_engine.execute_once(prefix_code + operation_code).status != Execution_Status.SUCCESS:
    #    utils.perror("Problem (executions doesn't success) with operation >>%s<< and prefix code >%s< for data type %s" % (operation_code, prefix_code, variable_type))

    # Rename not yet renamed variable tokens like v11, ...
    operation_code = rename_variables(operation_code, prefix_code)
    # Note: Currently I ignore functions and classes, when merging the operations into testcases (during fuzzing)
    # they are correctly handled, so it's not really required to handle them here

    # Ensure all tokens are contiguous
    new_content = testcase_helpers.ensure_all_variable_names_are_contiguous(operation_code)
    if new_content != operation_code:
        # if True:    # debugging code to skip executions
        if cfg.exec_engine.execute_once(prefix_code + new_content).status == Execution_Status.SUCCESS:
            operation_code = new_content   # Renaming was successful
    new_content = testcase_helpers.ensure_all_function_names_are_contiguous(operation_code)
    if new_content != operation_code:
        # if True:    # debugging code to skip executions
        if cfg.exec_engine.execute_once(prefix_code + new_content).status == Execution_Status.SUCCESS:
            operation_code = new_content   # Renaming was successful
    new_content = testcase_helpers.ensure_all_class_names_are_contiguous(operation_code)
    if new_content != operation_code:
        # if True:    # debugging code to skip executions
        if cfg.exec_engine.execute_once(prefix_code + new_content).status == Execution_Status.SUCCESS:
            operation_code = new_content   # Renaming was successful

    # Now try to assign results of code lines to newly created variables...
    last_used_variable_id = 0
    for idx in range(8000):
        token_name = "var_%d_" % idx
        if token_name in operation_code:
            last_used_variable_id = idx

    code_lines = operation_code.split("\n")
    number_of_lines = len(code_lines)
    for current_line_number in range(0, number_of_lines):
        current_line = code_lines[current_line_number]
        current_line_tmp = current_line.lstrip()

        # TODO: Rewrite to a list and a for loop..
        if current_line_tmp.startswith("var ") or           \
                current_line_tmp.startswith("let ") or      \
                current_line_tmp.startswith("const ") or    \
                current_line_tmp.startswith("function ") or \
                current_line_tmp.startswith("for ") or      \
                current_line_tmp.startswith("for(") or      \
                current_line_tmp.startswith("if ") or       \
                current_line_tmp.startswith("if(") or       \
                current_line_tmp.startswith("while ") or    \
                current_line_tmp.startswith("while(") or    \
                current_line_tmp.startswith("else ") or     \
                current_line_tmp.startswith("else{") or     \
                current_line_tmp.startswith("switch ") or   \
                current_line_tmp.startswith("switch(") or   \
                current_line_tmp.startswith("case ") or     \
                current_line_tmp.startswith("default:") or  \
                current_line_tmp.startswith("try ") or      \
                current_line_tmp.startswith("try(") or      \
                current_line_tmp.startswith("catch ") or    \
                current_line_tmp.startswith("catch(") or    \
                current_line_tmp.startswith("finally ") or  \
                current_line_tmp.startswith("finally{") or  \
                current_line_tmp.startswith("return "):
            # skip these codelines because a variable assignment doesn't make sense in these cases
            continue  
        
        if current_line_tmp.startswith("{"):
            if "catch" in current_line_tmp or "finally" in current_line_tmp or "else" in current_line_tmp:
                continue

        
        if current_line_tmp.startswith("var_TARGET_ =") and current_line_tmp.startswith("var_TARGET_ ==") is False:
            continue
        if current_line_tmp.startswith("var_TARGET_=") and current_line_tmp.startswith("var_TARGET_==") is False:
            continue
        
        splitted = current_line_tmp.split(" ")
        if len(splitted) > 2:
            if splitted[1] == "=":
                # code is something like "var_1_ = 123;"
                # => an assignment. In this case I don't want to assign it to a variable again
                # Note: This code doesn't work for all cases, e.g. "var_1_=123"
                # but it's enough for my use-cases
                continue

        tmp = ""
        # Add all code lines before tested line
        for idx in range(current_line_number):
            tmp += code_lines[idx] + "\n"

        # Add the tested code line including the assignment to a new variable...

        new_codeline = "var var_%s_ = " % (last_used_variable_id+1)
        new_codeline += current_line

        tmp += new_codeline + "\n"
        
        # And now add all the other code lines:
        for idx in range(current_line_number+1, number_of_lines):
            tmp += code_lines[idx] + "\n"

        # if True:    # debugging code to skip executions
        if cfg.exec_engine.execute_once(prefix_code + tmp).status == Execution_Status.SUCCESS:
            # If this point it reached the variable assignment was successful and can be performed
            code_lines[current_line_number] = new_codeline  # so change the code line in the resulting code
            last_used_variable_id += 1

    operation_code = "\n".join(code_lines)
    return operation_code


# TODO: I now have some code in javascript/js_renaming.py to rename variables? Merge it?
def rename_variables(content, prefix_code):
    variable_names_to_rename = list(js_helpers.get_variable_name_candidates(content))
    if len(variable_names_to_rename) == 0:
        return content  # Nothing to rename

    # Start renaming with the longest variable name.
    # This helps to prevent cases where a variable name is the substring of another variable name
    variable_names_to_rename.sort(reverse=True, key=len)

    # Get starting ID for the new variables
    last_used_variable_id = 0
    for idx in range(8000):
        token_name = "var_%d_" % idx
        if token_name in content:
            last_used_variable_id = idx

    # Now iterate through all variables and replace them
    variable_id = last_used_variable_id + 1
    for variable_name in variable_names_to_rename:
        if variable_name == "var_TARGET_":
            continue
        new_content = js_renaming.rename_variable_name_safe(content, variable_name, variable_id)
        if new_content != content:
            if cfg.exec_engine.execute_once(prefix_code + new_content).status == Execution_Status.SUCCESS:
                content = new_content
                variable_id += 1
    return content


def check_if_identified_operations_are_valid(all_generic_operations, all_variable_operations, all_variable_operations_others):
    global all_generic_operations_hashes
    global all_variable_operations_hashes
    global all_variable_operations_others_hashes

    # These are the variables which will be returned by the function
    all_variable_operations_working = dict()
    all_generic_operations_working = set()
    all_variable_operations_others_working = dict()
    all_variable_operations_exception = dict()
    all_generic_operations_exception = set()
    all_variable_operations_others_exception = dict()

    # First check the generic operations
    counter = 0
    for operation in all_generic_operations:
        counter += 1
        if counter % 1000 == 0:     # Short status update
            utils.msg("[i] Generic operations iteration: %d of %d" % (counter, len(all_generic_operations)))
            sys.stdout.flush()
        result = cfg.exec_engine.execute_once(operation)
        if result.status == Execution_Status.SUCCESS:
            all_generic_operations_working.add(operation)
        elif result.status == Execution_Status.CRASH:
            utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % operation)
            utils.store_testcase_with_crash(operation)
        else:
            # Variable name is not 100% correct, it's an exception or a timeout, but it doesn't matter
            all_generic_operations_exception.add(operation)

            # In some cases I can "fix" the operation and then add it, so let's try this:
            fixed_operation = try_to_fix_testcase(operation)
            if fixed_operation != operation:
                # something has changed, so also try if the fixed operation works without an exception:
                operation_hash = extract_helpers.get_hash_of_normalized_operation(fixed_operation)
                if operation_hash not in all_generic_operations_hashes:
                    # not seen before
                    all_generic_operations_hashes.add(operation_hash)
                    result = cfg.exec_engine.execute_once(fixed_operation)
                    if result.status == Execution_Status.SUCCESS:
                        all_generic_operations_working.add(fixed_operation)
                    elif result.status == Execution_Status.CRASH:
                        utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % fixed_operation)
                        utils.store_testcase_with_crash(fixed_operation)

    # Now check all the variable type operations:
    for variable_type in all_variable_operations:
        all_variable_operations_working[variable_type] = set()
        all_variable_operations_exception[variable_type] = set()

        # Get code to generate a variable of the data type >variable_type<
        prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type) + "\n"
        counter = 0
        for operation in all_variable_operations[variable_type]:
            counter += 1
            if counter % 1000 == 0:     # Short status update
                print("Variable %s operations iteration: %d of %d" % (variable_type, counter, len(all_variable_operations[variable_type])))
                sys.stdout.flush()
            code_to_test = prefix_code + operation

            result = cfg.exec_engine.execute_once(code_to_test)
            if result.status == Execution_Status.SUCCESS:
                all_variable_operations_working[variable_type].add(operation)
            elif result.status == Execution_Status.CRASH:
                utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % code_to_test)
                utils.store_testcase_with_crash(code_to_test)
            else:
                all_variable_operations_exception[variable_type].add(operation)

                fixed_operation = try_to_fix_testcase(operation)
                if fixed_operation != operation:
                    # something has changed, so also try if the fixed operation works without an exception:
                    operation_hash = extract_helpers.get_hash_of_normalized_operation(fixed_operation)
                    if operation_hash not in all_variable_operations_hashes[variable_type]:
                        # not seen before
                        all_variable_operations_hashes[variable_type].add(operation_hash)
                        result = cfg.exec_engine.execute_once(prefix_code+fixed_operation)
                        if result.status == Execution_Status.SUCCESS:
                            all_variable_operations_working[variable_type].add(fixed_operation)
                        elif result.status == Execution_Status.CRASH:
                            crashing_code = prefix_code+fixed_operation
                            utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % crashing_code)
                            utils.store_testcase_with_crash(crashing_code)

    # TODO: Remove the boilerplate code (all 3 steps (generic, variable operations and other variable operations) are very similar)!
    # Now same for the "other" operations for the variable types
    for variable_type in all_variable_operations_others:
        all_variable_operations_others_working[variable_type] = set()
        all_variable_operations_others_exception[variable_type] = set()

        # Get code to generate a variable of the data type >variable_type<
        prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type) + "\n"
        counter = 0
        for operation in all_variable_operations_others[variable_type]:
            counter += 1
            if counter % 1000 == 0:     # Short status update
                print("Variable %s other operations iteration: %d of %d" % (variable_type, counter, len(all_variable_operations_others[variable_type])))
                sys.stdout.flush()

            code_to_test = prefix_code + operation

            result = cfg.exec_engine.execute_once(code_to_test)
            if result.status == Execution_Status.SUCCESS:
                all_variable_operations_others_working[variable_type].add(operation)
            elif result.status == Execution_Status.CRASH:
                utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % code_to_test)
                utils.store_testcase_with_crash(code_to_test)
            else:
                all_variable_operations_others_exception[variable_type].add(operation)

                fixed_operation = try_to_fix_testcase(operation)
                if fixed_operation != operation:
                    # something has changed, so also try if the fixed operation works without an exception:
                    operation_hash = extract_helpers.get_hash_of_normalized_operation(fixed_operation)
                    if operation_hash not in all_variable_operations_others_hashes[variable_type]:
                        # not seen before
                        all_variable_operations_others_hashes[variable_type].add(operation_hash)
                        result = cfg.exec_engine.execute_once(prefix_code+fixed_operation)
                        if result.status == Execution_Status.SUCCESS:
                            all_variable_operations_others_working[variable_type].add(fixed_operation)
                        elif result.status == Execution_Status.CRASH:
                            crashing_code = prefix_code+fixed_operation
                            utils.msg("[i] FOUND A CRASH WHILE EXTRACTING OPERATIONS:\n%s" % crashing_code)
                            utils.store_testcase_with_crash(crashing_code)

    return (all_generic_operations_working,
            all_variable_operations_working,
            all_variable_operations_others_working,
            all_generic_operations_exception,
            all_variable_operations_exception,
            all_variable_operations_others_exception)


def enhance_and_calculate_states_for_generic_operations(all_generic_operations_working):
    all_generic_operations_with_state = []

    # Generic operations:
    number_operations = len(all_generic_operations_working)
    current_operation = 0
    for operation_code in all_generic_operations_working:
        current_operation += 1
        utils.msg("[i] Starting state creation for generic operation %d of %d" % (current_operation, number_operations))
        operation_enhanced = enhance_operation(operation_code)
        operation_state = create_state_file.create_state_file_safe(operation_enhanced)
        all_generic_operations_with_state.append((operation_enhanced, operation_state))

    return all_generic_operations_with_state


def enhance_and_calculate_states_for_variable_operations(all_variable_operations_working, all_variable_operations_others_working):
    global variable_operations_states_list_global
    global variable_operations_list_global

    all_variable_operations_with_state = dict()
    all_variable_operations_others_with_state = dict()

    # Handle "variable operations":
    number_operations = 0
    # Calculate how many executions are required (to display a progress message):
    for variable_type in all_variable_operations_working:
        number_operations += len(all_variable_operations_working[variable_type])
    # Now start to handle all operations:
    current_operation = 0
    for variable_type in all_variable_operations_working:
        all_variable_operations_with_state[variable_type] = []
        for operation in all_variable_operations_working[variable_type]:
            current_operation += 1
            utils.msg("[i] State creation for data types operation (%s) %d of %d" % (variable_type, current_operation, number_operations))
            utils.msg("[i] Length of operations: %d ; length of states: %d" % (len(variable_operations_list_global), len(variable_operations_states_list_global)))
            (operation_index, state_index) = get_operation_and_state_indexes(operation, variable_type)
            if operation_index is None:
                continue
            all_variable_operations_with_state[variable_type].append((operation_index, state_index))  # store here just a mapping of the indexes

    # Handle "other variable operations":
    number_operations = 0
    # Calculate how many executions are required (to display a progress message):
    for variable_type in all_variable_operations_others_working:
        number_operations += len(all_variable_operations_others_working[variable_type])
    # Now start to handle all operations:
    current_operation = 0
    for variable_type in all_variable_operations_others_working:
        all_variable_operations_others_with_state[variable_type] = []
        for operation in all_variable_operations_others_working[variable_type]:
            current_operation += 1
            utils.msg("[i] State creation for data types other operation (%s) %d of %d" % (variable_type, current_operation, number_operations))
            utils.msg("[i] Length of operations: %d ; length of states: %d" % (len(variable_operations_list_global), len(variable_operations_states_list_global)))
            (operation_index, state_index) = get_operation_and_state_indexes(operation, variable_type)
            if operation_index is None:
                continue
            all_variable_operations_others_with_state[variable_type].append((operation_index, state_index))  # store here just a mapping of the indexes

    return (all_variable_operations_with_state,
            all_variable_operations_others_with_state,
            variable_operations_states_list_global,
            variable_operations_list_global)


def fix_generic_operations(all_generic_operations_with_state):
    all_generic_operations_with_state_fixed = []

    for entry in all_generic_operations_with_state:
        (operation, state) = entry
        lines_of_code = len(operation.split("\n"))

        if 0 in state.lines_where_inserted_code_leads_to_exception or lines_of_code in state.lines_where_inserted_code_leads_to_exception:
            # Can't add something in front of the operation
            # or can't add something after operation
            # This typically results from an operation such as "#!"
            print("Skipping operation: %s" % operation)
            continue
        all_generic_operations_with_state_fixed.append(entry)

    return all_generic_operations_with_state_fixed


def fix_variable_operations(all_variable_operations_with_state, all_variable_operations_others_with_state, variable_operations_states_list, variable_operations_list):
    # And now fix some other wrong operations (TODO move this code before I create state files!
    # At the moment I have it here because I already created states; but before I create them again
    # move it upwards)
    global test_cache

    utils.msg("[i] Going to fix variable operations")

    current_length = 0
    for variable_type in all_variable_operations_with_state:
        current_length += len(all_variable_operations_with_state[variable_type])
    utils.msg("[i] Start length all_variable_operations_with_state: %d" % current_length)

    current_length = 0
    for variable_type in all_variable_operations_others_with_state:
        current_length += len(all_variable_operations_others_with_state[variable_type])
    utils.msg("[i] Start length all_variable_operations_others_with_state: %d" % current_length)

    new_dict = dict()
    for variable_type in all_variable_operations_with_state:
        new_dict[variable_type] = []
        utils.msg("[i] Going to handle data type: %s" % variable_type)
        for entry in all_variable_operations_with_state[variable_type]:
            (operation_index, state_index) = entry
            operation = variable_operations_list[operation_index]
            state = variable_operations_states_list[state_index]
            if check_if_operation_is_allowed(operation, state, variable_type):
                new_dict[variable_type].append(entry)
            else:
                # In this case just remove the entry in >all_variable_operations_with_state<
                # but don't remove the operation or state (otherwise the indexes would no longer match)
                # or another operation could point to the same indexes
                pass
    all_variable_operations_with_state = new_dict

    new_dict = dict()
    for variable_type in all_variable_operations_others_with_state:
        new_dict[variable_type] = []
        utils.msg("[i] Going to handle data type (others): %s" % variable_type)
        for entry in all_variable_operations_others_with_state[variable_type]:
            (operation_index, state_index) = entry
            operation = variable_operations_list[operation_index]
            state = variable_operations_states_list[state_index]
            if check_if_operation_is_allowed(operation, state, variable_type):
                new_dict[variable_type].append(entry)
            else:
                # In this case just remove the entry in >all_variable_operations_others_with_state<
                # but don't remove the operation or state (otherwise the indexes would no longer match)
                # or another operation could point to the same indexes
                pass
    all_variable_operations_others_with_state = new_dict

    current_length = 0
    for variable_type in all_variable_operations_with_state:
        current_length += len(all_variable_operations_with_state[variable_type])
    utils.msg("[i] Length afterwards all_variable_operations_with_state: %d" % current_length)

    current_length = 0
    for variable_type in all_variable_operations_others_with_state:
        current_length += len(all_variable_operations_others_with_state[variable_type])
    utils.msg("[i] Length afterwards all_variable_operations_others_with_state: %d" % current_length)

    utils.msg("[i] test_cache length: %d" % len(test_cache.keys()))

    variable_operations_states_list_is_in_use = [False] * len(variable_operations_states_list)
    variable_operations_list_is_in_use = [False] * len(variable_operations_list)

    # Mark everything which is in use
    for variable_type in all_variable_operations_with_state:
        for entry in all_variable_operations_with_state[variable_type]:
            (operation_index, state_index) = entry
            variable_operations_states_list_is_in_use[state_index] = True
            variable_operations_list_is_in_use[operation_index] = True

    for variable_type in all_variable_operations_others_with_state:
        for entry in all_variable_operations_others_with_state[variable_type]:
            (operation_index, state_index) = entry
            variable_operations_states_list_is_in_use[state_index] = True
            variable_operations_list_is_in_use[operation_index] = True

    # Now remove everything which is not in use
    # Fix the states
    for i in range(0, len(variable_operations_states_list)):
        is_in_use = variable_operations_states_list_is_in_use[i]
        if is_in_use is False:
            variable_operations_states_list[i] = None

    # Fix the operations:
    for i in range(0, len(variable_operations_list)):
        is_in_use = variable_operations_list_is_in_use[i]
        if is_in_use is False:
            variable_operations_list[i] = None

    return all_variable_operations_with_state, all_variable_operations_others_with_state, variable_operations_states_list, variable_operations_list


def check_if_operation_is_allowed(operation, state, variable_type):
    global test_cache

    # TODO: creating the hash myself is not required here because python itself would
    # create a hash for the dict lookup
    # Moreover, I should implement the caching as a decorator for the function
    # but the code will later be rewritten anyway (because it must be executed before I calculate states)
    # so I'm therefore not changing it yet
    operation_hash = utils.calc_hash(operation)
    if operation_hash in test_cache and variable_type != "boolean" and variable_type != "real_number" and variable_type != "special_number":
        return test_cache[operation_hash]

    # Check1:
    # Remove operations such as:
    # const var_1_ = Array();
    # var var_2_ = var_1_,var_TARGET_,Array;

    # or:
    # var var_8_ = Object,Object,func_1_,var_TARGET_;
    # => and because of "func_1_" a lot of shit is stored in the operation...

    # var var_6_ = var_4_, var_TARGET_
    # =>
    # var var_6_ = var_4_, var_1_.toString

    # Properties are also not working in this context.
    # I should try to search if the operation contains "var_TARGET_" in a line which starts with "var ", "let " or "const "
    # and which contains "," without containing "("
    # The "(" would indicate that a function call is used where the "," would be allowed

    for line in operation.split("\n"):
        line_without_space = line.replace(" ", "")
        if ",var_TARGET_" in line_without_space or "var_TARGET_,":
            if line.startswith("var ") or line.startswith("let ") or line.startswith("const "):
                if "(" not in line:  # with "(" it could be a function invocation and var_TARGET_ could be a parameter passed to the function
                    test_cache[operation_hash] = False
                    return False

    # Check2:
    # Check if operation contains something like:
    # function func_1_(var_21_, var_TARGET_) {

    # During Fuzzing:
    # function func_3_(var_26_, var_3_[4]) {

    # => "var_3_[4]" is not allowed in this context.
    # => filter out operations where "function " and "var_TARGET_" are in the same line

    # Another example during fuzzing:
    # var var_10_ = async function func_2_(var_7_,var_8_,var_2_[1],var_9_,var_6_) {
    # =>
    # var_2_[1] is not allowed there
    #
    # In a later state it maybe makes sense to save such operations and store these operations
    # separately in a list with operations which can't be applied to properties/array items
    # => but I also think that these operations don't make a lot of sense..
    for line in operation.split("\n"):
        line_without_space = line.replace(" ", "")
        if ",var_TARGET_" in line_without_space or "var_TARGET_,":
            if "function " in line:
                test_cache[operation_hash] = False
                return False

    # Check3:
    # Check if code can be try-catch / try-finally wrapped

    # For example:
    # function func_1_() {
    # }
    # var var_8_ = Object,func_1_;
    # => no exception

    # However, when the operation is added inside a try-catch block during fuzzing:
    # try {
    #   function func_1_() {
    #   }
    #   var var_8_ = Object,func_1_;
    # } catch(var_1111_) { }
    # => exception

    # To avoid these exceptions during fuzzing I check here if the operation also works
    # without a try-catch block

    # If this point is reached it's a valid operation

    # Currently I'm using a static approach to detect it because I no longer have such operations
    # (check1 & check2 already handled these cases)
    for line in operation.split("\n"):
        line_without_space = line.replace(" ", "")
        if ",func_" in line_without_space:
            if line.startswith("var ") or line.startswith("let ") or line.startswith("const "):
                if "(" not in line:
                    test_cache[operation_hash] = False
                    return False

    # This would be the old (slow) dynamic approach
    # prefix_code = get_code_to_instantiate_obj(variable_type)
    # code_to_test = prefix_code + operation
    # code_to_test = "try {\n" + code_to_test + "\n} catch(someCatchVariableName) { }"
    # if cfg.exec_engine.execute_once(code_to_test).status != Execution_Status.SUCCESS:
    #    print("Incorrect operation2:")
    #    print(operation)
    #    print("\n")
    #    test_cache[operation_hash] = False
    #    False

    # Check 4
    # filter out operations which work with "var var_TARGET_" but which don't work with "let var_TARGET_".
    # e.g.:

    # var var_TARGET_ = 1;
    # for (var var_1_ = 6; var_1_ <= 48; var_1_ *= 2) {
    # var var_2_ = var_1_,var_TARGET_
    # };
    # => no exception (during operation creation)

    # let var_TARGET_ = 1;
    # for (var var_1_ = 6; var_1_ <= 48; var_1_ *= 2) {
    # var var_2_ = var_1_,var_TARGET_
    # };
    # => exception (during fuzzing)

    prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type)
    prefix_code = prefix_code.replace("var ", "let ")
    code_to_test = prefix_code + operation

    if cfg.exec_engine.execute_once(code_to_test).status != Execution_Status.SUCCESS:
        test_cache[operation_hash] = False
        return False

    # Check 5

    # E.g.:
    # for (var var_7_ = var_5_; var_7_ <= var_TARGET_; var_7_++) {
    # *incorrect code*
    # }

    # During current state creation I create var_TARGET_ e.g. as value 0.
    # Then the for loop would not be executed and therefore the incorrect code doesn't get executes.
    # However, during real fuzzer var_TARGET_ can be different and it can therefore always leads to an exception
    # in case the for-body gets executes...

    # same applies for boolean true/false values:

    if variable_type == "boolean":
        prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type)
        prefix_code = prefix_code.replace("new Boolean;", "new Boolean(true);")
        code_to_test = prefix_code + operation
        if cfg.exec_engine.execute_once(code_to_test).status != Execution_Status.SUCCESS:
            test_cache[operation_hash] = False
            return False

    if variable_type == "special_number" or variable_type == "real_number":
        # It was already tested with the number 0, so test it now with 1337 & 1338
        # this are higher numbers and are even & odd
        # Note: previously I also tested for -9 to have a negative number
        # That filters out code which contains stuff like:
        # var_1_[var_TARGET_]
        # or
        # var_1_.length = var_TARGET_;
        #
        # => However, I want such operations (and I just have ~10-20 such operations)
        # so I keep them and don't use -9 as test
        replacement_list = ["1337", "1338"]
        for replacement in replacement_list:
            prefix_code = extract_helpers.get_code_to_instantiate_obj(variable_type)
            prefix_code = prefix_code.replace("new Number;", "new Number(%s);" % replacement)
            code_to_test = prefix_code + operation
            if cfg.exec_engine.execute_once(code_to_test).status != Execution_Status.SUCCESS:
                test_cache[operation_hash] = False
                return False

    test_cache[operation_hash] = True
    return True


# Function is just used to print some statistics to get an overview over the extracted operations
# during the execution of the script
def print_extracted_operations(arg_msg, all_generic_operations, all_variable_operations, all_variable_operations_others):
    utils.msg("[i]\n")
    utils.msg("[i] -------------------------------------------------")
    utils.msg("[i] %s" % arg_msg)
    utils.msg("[i]\n")
    utils.msg("[i] Generic operations: %d operations" % len(all_generic_operations))
    utils.msg("[i]\n")
    utils.msg("[i] Variable operations:")
    for variable_type_entry in all_variable_operations:
        utils.msg("[i] Datatype %s has %d operations" % (variable_type_entry, len(all_variable_operations[variable_type_entry])))

    if all_variable_operations_others is not None:
        utils.msg("[i]\n")
        utils.msg("[i] Other variable operations:")
        for variable_type_entry in all_variable_operations_others:
            utils.msg("[i] Datatype %s has %d operations" % (variable_type_entry, len(all_variable_operations_others[variable_type_entry])))
    utils.msg("[i]\n")
    sys.stdout.flush()
