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



# A corpus is the collection of all input files/testcases which trigger unique behavior/coverage.
# When a new fuzzing sessions is started, the corpus files are loaded to memory
# and random files from this corpus are selected in every fuzzing iteration and combined to new testcases
# If the testcase would trigger new behavior, the testcase would be added to the corpus

import os.path
import sys
import testcase_state
import utils
import tagging_engine.tagging as tagging
import modes.deterministic_preprocessing as deterministic_preprocessing
import config as cfg
import datetime
import pickle


class Corpus:
    def __init__(self, output_dir):
        self.current_corpus = []
        self.current_corpus_states = []
        self.current_corpus_filenames = []
        self.output_dir = output_dir
        self.current_corpus_id = 0
        self.number_newly_added_testcases = 0
        
        self.last_newly_added_testcase_time = None
        self.last_newly_added_testcase_time_str = cfg.status_update_time_not_set

        self.number_disabled_corpus_files = 0
        self.permanently_disabled_files = set()

    # Corpus files which often trigger exceptions/hangs can permanently be disabled.
    def permanently_disable_testcase(self, testcase_name):
        if cfg.enable_permanently_disabled_files is False:
            return
        if cfg.permanently_disabled_files_disable_new_files is True:
            return

        self.permanently_disabled_files.add(testcase_name)
        # Save it in the cached permanently disabled file
        with open(cfg.permanently_disabled_files_file, 'wb') as fout:
            pickle.dump(self.permanently_disabled_files, fout, pickle.HIGHEST_PROTOCOL)
        utils.msg("[i] Marked %s as permanently disabled" % testcase_name)

    # Loads the file which stores permanently disabled corpus files from disk to memory
    def load_permanently_disabled_testcases(self):
        if cfg.enable_permanently_disabled_files is False:
            return
      
        if os.path.exists(cfg.permanently_disabled_files_file):
            with open(cfg.permanently_disabled_files_file, 'rb') as finput:
                self.permanently_disabled_files = pickle.load(finput)
                utils.msg("[i] %d testcases are permanently disabled according to %s" % (len(self.permanently_disabled_files), cfg.permanently_disabled_files_file))
        else:
            utils.msg("[i] Tried to load permanently disabled files, but found no .pickle file: %s" % cfg.permanently_disabled_files_file)


    def is_file_permanently_disabled(self, testcase_name):
        if cfg.enable_permanently_disabled_files is False:
            return False
        if testcase_name in self.permanently_disabled_files:
            return True
        return False


    def add_new_testcase_to_corpus(self, code, state, required_coverage, runtime_adjustment_factor=None):
        code = code.rstrip()
        if len(code) == 0:
            return  # should never occur but just to get sure

        self.current_corpus_id += 1
        output_filename = "tc%d.js" % self.current_corpus_id
        output_filepath = os.path.join(self.output_dir, output_filename)
        output_state_filepath = output_filepath + ".pickle"
        with open(output_filepath, "w") as fobj:
            fobj.write(code)

        required_coverage_filepath = output_filepath[:-3] + "_required_coverage.pickle"
        with open(required_coverage_filepath, 'wb') as fout:
            pickle.dump(required_coverage, fout, pickle.HIGHEST_PROTOCOL)


        # The following code ensures that corpus files generated on different systems have "a similar runtime range"
        # e.g. input corpus was generated on a very slow virtual machine and fuzzing is performed on a fast system with a good CPU
        # => the new files would have a very low runtime but compared to other files would be slower
        # => therefore the runtime of new found files is modified because on the dynamically calculated adjustment factor
        if runtime_adjustment_factor is not None:
            state.runtime_length_in_ms = int(float(state.runtime_length_in_ms) / runtime_adjustment_factor)

        state.testcase_filename = output_filename
        testcase_state.save_state(state, output_state_filepath)

        with open(output_state_filepath, "rb") as fobj:
            state_file_content = fobj.read()    # state file content is later required when the state must be synced to a bucket
            
        with open(required_coverage_filepath, "rb") as fobj:
            required_coverage_content = fobj.read()

        # Now check if the file should really be loaded to the active corpus
        if should_testcase_be_loaded(code, state, output_filename):
            self.current_corpus.append(code)
            self.current_corpus_states.append(state)
            self.current_corpus_filenames.append(output_filename)

            self.last_newly_added_testcase_time = datetime.datetime.now().replace(microsecond=0)
            self.last_newly_added_testcase_time_str = self.last_newly_added_testcase_time.strftime(cfg.status_update_time_format)
            self.number_newly_added_testcases += 1
            tagging.add_testcase_filename(output_filename)
            return output_filename, state_file_content, required_coverage_content
        else:
            self.permanently_disable_testcase(output_filename)
            self.number_disabled_corpus_files += 1
            # return None # None means testcase was not added (and e.g. deterministic preprocessing should not be performed)
            # edit: I should still return here something instead of None
            # to make sure that the new file gets synced in the bucket.
            # Otherwise I would not store it in my global results
            return output_filename, state_file_content, required_coverage_content

    def size(self):
        return len(self.current_corpus)


    def get_stats(self):
        return len(self.current_corpus), self.number_newly_added_testcases, self.last_newly_added_testcase_time, self.last_newly_added_testcase_time_str, self.number_disabled_corpus_files


    def load_corpus_from_directory(self):
        utils.msg("[i] Going to load code snippet corpus from: %s" % self.output_dir)

        deterministic_preprocessing_mode_start_tc_id = cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id
        deterministic_preprocessing_mode_stop_tc_id = cfg.fuzzer_arguments.deterministic_preprocessing_mode_stop_tc_id
        biggest_testcase_id = 0
        self.load_permanently_disabled_testcases()
        
        for filename in os.listdir(self.output_dir):
            if filename.endswith("pickle"):
                continue
            if filename.endswith(".js") is False:
                continue

            # utils.msg("Loading JavaScript corpus file: %s" % filename)
            filepath = os.path.join(self.output_dir, filename)
            if os.path.isfile(filepath) is False:
                continue

            with open(filepath, 'r') as fobj:
                content = fobj.read().rstrip()

            # Load the state
            state_filepath = filepath + ".pickle"
            try:
                state = testcase_state.load_state(state_filepath)
            except Exception as e:
                utils.msg("[!] Exception occurred during loading a state, skipping it... (Details: %s)" % repr(e))
                sys.exit(-1)
                # continue

                # It seems that this can happen if the .state file is empty
                # This occurred one time with a fuzzer instance and then the fuzzer "hangs"
                # because the watchdog restarted the fuzzer but the fuzzer could not start because
                # there was a state in the corpus which was empty and could therefore not be loaded
                # I think this either occurred because of a filesystem problem on the fuzzer, a bug in my code
                # or some problem with GCE buckets (e.g. transfer-limits were reached and therefore I got an empty response?)
                # to fix this, I just don't load this testcase with the corrupted state (on this single fuzzer instance)


            state.testcase_filename = filename

            testcase_id = int(filename[2:-3])
            if testcase_id > biggest_testcase_id:
                # Important: Setting biggest testcase ID must be performed because should_testcase_be_loaded() is later called
                biggest_testcase_id = testcase_id

            if self.is_file_permanently_disabled(filename):
                # utils.msg("[-] skipping testcase because it's permanently disabled: %s" % filename)
                self.number_disabled_corpus_files += 1
                continue

            if should_testcase_be_loaded(content, state, filename) is False:
                self.number_disabled_corpus_files += 1
                self.permanently_disable_testcase(filename)
                continue

            self.current_corpus.append(content)
            self.current_corpus_states.append(state)
            self.current_corpus_filenames.append(filename)

            # Deterministic preprocessing:
            # Note: Logically it doesn't make any sense to implement this functionality here...
            # But since this is the only place where I access the filenames of the input corpus
            # I implemented it here.
            # TODO: Maybe move this functionality later to another place
            if deterministic_preprocessing_mode_start_tc_id is not None:
                if testcase_id >= deterministic_preprocessing_mode_start_tc_id:
                    if testcase_id <= deterministic_preprocessing_mode_stop_tc_id:
                        # I'm here just adding the files to the queue of files which will later be preprocessed
                        # Preprocessing will start before the main fuzzer loop is entered
                        deterministic_preprocessing.add_testcase_to_preprocessing_queue(content, state, filename)

        utils.msg("[+] Successfully loaded %d files (additional %d testcases are permanently disabled)" % (len(self.current_corpus), self.number_disabled_corpus_files))
        self.current_corpus_id = biggest_testcase_id
        tagging.set_testcase_filenames(self.current_corpus_filenames)


    def check_if_testcases_should_be_disabled(self):
        utils.msg("[i] Going to check if some testcases can be disabled...")

        testcase_ids_which_should_be_disabled = []
        idx = -1
        for testcase_name in self.current_corpus_filenames:
            idx += 1
            (number_success, number_exception, number_hang) = tagging.get_testcase_stats(testcase_name)
            
            total_executions = number_success + number_exception + number_hang    # doesn't count crashes and so on, but this doesn't matter
            if total_executions < cfg.min_number_testcase_executions_before_disable_check:
                continue    # not enough executions yet, so nothing to check

            percent_exceptions = float(number_exception) / total_executions
            percent_hangs = float(number_hang) / total_executions
            if percent_exceptions >= cfg.disable_check_min_percent_exceptions:
                # disable it
                utils.msg("[i] Going to disable testcase %s because of high exception rate: %.2f" % (testcase_name, percent_exceptions))
                testcase_ids_which_should_be_disabled.append(idx)
                continue
            if percent_hangs >= cfg.disable_check_min_percent_hangs:
                # disable it
                utils.msg("[i] Going to disable testcase %s because of high hang rate: %.2f" % (testcase_name, percent_hangs))
                testcase_ids_which_should_be_disabled.append(idx)
                continue

        utils.msg("[i] Going to disable %d testcases" % len(testcase_ids_which_should_be_disabled))
        self.number_disabled_corpus_files += len(testcase_ids_which_should_be_disabled)
        
        id_adjustment = 0
        for testcase_id in testcase_ids_which_should_be_disabled:
            testcase_id = testcase_id - id_adjustment
            filename = self.current_corpus_filenames[testcase_id]
            # utils.msg("[i] Debug disabling testcase: %s" % self.current_corpus_filenames[testcase_id])
            del self.current_corpus[testcase_id]
            del self.current_corpus_states[testcase_id]
            del self.current_corpus_filenames[testcase_id]
            id_adjustment += 1
            self.permanently_disable_testcase(filename)


    def corpus_iterator(self):
        number_entries = len(self.current_corpus)
        for idx in range(0, number_entries):
            yield self.current_corpus[idx], self.current_corpus_states[idx], self.current_corpus_filenames[idx]


    def get_random_testcase(self, runtime_adjustment_factor=None):
        number_entries = len(self.current_corpus)
        if number_entries == 0:
            utils.perror("corpus.py.get_random_testcase() was called, but it seems like the loaded corpus is empty")

        random_idx = utils.get_random_int(0, number_entries-1)
        content = self.current_corpus[random_idx]

        # The following call to deep_copy() is very important!
        # Since the returned state will be modified (e.g.: merged with other states)
        # It's important that I return a copy. Otherwise the states of corpus entries will get modified.
        state = self.current_corpus_states[random_idx].deep_copy()
        if runtime_adjustment_factor is not None:
            state.runtime_length_in_ms = int(state.runtime_length_in_ms * runtime_adjustment_factor)
        filename = self.current_corpus_filenames[random_idx]

        return filename, content, state


    def print_corpus(self):
        for i in range(len(self.current_corpus)):
            print("Corpus file: %d" % i)
            (code, result) = self.current_corpus[i]
            print("Code: %s" % code)
            print("New edges: %d, total edges: %d" % (result.num_new_edges, result.num_edges))
            print("")



def should_testcase_be_loaded(code, state, filename):
    if cfg.max_runtime_of_input_file_in_ms != 0 and state.runtime_length_in_ms > cfg.max_runtime_of_input_file_in_ms:
        # utils.dbg_msg("[i] skipping input because of too long runtime: %d ms, testcase: %s" % (state.runtime_length_in_ms, filename))
        return False

    if len(state.lines_where_code_can_be_inserted) == 0 and len(
            state.lines_where_code_with_coma_can_be_inserted) == 0 and len(
            state.lines_where_code_with_start_coma_can_be_inserted) == 0:
        # utils.msg("[-] skipping input because it can't be combined with other testcases: %s" % filename)
        return False

    if "new Worker" in code:
        # utils.msg("[-] skipping input because it contains a Worker: %s" % filename)
        # Workers spawn a 2nd v8 process which I currently don't terminate
        # => after some time it would "fork-bomb" a system during fuzzing
        return False

    if "WebAssembly.validate" in code:
        # utils.msg("[-] skipping input because it contains WebAssembly.validate: %s" % filename)
        # I have "a lot of" testcases similar to:
        # let var_1_ = new Uint8Array([ 0, 97, 115, 109, /*...*/ 1, 128, 0, 1,]);
        # var var_2_ = WebAssembly.validate(var_1_);
        # And only the bytes in the array are always different
        # I think fuzzing these testcases is a waste of resources, so I'm skipping them
        # If I really want to fuzz such testcases, I can implement a specific mutation strategy which just
        # modifies these numbers but nothing else..
        return False

    if "new WebAssembly.Module(var" in code or "new WebAssembly.Module(func_" in code:
        # utils.msg("[-] skipping input because it contains new WebAssembly.Module(var: %s" % filename)
        # These testcases should be fuzzed separately, similar to the above WebAssembly.validate example
        return False

    if "new WebAssembly.Module(new " in code:
        # utils.msg("[-] skipping input because it contains new WebAssembly.Module(new : %s" % filename)
        # Code like: new WebAssembly.Module(new Uint8Array([
        return False

    if "new WebAssembly.Instance(" in code:
        # contains code like:
        # new WebAssembly.Instance(new WebAssembly.Module(new Uint8Array
        # and then the Uint8Array contains fuzzed byte-numbers
        # utils.msg("[-] skipping input because it contains new WebAssembly.Instance(: %s" % filename)
        return False

    if "%GetOptimizationStatus" in code:
        lines = code.split("\n")
        for idx in range(0, len(lines)):
            current_line = lines[idx]
            next_line = ""
            if idx != (len(lines) - 1):
                next_line = lines[idx + 1]
            if "%GetOptimizationStatus" in current_line:
                if next_line.startswith(","):
                    # utils.msg("[-] skipping input because it contains %%GetOptimizationStatus: %s" % filename)
                    return False

    possible_lines = state.lines_where_code_can_be_inserted + state.lines_where_code_with_coma_can_be_inserted + state.lines_where_code_with_start_coma_can_be_inserted
    contains_at_least_one_line_where_code_can_be_inserted = False
    for line_number in possible_lines:
        if line_number not in state.lines_which_are_not_executed:
            contains_at_least_one_line_where_code_can_be_inserted = True
            break

    if contains_at_least_one_line_where_code_can_be_inserted is False:
        # this mainly occurs when the testcase is very slow and therefore extraction of line executions
        # didn't worked. But I also don't want to use these slow testcases (which also have an incorrect state)
        # utils.msg("[-] skipping input because code can't be inserted: %s" % filename)
        return False

    # Check if the state is correct:
    # Check the number of lines:
    # There are some testcases which have unicode stored and I think I currently load them the wrong way
    # e.g.: tc13538.js
    # During state file creation len(content.split("\n")) returned 6,
    # however, after saving the content to a file and loading it, the same
    # code now returns 8 as number of code lines. This screws up the fuzzer.
    # This is because of the unicode symbols stored in the testcase.
    # TODO: later I need to determine why I incorrectly store the code,
    # but for now I just don't load these testcases
    # At the moment this affects 3 testcases:
    # tc12894.js
    # tc13538.js
    # tc12985.js
    number_of_lines = len(code.split("\n"))
    if number_of_lines != state.testcase_number_of_lines:
        # utils.msg("[-] skipping input because it has an incorrect number of lines: %s" % filename)
        return False

    return True
