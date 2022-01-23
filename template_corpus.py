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



# The template corpus files.
# Typically I don't want to load all template files into memory because
# it can easily lead to several hundred thousand of template files
# Keeping all template files in memory would consume too much RAM
# e.g.: the fuzzer should be able to run on a 1 GB AWS machine to keep cost low
# All filenames are therefore initially read and the fuzzer selects e.g. 100 random
# template files which will be used for e.g. the next 10 000 fuzzing iterations.
# Using this approach the number of in-memory files can be kept low and the fuzzer should
# try to fuzz all template files
#
# TODO: support template directories
# TODO: ensure that template selection uses templates which are "special" (e.g.: not common callbacks, ...) => Find a heuristic for this!


import os.path
import utils
import config as cfg
import testcase_state
import pickle


class Template_Corpus:
    def __init__(self, template_dir):
        self.template_file_names_self_created = []
        self.template_file_names_injected = []
        self.template_dir = template_dir

        self.inmemory_corpus_filename = []
        self.inmemory_corpus_files = []
        self.inmemory_corpus_states = []
        self.how_often_a_template_file_was_queried = 0  # counts how often the get_random_testcase() function was called to know when in-memory files should be replaced with new random files

        # Note: I keep 3 lists of "in-memory loaded" files:
        # *) the general list like >inmemory_corpus_files<
        # *) one just for "self created" templates like: >inmemory_corpus_files_self_created<
        # *) one just for "callback injected" templates like: >inmemory_corpus_files_callback_injected<
        # => This is required for the "adjust_runtime" functionality because .state files for
        # "self created" and "callback injected" were calculated on different systems, so 
        # the runtime adjustment must be executed separately.
        # Moreover, some mutations techniques expect that they are separated (e.g. only get testcases with injected callbacks..)

        # Same as above just but just for "self created" templates
        self.inmemory_corpus_filename_self_created = []
        self.inmemory_corpus_files_self_created = []
        self.inmemory_corpus_states_self_created = []
        self.how_often_a_template_file_was_queried_self_created = 0     # counts how often get_random_testcase_self_created() was called

        # Same as above just but just for "callback injected" templates
        self.inmemory_corpus_filename_callback_injected = []
        self.inmemory_corpus_files_callback_injected = []
        self.inmemory_corpus_states_callback_injected = []
        self.how_often_a_template_file_was_queried_callback_injected = 0    # counts how often get_random_testcase_callback_injected() was called


    def size(self):
        return len(self.template_file_names_self_created), len(self.template_file_names_injected)


    def load_random_files_into_memory_self_created(self):
        # utils.msg("[i] load_random_files_into_memory_self_created()")

        self.inmemory_corpus_filename_self_created.clear() 
        self.inmemory_corpus_files_self_created.clear()
        self.inmemory_corpus_states_self_created.clear()
        
        selected_filenames = []
        number_total_entries = len(self.template_file_names_self_created)
        if number_total_entries <= cfg.template_files_how_many_inmemory_files:
            selected_filenames = self.template_file_names_self_created
        else:
            # Select random files
            while len(selected_filenames) < cfg.template_files_how_many_inmemory_files:
                selected_filenames.append(utils.get_random_entry(self.template_file_names_self_created))

        for filename in selected_filenames:
            filepath = os.path.join(self.template_dir, filename)
            with open(filepath, 'r') as fobj:
                content = fobj.read().rstrip()
                self.inmemory_corpus_files_self_created.append(content)
            state_filepath = filepath + ".pickle"
            state = testcase_state.load_state(state_filepath)
            self.inmemory_corpus_states_self_created.append(state)
            self.inmemory_corpus_filename_self_created.append(filename)


    def load_random_files_into_memory_callback_injected(self):
        # utils.msg("[i] load_random_files_into_memory_callback_injected()")

        self.inmemory_corpus_filename_callback_injected.clear() 
        self.inmemory_corpus_files_callback_injected.clear()
        self.inmemory_corpus_states_callback_injected.clear()
        
        selected_filenames = []
        number_total_entries = len(self.template_file_names_injected)
        if number_total_entries <= cfg.template_files_how_many_inmemory_files:
            selected_filenames = self.template_file_names_injected
        else:
            # Select random files
            while len(selected_filenames) < cfg.template_files_how_many_inmemory_files:
                selected_filenames.append(utils.get_random_entry(self.template_file_names_injected))

        for filename in selected_filenames:
            filepath = os.path.join(self.template_dir, filename)
            with open(filepath, 'r') as fobj:
                content = fobj.read().rstrip()
                self.inmemory_corpus_files_callback_injected.append(content)
            state_filepath = filepath + ".pickle"
            state = testcase_state.load_state(state_filepath)
            state.testcase_filename = "template(%s)" % filename  # set the filename for debugging
            self.inmemory_corpus_states_callback_injected.append(state)
            self.inmemory_corpus_filename_callback_injected.append(filename)


    def load_random_files_into_memory(self):
        # utils.msg("[i] load_random_files_into_memory()")
        
        self.inmemory_corpus_filename.clear() 
        self.inmemory_corpus_files.clear()
        self.inmemory_corpus_states.clear()
        
        selected_filenames = []
        number_total_entries = len(self.template_file_names_self_created) + len(self.template_file_names_injected)
        if number_total_entries <= cfg.template_files_how_many_inmemory_files:
            # E.g. I just have 200 self created and 500 callback injected templates, but 
            # >template_files_how_many_inmemory_files< is 1000
            # => in this case I just take all available files because they are less than 1000 and I therefore don't have to
            # randomly select some files
            selected_filenames = self.template_file_names_self_created + self.template_file_names_injected
        else:
            # Select random files
            number_self_created_templates_to_load = int(cfg.template_files_how_many_inmemory_files * cfg.percent_of_templates_self_created)
            number_injected_callback_templates_to_load = cfg.template_files_how_many_inmemory_files - number_self_created_templates_to_load
            # print("number_self_created_templates_to_load: %d" % number_self_created_templates_to_load)
            # print("number_injected_callback_templates_to_load: %d" % number_injected_callback_templates_to_load)

            # Load self created templates
            while len(selected_filenames) < number_self_created_templates_to_load:
                selected_filenames.append(utils.get_random_entry(self.template_file_names_self_created))

            # Load injected callback templates
            while len(selected_filenames) < cfg.template_files_how_many_inmemory_files:
                selected_filenames.append(utils.get_random_entry(self.template_file_names_injected))

            
        for filename in selected_filenames:
            # print("Selected: %s" % filename)
            filepath = os.path.join(self.template_dir, filename)
            with open(filepath, 'r') as fobj:
                content = fobj.read().rstrip()
            
            if "new Worker" in content:
                # Workers spawn a 2nd v8 process which I currently don't terminate
                # => after some time it would "fork-bomb" a system during fuzzing
                # TODO: In worst case every selected file has a worker, then the >inmemory_corpus_files<
                # would be empty. But I assume that this will not happen during fuzzing..
                continue

            self.inmemory_corpus_files.append(content)
            state_filepath = filepath + ".pickle"
            state = testcase_state.load_state(state_filepath)
            state.testcase_filename = "template(%s)" % filename     # set the filename for debugging
            self.inmemory_corpus_states.append(state)
            self.inmemory_corpus_filename.append(filename)


    def save_cache_file(self):
        cached_file = [None, None]
        cached_file[0] = self.template_file_names_self_created
        cached_file[1] = self.template_file_names_injected
        output_fullpath = os.path.join(self.template_dir, cfg.cache_filename_template_corpus)
        utils.msg("[i] Saving template corpus in cache file: %s" % output_fullpath)
        with open(output_fullpath, 'wb') as fout:
            pickle.dump(cached_file, fout, pickle.HIGHEST_PROTOCOL)


    def load_cache_file(self):
        input_fullpath = os.path.join(self.template_dir, cfg.cache_filename_template_corpus)
        if os.path.exists(input_fullpath) is False:
            return False    # Cache file doesn't exist yet
        utils.msg("[i] Load template corpus cache file: %s" % input_fullpath)
        with open(input_fullpath, 'rb') as finput:
            cached_file = pickle.load(finput)
        self.template_file_names_self_created = cached_file[0]
        self.template_file_names_injected = cached_file[1]
        if len(self.template_file_names_self_created) == 0 and len(self.template_file_names_injected) == 0:
            return False    # cache seems to be incorrect
        return True     # successfully loaded


    def load_corpus_from_directory(self):
        utils.msg("[i] Going to load template file corpus...")
        already_loaded = False
        if cfg.cache_template_corpus:
            # Try to load
            already_loaded = self.load_cache_file()
        if already_loaded is False:     # caching not enabled or cache file was not created yet, so manually load it
            for filename in os.listdir(self.template_dir):
                if filename.endswith("pickle"):
                    continue
                if filename.endswith(".js") is False:
                    continue

                filepath = os.path.join(self.template_dir, filename)
                if os.path.isdir(filepath):
                    foldername = filename
                    # If this point is reached it's a directory of a testcase where callbacks were injected
                    for sub_filename in os.listdir(filepath):
                        if sub_filename.endswith("pickle"):
                            continue
                        if sub_filename.endswith(".js") is False:
                            continue
                        sub_path = os.path.join(foldername, sub_filename)
                        self.template_file_names_injected.append(sub_path)
                    continue
                if os.path.isfile(filepath) is False:
                    continue    # should never occur
                
                # If this point is reached it's a "self created" template file
                self.template_file_names_self_created.append(filename)  # I just store the filename, the fullpath would waste a lot of RAM (for a big corpus)
            if cfg.cache_template_corpus:
                self.save_cache_file()

        self.load_random_files_into_memory()
        self.load_random_files_into_memory_self_created()
        self.load_random_files_into_memory_callback_injected()
        utils.msg("[+] Successfully loaded %d (self) and %d (injected) template files" % self.size())


    def get_random_testcase(self, runtime_adjustment_factor_self_created=None, runtime_adjustment_factor_injected_callbacks=None):
        self.how_often_a_template_file_was_queried += 1
        if self.how_often_a_template_file_was_queried >= cfg.template_files_after_how_many_executions_reload_inmemory_files:
            self.how_often_a_template_file_was_queried = 1  # reset the counter; sets it to 1 because this call will return a new file
            self.load_random_files_into_memory()

        number_entries = len(self.inmemory_corpus_files)
        if number_entries == 0:
            return None
        random_idx = utils.get_random_int(0, number_entries-1)
        content = self.inmemory_corpus_files[random_idx]

        # The following call to deep_copy() is very important!
        # Since the returned state will be modified (e.g.: merged with other states)
        # It's important that I return a copy. Otherwise the states of corpus entries will get modified!
        state = self.inmemory_corpus_states[random_idx].deep_copy()
        filename = self.inmemory_corpus_filename[random_idx]

        if "/" in filename:
            # injected callbacks
            if runtime_adjustment_factor_injected_callbacks is not None:
                state.runtime_length_in_ms = int(state.runtime_length_in_ms * runtime_adjustment_factor_injected_callbacks)
        else:
            # self created
            if runtime_adjustment_factor_self_created is not None:
                state.runtime_length_in_ms = int(state.runtime_length_in_ms * runtime_adjustment_factor_self_created)

        return filename, content, state


    def get_random_testcase_self_created(self, runtime_adjustment_factor_self_created=None):
        self.how_often_a_template_file_was_queried_self_created += 1
        if self.how_often_a_template_file_was_queried_self_created >= cfg.template_files_after_how_many_executions_reload_inmemory_files:
            self.how_often_a_template_file_was_queried_self_created = 1  # reset the counter; sets it to 1 because this call will return a new file
            self.load_random_files_into_memory_self_created()

        number_entries = len(self.inmemory_corpus_files_self_created)
        if number_entries == 0:
            return None
        random_idx = utils.get_random_int(0, number_entries-1)
        content = self.inmemory_corpus_files_self_created[random_idx]

        # The following call to deep_copy() is very important!
        # Since the returned state will be modified (e.g.: merged with other states)
        # It's important that I return a copy. Otherwise the states of corpus entries will get modified!
        state = self.inmemory_corpus_states_self_created[random_idx].deep_copy()
        filename = self.inmemory_corpus_filename_self_created[random_idx]

        if runtime_adjustment_factor_self_created is not None:
            state.runtime_length_in_ms = int(state.runtime_length_in_ms * runtime_adjustment_factor_self_created)
        return filename, content, state


    def get_random_testcase_callback_injected(self, runtime_adjustment_factor_injected_callbacks=None):
        self.how_often_a_template_file_was_queried_callback_injected += 1
        if self.how_often_a_template_file_was_queried_callback_injected >= cfg.template_files_after_how_many_executions_reload_inmemory_files:
            self.how_often_a_template_file_was_queried_callback_injected = 1  # reset the counter; sets it to 1 because this call will return a new file
            self.load_random_files_into_memory_callback_injected()

        number_entries = len(self.inmemory_corpus_files_callback_injected)
        if number_entries == 0:
            return None
        random_idx = utils.get_random_int(0, number_entries-1)
        content = self.inmemory_corpus_files_callback_injected[random_idx]

        # The following call to deep_copy() is very important
        # Since the returned state will be modified (e.g.: merged with other states)
        # It's important that I return a copy. Otherwise the states of corpus entries will get modified!
        state = self.inmemory_corpus_states_callback_injected[random_idx].deep_copy()
        filename = self.inmemory_corpus_filename_callback_injected[random_idx]

        if runtime_adjustment_factor_injected_callbacks is not None:
            state.runtime_length_in_ms = int(state.runtime_length_in_ms * runtime_adjustment_factor_injected_callbacks)
        return filename, content, state
