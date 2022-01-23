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



# Note: This script is not production ready
# I often rewrote it during development to find/fix specific testcases

# TODO: Refactor code

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import testcase_state
import utils
import config as cfg
import standardizer.testcase_standardizer as testcase_standardizer
import minimizer.testcase_minimizer as testcase_minimizer
import state_creation.create_state_file as create_state_file
import re
import hashlib
from shutil import copyfile
import native_code.coverage_helpers as coverage_helpers
import pickle



correct_variable_types = ["string", "array", "int8array", "uint8array", "uint8clampedarray", "int16array", "uint16array", "int32array", "uint32array", "float32array", "float64array", "bigint64array", "biguint64array", "set", "weakset", "map", "weakmap", "regexp", "arraybuffer", "sharedarraybuffer", "dataview", "promise", "intl.collator", "intl.datetimeformat", "intl.listformat", "intl.numberformat", "intl.pluralrules", "intl.relativetimeformat", "intl.locale", "webassembly.module", "webassembly.instance", "webassembly.memory", "webassembly.table", "webassembly.compileerror", "webassembly.linkerror", "webassembly.runtimeerror", "urierror", "typeerror", "syntaxerror", "rangeerror", "evalerror", "referenceerror", "error", "date", "null", "math", "json", "reflect", "globalThis", "atomics", "intl", "webassembly", "object1", "object2", "unkown_object", "real_number", "special_number", "function", "boolean", "symbol", "undefined", "bigint"]


def find_problematic_corpus_files():
    utils.msg("[i] Starting to find problematic testcases...")

    corpus_filepath = cfg.output_dir_current_corpus

    counter = 0
    for filename in os.listdir(corpus_filepath):
        if filename.endswith(".js") is False:
            continue

        filepath = os.path.join(corpus_filepath, filename)
        if os.path.isfile(filepath) is False:
            continue

        counter += 1
        # print("Next file (counter: %d): %s" % (counter, filename))
        with open(filepath, "r") as fobj:
            content = fobj.read()

        state_filepath = filepath + ".pickle"
        state = testcase_state.load_state(state_filepath)

        problem_found = False
        for variable_name in state.variable_types:
            for entry in state.variable_types[variable_name]:
                (entry_line_number, variable_type) = entry
                if variable_type not in correct_variable_types:
                    print("Problematic entry: %s has for variable %s data type: %s" % (filename, variable_name, variable_type))
                    problem_found = True
                    break
            if problem_found:
                break

        # TODO Check if variable name has strange entries

    # print("STOP")
    # sys.exit(-1)

    """
    print("Going to sort files based on file size")

    mapping_hash_to_content_length = dict()
    mapping_hash_to_filename = dict()

    corpus_path = "/home/user/fuzzer/OUTPUT/current_corpus/"
    fixed_corpus_path = "/home/user/fuzzer/OUTPUT/current_corpus_fixed/"
    for filename in os.listdir(corpus_path):
        if filename.endswith(".pickle"):
            continue
        if filename.endswith(".js") == False:
            continue
        print("Handling file: %s" % filename)
        filepath = os.path.join(corpus_path, filename)
        if os.path.isfile(filepath) == False:
            continue

        with open(filepath, 'r') as fobj:
            content = fobj.read().rstrip()

        m = hashlib.md5()
        m.update(content.encode("utf-8"))
        sample_hash = str(m.hexdigest())
        sample_length = len(content)           
        if sample_hash in mapping_hash_to_content_length:
            print("PROBLEM, found two similar files !")
            print("current file: %s" % filename)
            print("Previous one: %s" % mapping_hash_to_filename[sample_hash])

            if int(filename[2:-3],10) < int(mapping_hash_to_filename[sample_hash][2:-3],10):
                # the current file has a smaller testcase ID which means it's most likely the correct required coverage
                # so overwrite the filename to take the current one
                mapping_hash_to_content_length[sample_hash] = sample_length
                mapping_hash_to_filename[sample_hash] = filename
            continue
        mapping_hash_to_content_length[sample_hash] = sample_length
        mapping_hash_to_filename[sample_hash] = filename


    print("Starting to sort the list...")
    list_sorted_per_size = sorted(mapping_hash_to_content_length.items(), key=lambda x: x[1])
    print("Finished sorting the list.")

    total_number_files = len(list_sorted_per_size)
    current_file = 0

    for entry in list_sorted_per_size:
        (file_hash, file_size) = entry

        current_file += 1
        print("Handling file: %d of %d" % (current_file, total_number_files))
        filename = mapping_hash_to_filename[file_hash]

        input_fullpath = os.path.join(corpus_path, filename)
        output_fullpath = os.path.join(fixed_corpus_path, "tc%d.js" % current_file)

        copyfile(input_fullpath, output_fullpath)
        copyfile(input_fullpath+ ".pickle", output_fullpath+ ".pickle")
        copyfile(input_fullpath[:-3] + "_required_coverage.pickle", output_fullpath[:-3] + "_required_coverage.pickle")

    return
    """

    files_which_must_be_fixed = []

    # Fix testcases
    """
    files_which_must_be_fixed = ["tc12451.js",]
    for filename in files_which_must_be_fixed:
        print("Need to fix file: %s" % filename)

        # Reload the original content:
        path_original = "/home/user/fuzzer/OUTPUT/current_corpus_before_min/current_corpus_minimized/"
        path_target = "/home/user/fuzzer/OUTPUT/current_corpus/"
        filepath = os.path.join(path_original, filename)
        with open(filepath, "r") as fobj:
            content = fobj.read()

        required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"
        with open(required_coverage_filepath, 'rb') as finput:
            required_coverage = pickle.load(finput)

        sys.exit(-1)

        print("Original content:")
        print(content)
        content = testcase_standardizer.standardize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)

        print("Renamed:")
        print(content)

        content = testcase_minimizer.minimize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)

        print("Minimized:")
        print(content)

        # Recalculate the state of the modified file
        state = create_state_file.create_state_file_safe(content)
        if cfg.adjustment_factor_code_snippet_corpus != None:
            state.runtime_length_in_ms = int(float(state.runtime_length_in_ms) / cfg.adjustment_factor_code_snippet_corpus)

        filepath = os.path.join(path_target, filename)   # set the output path
        output_state_filepath = filepath + ".pickle"
        save_state(state, output_state_filepath)

        # Save the minimized / renamed file
        with open(filepath, "w") as fobj:
            fobj.write(content)
    sys.exit(-1)
    """

    counter = 0
    for filename in os.listdir(corpus_filepath):
        if filename.endswith(".js") is False:
            continue

        filepath = os.path.join(corpus_filepath, filename)
        if os.path.isfile(filepath) is False:
            continue

        counter += 1
        # print("Next file (counter: %d): %s" % (counter, filename))
        with open(filepath, "r") as fobj:
            content = fobj.read()

        state_filepath = filepath + ".pickle"
        state = testcase_state.load_state(state_filepath)

        required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"
        with open(required_coverage_filepath, 'rb') as finput:
            required_coverage = pickle.load(finput)

        # original_required_coverage_length = len(required_coverage)
        # required_coverage = get_required_coverage_without_problematic_entries(content, required_coverage)
        # required_coverage = get_required_coverage_without_problematic_entries(content, required_coverage)
        # print("Testcase: %s initial: %d and now: %d" % (filename, original_required_coverage_length, len(required_coverage)))

        # if original_required_coverage_length == len(required_coverage):
        #     continue
        # if len(required_coverage) == 0:
        #     files_which_must_be_fixed.append(filename)
        #     continue

        print("Going to fix testcase (counter: %d): %s" % (counter, filename))
        original_content = content
        content = testcase_standardizer.standardize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)
        if original_content.rstrip().rstrip(";").rstrip() == content.rstrip().rstrip(";").rstrip():
            continue  # variable renaming didn't change anything - so nothing to do here!

        content = testcase_minimizer.minimize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)
        if len(content) == 0:
            continue  # safety check, should never occur

        with open(required_coverage_filepath, 'wb') as fout:
            pickle.dump(required_coverage, fout, pickle.HIGHEST_PROTOCOL)

        if original_content.rstrip().rstrip(";").rstrip() != content.rstrip().rstrip(";").rstrip():
            # Recalculate the state of the modified file
            state = create_state_file.create_state_file_safe(content)
            testcase_state.save_state(state, state_filepath)

            # Save the minimized / renamed file
            with open(filepath, "w") as fobj:
                fobj.write(content)

        """
        # Check if the testcase contains unicode characters...
        problem_found = False
        for c in content:
            if ord(c) > 128:
                # Unicode is a problem because I had a bug in my state creation code
                # => so maybe the state of these files is incorrect and I want to recalculate the state
                # with the fixed code
                utils.msg("[-] Problematic testcase %s: Contains unicode!" % (filename))
                files_which_must_be_fixed.append(filename)
                problem_found = True
                break
        if problem_found == True:
            continue
        """

        """
        if len(state.lines_where_code_can_be_inserted) == 0 and len(state.lines_where_code_with_coma_can_be_inserted) == 0:
            # This typically occurs when the testcase contains special unicode characters
            # These unicode characters screw up my create_state() logic
            utils.msg("[-] Problematic testcase %s: No lines to insert code" % (filename))
            continue
        """

        # Now checks can be performed to identify problematic testcases

        # Check the runtime of the testcase
        """
        MAX_RUNTIME_FOR_TESTCASES = 580
        if state.runtime_length_in_ms > MAX_RUNTIME_FOR_TESTCASES:
            utils.msg("[-] Problematic testcase %s: runtime too long %d ms" % (filename, state.runtime_length_in_ms))

            required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"
            with open(required_coverage_filepath, 'rb') as finput:
                required_coverage = pickle.load(finput)

            print("Before required coverage:")
            print(required_coverage)
            if does_code_still_trigger_coverage(content, required_coverage) == True:
                print("still triggers coverage")
                result = cfg.exec_engine.execute_once(content)
                print(result)   # display runtime

                # Save result
                state = create_state_file.create_state_file_safe(content)
                output_state_filepath = filepath + ".pickle"
                save_state(state, output_state_filepath)
            else:
                print("NOT triggering coverage anymore")
                cfg.exec_engine.restart_engine()
                required_coverage = get_required_coverage_without_problematic_entries(content, required_coverage)
                print("New required coverage:")
                print(required_coverage)

                #with open(required_coverage_filepath, 'wb') as fout:
                #    pickle.dump(required_coverage, fout, pickle.HIGHEST_PROTOCOL)

            sys.exit(-1)

            continue

        if "new Worker" in content:
            # Workers spawn a 2nd v8 process which I currently don't terminate
            # => after some time it would "fork-bomb" a system during fuzzing
            utils.msg("[-] Problematic testcase %s: Contains 'new Worker' code" % (filename))
            continue
        """
        """

        if "throw " in content or "throw(" in content or "throw\t" in content:
            # testcase can throw an exception => check if it also catches the exception
            # Reason: I had some testcases which just throw an exception in case an if-condition becomes true or false
            # Per default the throw-code was not executed, however, in fuzzing (e.g. when replacing numbers)
            # it triggered very often the throw code => the testcase nearly always results in an exception
            # => I therefore try to manually fix these testcases and to identify them I use this script
            if "try" not in content:
                utils.msg("[-] Problematic testcase %s: Contains throw-code but not try-catch" % (filename))
                continue


        """

        """
        # For testcases where a "_" variable, function or class was renamed!
        # This incorrectly took something like "func_1_" and replaced the "_" in it
        # Examples of invalid strings in the testcase:
        # func_1func_1_
        # var_3func_1_
        # var_2func_1_
        # var_3var_1_
        words = ["func_%d", "var_%d", "cl_%d"]
        problem_found = False
        for word1 in words:
            for word2 in words:
                for number1 in range(1,10):
                    for number2 in range(1,10):
                        token = (word1 % number1) + (word2 % number2)
                        if token in content:
                            utils.msg("[-] Problematic testcase %s: Flaw in variable renaming, contains token: %s" % (filename, token))
                            files_which_must_be_fixed.append(filename)
                            problem_found = True
                            break
                    if problem_found == True:
                        break
                if problem_found == True:
                    break
            if problem_found == True:
                break
        if problem_found == True:
            continue



        words = ["func_%d", "var_%d", "cl_%d"]
        problem_found = False  
        for word in words:
            for number1 in range(1,400):
                token = (word % number1)
                all_positions = [m.start() for m in re.finditer(re.escape(token), content)]
                for pos in all_positions:
                    if pos == 0:
                        continue
                    char_before = content[pos-1]
                    if char_before.isalnum() == True or char_before == "_":
                        # problem, there is a testcase containing something like "Xvar_1_" whereas X is alphanumeric or _ => incorrect renaming!
                        utils.msg("[-] Problematic testcase %s: Flaw in variable renaming, position: %d char: %s" % (filename, pos-1, char_before))
                        problem_found = True
                        break
                if problem_found == True:
                    break
            if problem_found == True:
                break
    # TODO: Try to find var_ or func_ and cl_ and check if the symbol before it is a-zA-Z or _
    """

    # for filename in files_which_must_be_fixed:
    #     utils.msg("[i] Problem - 0 new coverage: %s" % filename)
    # for missing_variable in all_missing_variable_names:
    #     print(missing_variable)

    utils.msg("[i] Finished finding problematic testcases")


def does_code_still_trigger_coverage(new_code, required_coverage):
    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(new_code, cfg.coverage_map_corpus_minimizer)
    # utils.msg("[i] does_code_still_trigger_coverage(): Triggered %d edges" % len(triggered_coverage))
    for coverage_entry in required_coverage:
        if coverage_entry not in triggered_coverage:
            return False
    return True


def get_required_coverage_without_problematic_entries(new_code, required_coverage):
    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(new_code, cfg.coverage_map_corpus_minimizer)

    problem_entries = []
    for coverage_entry in required_coverage:
        if coverage_entry not in triggered_coverage:
            # utils.msg("[-] Problem finding coverage %d again in file" % coverage_entry)
            problem_entries.append(coverage_entry)

    for coverage_entry in problem_entries:
        required_coverage.remove(coverage_entry)
    return required_coverage
