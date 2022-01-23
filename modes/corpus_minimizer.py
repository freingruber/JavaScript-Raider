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


# This mode can be started by passing the "--minimize_corpus_mode" flag to the fuzzer.
#
# This mode tries to reduce the size of the JavaScript Corpus.
# It first tries to minimize the number of testcases in the Corpus
# and then tries to further minimize testcases.
# Testcases should already get minimized when they are added to the corpus,
# however, this sometimes fails. It therefore makes sense to start this code
# from time to time to further reduce the corpus size.


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import pickle
from shutil import copyfile
import utils
import standardizer.testcase_standardizer as testcase_standardizer
import minimizer.testcase_minimizer as testcase_minimizer
import state_creation.create_state_file as create_state_file
import native_code.coverage_helpers as coverage_helpers
import config as cfg
import testcase_state

results = dict()


def minimize_corpus():
    calculate_coverage_per_testcase(cfg.output_dir_current_corpus)
    new_folder = os.path.join(cfg.output_dir, cfg.current_corpus_minimized_dir)
    utils.make_dir_if_not_exists(new_folder)
    calculate_minset_of_corpus(cfg.output_dir_current_corpus, new_folder)
    rename_and_minimize_all_testcases(new_folder)


def add_result(idx, current_id):
    global results
    if idx not in results:
        results[idx] = []
    results[idx].append(current_id)


def handle_file_and_extract_coverage(content, filepath, filename):
    coverage = coverage_helpers.extract_coverage_of_testcase(content, cfg.coverage_map_corpus_minimizer)

    # Now check if all of this new coverage can reliable be triggered
    triggered_coverage = coverage_helpers.extract_coverage_of_testcase(content, cfg.coverage_map_corpus_minimizer)
    problem_entries = []
    for coverage_entry in coverage:
        if coverage_entry not in triggered_coverage:
            problem_entries.append(coverage_entry)

    for coverage_entry in problem_entries:
        coverage.remove(coverage_entry)

    utils.msg("[i] File %s has %d triggered edges" % (filename, len(coverage)))
    with open(filepath[:-3] + "_coverage.pickle", 'wb') as fout:
        pickle.dump(coverage, fout, pickle.HIGHEST_PROTOCOL)


def calculate_coverage_per_testcase(output_dir_current_corpus):
    last_testcase_id = utils.get_last_testcase_number(output_dir_current_corpus)
    utils.msg("[i] Last testcase ID: %d" % last_testcase_id)

    for current_id in range(1, last_testcase_id+1):
        filename = "tc%d.js" % current_id
        filepath = os.path.join(output_dir_current_corpus, filename)
        if os.path.isfile(filepath) is False:
            continue        
        with open(filepath, 'r') as fobj:
            content = fobj.read().rstrip()

        handle_file_and_extract_coverage(content, filepath, filename)


def calculate_minset_of_corpus(base_path, base_path_out):
    testcases_must_trigger = dict()
    filesizes = []

    last_testcase_id = utils.get_last_testcase_number(base_path)
    utils.msg("[i] Last testcase ID: %d" % last_testcase_id)

    utils.msg("[i] Going to read file sizes...")
    for current_id in range(1, last_testcase_id+1):
        filename = "tc%d.js" % current_id
        utils.msg("[i] Getting file size of: %s" % filename)
        filepath = os.path.join(base_path, filename)
        if os.path.isfile(filepath) is False:
            continue        
        with open(filepath, 'r') as fobj:
            content = fobj.read().rstrip()
        filesizes.append((current_id, len(content)))
    utils.msg("[i] Finished reading file sizes")

    # sort list based on file sizes
    filesizes.sort(key=lambda x: x[1])

    # Now iterate through the coverage by starting with the smallest files
    # => This ensures that always the smallest file is taken which triggers a coverage
    for entry in filesizes:
        (current_id, content_length) = entry
        filename = "tc%d.js_coverage.pickle" % current_id
        filepath = os.path.join(base_path, filename)
        print("Going to load %s" % filename)
        with open(filepath, 'rb') as finput:
            tmp_coverage = pickle.load(finput)
        for coverage_entry in tmp_coverage:
            add_result(coverage_entry, current_id)

    # Now take for every coverage the smallest file
    files_to_take = set()
    for coverage_index in results:
        first_entry = results[coverage_index][0]    # first entry is always the smallest file
        filename = "tc%d.js" % first_entry

        if filename not in testcases_must_trigger:
            testcases_must_trigger[filename] = []

        testcases_must_trigger[filename].append(coverage_index)
        files_to_take.add(filename)
    

    # Now print the result
    for filename in files_to_take:
        # print("Taking: %s" % filename)
        input_filepath = os.path.join(base_path, filename)
        output_filepath = os.path.join(base_path_out, filename)
        copyfile(input_filepath, output_filepath)
        copyfile(input_filepath + ".pickle", output_filepath + ".pickle")

        output_filepath_required_coverage = output_filepath[:-3] + "_required_coverage.pickle"
        with open(output_filepath_required_coverage, 'wb') as fout:
            pickle.dump(testcases_must_trigger[filename], fout, pickle.HIGHEST_PROTOCOL)


def rename_and_minimize_testcase(filepath):
    with open(filepath, 'r') as fobj:
        content = fobj.read().rstrip()

    required_coverage_filepath = filepath[:-3] + "_required_coverage.pickle"
    with open(required_coverage_filepath, 'rb') as finput:
        required_coverage = pickle.load(finput)

    if len(required_coverage) == 0:
        utils.perror("Logic flaw1")
    
    original_content = content

    content = testcase_standardizer.standardize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)
    content = testcase_minimizer.minimize_testcase(content, required_coverage, cfg.coverage_map_corpus_minimizer)

    if content != original_content:
        utils.msg("[i] Applied modifications on file: %s" % filepath)

        # Recalculate the state of the modified file
        state = create_state_file.create_state_file_safe(content)
        if cfg.adjustment_factor_code_snippet_corpus is not None:
            state.runtime_length_in_ms = int(float(state.runtime_length_in_ms) / cfg.adjustment_factor_code_snippet_corpus)

        output_state_filepath = filepath + ".pickle"
        testcase_state.save_state(state, output_state_filepath)

        # Save the minimized / renamed file
        with open(filepath, "w") as fobj:
            fobj.write(content)
    

def rename_and_minimize_all_testcases(base_path):
    last_testcase_id = utils.get_last_testcase_number(base_path)
    utils.msg("[i] Last testcase ID: %d" % last_testcase_id)

    utils.msg("[i] Going to rename and minimize all files...")
    for current_id in range(1, last_testcase_id+1):
        filename = "tc%d.js" % current_id
        filepath = os.path.join(base_path, filename)
        if os.path.isfile(filepath) is False:
            continue
        utils.msg("[i] Going to rename and minimize file: %s" % filename)
        rename_and_minimize_testcase(filepath)
