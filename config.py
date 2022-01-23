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



# Configuration file of the fuzzer.


import os.path
import sys
import platform

fuzzer_basefolder = os.path.dirname(os.path.abspath(__file__))


# Paths to compiled v8 binaries
v8_path_with_coverage = "/home/user/Desktop/JavaScriptEngines/v8_31.Dez.2021_with_coverage/d8"
v8_path_without_coverage = "/home/user/Desktop/JavaScriptEngines/v8_01.Aug.2021_without_coverage/d8"
v8_path_debug_without_coverage = "/home/user/Desktop/JavaScriptEngines/currently_not_compiled/d8"


v8_shm_id = 1138


# Bigger number of in-memory executions before a JS engine restart increase the exec/speed because the engine
# has to be started fewer times.
# However: A too big value is also bad because the "in-memory" executions are not 100% separated
# My assumption is that global variables are shared between "in-memory" executions
# So if testcase1 modifies a global variable and testcase2 works with this variable, it can lead to
# a crash/hang of the 2nd testcase, although the 2nd testcase alone would not crash/hang
# I therefore try to keep this number small, but at the same time big enough get a good fuzzer speed
# use something between 50-300 (I use 100)
v8_restart_engine_after_executions = 100    # After X in-memory executions the engine gets restarted

# I calculate per testcase the expected runtime. This value is multiplied to the runtime
# to get the used timeout value. E.g. if I combine 2 testcases, I also sum up the expected runtime from both samples
# but because merging can lead to a longer runtime (e.g. testcase2 is embedded in a loop in testcase1) I also
# use this factor here. This is also used to count for additional runtime because of possible applied mutations.
v8_default_timeout_multiplication_factor = 2.0

# If the resulting timeout would be 400 and this setting is 500, I would change it to 500 ms timeout
v8_timeout_per_execution_in_ms_min = 500

# Enforce a maximum runtime to ensure that slow testcases can't slow down fuzzing
v8_timeout_per_execution_in_ms_max = 2000

# Corpus minimizer has a longer runtime to ensure that testcases which are close to the runtime max boundary
# get fully minimized.
v8_timeout_per_execution_in_ms_corpus_minimizer = 3000

# The testsuite max. runtime is a lot slower so ensure that tests run fast
# I'm triggering intentionally multiple timeouts in the tests and to ensure that they
# are triggered quickly, I use here a shorter timeout
v8_timeout_per_execution_in_ms_testsuite = 400

# I make the timeout here a little bit smaller because I don't want slow templates
# Moreover, I'm creating templates using a JS engine with coverage feedback turned off
# which should be by itself a lot faster
v8_timeout_templates_creation = 800

# When the corpus was created on another machine with different specs (e.g. another CPU),
# the runtime can be different during fuzzing than the expected runtime from the state-file
# Initially I dynamically adjusted the runtime.
# However, I now disabled this and instead I recalculate the correct runtimes by starting the fuzzer
# with the "--recalculate_testcase_runtimes" flag.
# "dynamic_runtime_adjustment" means that the fuzzer tries to initially execute some testcases without modification
# and try to detect an adjustment factor which must be applied to the expected runtime to get the real runtime.
# But it's better to first call the fuzzer with "--recalculate_testcase_runtimes"
# => This will update the runtimes in all testcase state files for the current CPU (every testcase will get executed)
enable_dynamic_runtime_adjustment = False
adjust_runtime_executions = 64
adjust_runtime_remove_first_and_last_number_of_entries = 7


# The built-in JS engine command to execute commands in the JS engine (e.g. print to the STDOUT fuzzer channel or
# to trigger a bash to test the engine/executor).
v8_fuzzcommand = "fuzzilli"
v8_print_command = "FUZZILLI_PRINT"
v8_crash_command = "FUZZILLI_CRASH"

v8_temp_print_id = "_PRINT_ID_"
v8_print_start = "%s('%s'," % (v8_fuzzcommand, v8_print_command)
v8_print_js_codeline = "%s '%s')" % (v8_print_start, v8_temp_print_id)  # line like: fuzzilli('FUZZILLI_PRINT', '_PRINT_ID_');

v8_print_id_prefix = "_PRINT_"      # Should not start completely the same as >v8_temp_print_id<

# We must add a postfix, otherwise it can detect stuff incorrectly.
# E.g.: _PRINT_1 has same beginning as _PRINT_12, but _PRINT_1_ doesn't has some
# starting as _PRINT_12_; Therefore the _ at the end is important
v8_print_id_postfix = "_"
v8_print_id_not_printed = "_NOT_PRINTED_"
v8_print_id_not_reachable = "_NOT_REACHED_"

# This are global JS tokens which are just available in d8 but not in the JS engine in Chrome
# or which I should skip for various reasons (e.g. calling quite would hinder fuzzing...)
v8_globals_to_ignore = ["quit", "read", "readbuffer", "readline", "load", "print", "testRunner", "gc", "version", "undefined", "Realm", "os", v8_fuzzcommand, "var_1_"]

status_update_time_format = "%Y-%m-%d %H:%M"
status_update_time_not_set = "not yet seen"

# How often the fuzzer GUI should be updated
# Updating is not costly, so you can pretty frequently update the GUI
status_update_after_x_executions = 500

# Dumping tagging results is costly, I would not dump them too often
# E.g.: after 20 000 in-memory executions
dump_tags_after_x_executions = 20000
tagging_filename_extension = ".tags"


measure_mode_number_of_status_updates = 5   # higher value => means that measure mode runs longer but is more precise


# When the fuzzer is started, it dynamically extracts available global JS tokens from the engine
# The tokens/names can be cached, which is recommended.
# Instead of dynamically extracting the values, the fuzzer would then take the cached tokens.
load_cached_globals = True
pickle_database_globals = "globals.pickle"


# precise curly bracket calculation means that the fuzzer tries to find the real "{" positions
# A lot of operations require the knowledge of the {}-blocks, for example, when moving operations
# around or when adding a new variable to determine the scope of it.
# Problems can occur in testcases like:
# var var_1_ = "foo{bar" ; if { ... }
# => When "precise curly bracket mode" is enabled, the { symbol in the foo{bar string will be ignored.
# If precise curly bracket mode is disabled, the fuzzer would take the { inside the string
# which leads to wrong results and therefore to more generated exceptions
# Reason why I previously had the mode turned off:
# The implementation was very slow.
# It consumed 8% of the overall time (and just 92% of the time for real fuzzing) (by adding 2 variables to each testcase)
# When adding 20 variables to a testcase, it changes to 50% waste of time in the calculate_curly_bracket_offsets() function.
# Current situation:
# I finally re-implemented it in C, so it should be fine to always use the precise mode :)
precise_curly_bracket_calculation_mode_enabled = True


# The fuzzer must create a backup of the global coverage map in various operations like the minimizer
# to restore the previous coverage. (e.g. during minimization, it must restore the coverage map always be able
# to trigger coverage again)
coverage_map_minimizer_filename = "minimizer_coverage_map.map"
coverage_map_corpus_minimizer = "corpus_minimizer_coverage_map_restore.map"
final_coverage_map_file = "final_coverage_map.map"
previous_coverage_map_file = "previous_coverage_map.map"
coverage_map_testsuite = "testsuite_coverage_map.map"
# TODO: Maybe rename the files to "coverage_map_XYZ.bin"


# The current corpus contains all files from the corpus
current_corpus_dir = "current_corpus"

# The new_files folder contains all newly discovered files.
# Be aware: It can contain files which are not stored in the current_corpus.
# I think the current implementation stores new files in this folder, but then re-verifies if coverage can be triggered
# again. If this fails, it will not be stored in current_corpus.
# Reason: After long fuzzing sessions I collect all "new_coverage" files and try to again import them to the corpus.
# This will typically find again some new behavior files (which for some reason were not reliable in the 2nd execution
# during fuzzing).
new_files_dir = "new_coverage"

# All crashes are stored here:
crash_dir = "crashes"

# I added "crash_exceptions" because I had some testcases which returned a "crash" according to
# fuzzilli's REPRL implementation, but which are not real crashes. I think this are testcases which spawn
# another JS engine instance, for example, if the testcases uses JavaScript Workers.
# I think in most cases I can ignore these crash_exceptions, but I stored them to further see which files the
# fuzzer would find.
crash_exception_dir = "crash_exceptions"

# The database dir contains created databases for the current corpus
# For example, strings and numbers, which are used by the corpus as well as
# extracted JavaScript operations
databases_dir = "databases"


# Used by "modes/corpus_minimizer.py"
current_corpus_minimized_dir = "current_corpus_minimized"

# The fuzzer has a mode to recalculate the coverage map (--recalculate_coverage_map)
# This mode is used when the JS engine is updated and the coverage map therefore doesn't match the used JS engine.
# The below setting specifies how often a testcase should be executed in this mode to generated a new coverage map.

# TODO: Maybe I have a logic flaw here? During fuzzing my code executes a new testcase up to 125 times until it
# doesn't trigger new coverage again (because of in-deterministic behavior). When I recalculate the coverage map,
# I just execute these testcases 5 times. This means that this in-deterministic behavior will maybe later be
# triggered again during fuzzing and I would add useless testcases to the corpus... I should change the
# recalculate-coverage-map implementation..
number_executions_during_initial_coverage_map_calculation = 5   # should be 3-5

# My current template corpus is pretty big (~230 000 files).
# The fuzzer would have to load all template corpus file names (but not contents) into memory during startup
# This takes several minutes for a big corpus.
# I'm therefore caching all filenames in a pickle file, which can be loaded a lot faster
# However, if you update the template corpus (e.g. remove or add template files),
# you must change >cache_template_corpus< to False for one fuzzer execution.
# Note: At the moment I would not recommend using the template corpus at all (it's currently in-efficient).
cache_template_corpus = True
cache_filename_template_corpus = "template_corpus_cache.pickle"




# Mutation configuration
testcases_to_combine_min = 1
testcases_to_combine_max = 2    # 2

number_mutations_min = 2    # 1
number_mutations_max = 3   # 2

number_late_mutations_min = 2   # 1
number_late_mutations_max = 3   # 2

template_number_mutations_min = 0
template_number_mutations_max = 1 
template_number_late_mutations_min = 1
template_number_late_mutations_max = 2

# 0.2 means 20% of templates are self created files and other 80% are testcases with injected callbacks
# Here are some notes to my current corpus:
# 9 867 self created template files
# 360 191 injected template files
# Since I want a fair distribution, the self created percentage must be very low because
# I have so many injected template files
# E.g.: 3 % (value: 0.03) would mean when I create 400 000 files
# 400 000 * 0.03 = 12 000 self created files would be taken
# and 400 000 * 0.97 = 388 000 injected template files
# which sounds fair
percent_of_templates_self_created = 0.05


# Set to True to also use the template corpus (currently disabled because templates didn't perform that well)
templates_enabled = False

likelihood_to_load_template_file = 0.33     # should be something like 0.5 - 0.25
templates_to_combine_min = 1
templates_to_combine_max = 1    # don't set this to a too big value => testcases will run too long and hang!

# If a template file has e.g. 15 callback locations, then in most of the cases I just want to use some of them
# e.g. 3. This variable specifies how many callback locations are approximately used.
# If the value is 3, but the template file just contains 1 location, then the fuzzer obvious would just add
# at 1 location code
# Hint: Don't make this number too high, otherwise the fuzzer creates too many testcases with exceptions
template_number_insertion_points_to_use = 2     # e.g. 3

# Currently it's better to use database operations because they have a bigger success rate
# The self created operations have a high exception rate, therefore I'm using more database operations
# However: for Array-operations the self-created should be better because they have a higher likelihood to trigger
# a bug...
likelihood_template_insert_operation_from_database = 0.8

likelihood_template_insert_array_operation = 0.15 

# Keep the "testcases_to_combine_for_insertion_point_in_template_*" values very small
# e.g. 1 or 2, otherwise the testcases with templates quickly become very huge
testcases_to_combine_for_insertion_point_in_template_min = 1
testcases_to_combine_for_insertion_point_in_template_max = 1


# Just load e.g.: 100 template files into memory and make the next e.g. 10 000 iterations just using these 100 files
template_files_how_many_inmemory_files = 1000

# after this number of executions the templates are replaced with the next random "inmemory" templates
template_files_after_how_many_executions_reload_inmemory_files = 50000

test_mode_number_iterations = 10000   # number iterations how often a mutation/merging operation is tested

# I can configure to skip inputs which are very slow; this will speed up fuzzing;
# This option is mainly used for testing. In a real fuzzing session, the corpus itself should be trimmed
# so that the coverage map also reflects that less files will be loaded and the fuzzer can find
# faster testcases which trigger the same coverage
max_runtime_of_input_file_in_ms = 800       # Set to 0 to disable this option    


# Deterministic preprocessing: Perform 20-30 deterministic fuzzing operations on every new found testcase
# These 20-30 operations often lead to new coverage and it therefore makes sense to apply them to all
# new testcases.
# However, enabling it will take very long because execution speed drops
# from 30-40 execs to 2-3 exec/sec.
# I think I currently somewhere restart the engine during deterministic preprocessing
# TODO: Check this
# Since I don't find too many new behavior files currently, enabling it should not hurt.
# But if you start with a new corpus (or bad corpus), I would disable it.
deterministic_preprocessing_enabled = False 


# The data_extractors/* scripts extract strings which are used in testcases from the corpus
# This is the file which caches the extracted strings
# The file is stored in the databases folder in the OUTPUT fuzzer directory
pickle_database_path_strings = "strings.pickle"

# The data_extractors/* scripts extract numbers which are used in testcases from the corpus
# This is the file which caches the extracted numbers
# The file is stored in the databases folder in the OUTPUT fuzzer directory
pickle_database_path_numbers = "numbers.pickle"


# The data_extractors/* extract variable or generic operations which are used in testcases from the corpus
# The extracted operations (and states) are stored in the following files:
pickle_database_generic_operations = "generic_operations.pickle"
pickle_database_variable_operations = "variable_operations.pickle"
pickle_database_variable_operations_others = "variable_operations_others.pickle"
pickle_database_variable_operations_states_list = "variable_operations_states_list.pickle"
pickle_database_variable_operations_list = "variable_operations_list.pickle"


# Tagging Configuration:
tagging_enabled = True
tagging_filename_template = "%d_%d_tagging_log.csv"  # should contain 2 %s: first for start timestamp and 2nd for used seed
status_filename_template = "%d_%d_status_log.txt"    # should contain 2 %s: first for start timestamp and 2nd for used seed
logfile_filename_template = "%d_%d_fuzzer_log.txt"   # should contain 2 %s: first for start timestamp and 2nd for used seed


# Mutation configuration
mutation_stresstest_transition_tree_number_of_mutations_min = 2
mutation_stresstest_transition_tree_number_of_mutations_max = 4     # don't make it too big => it dramatically slows down fuzzing
mutation_stresstest_transition_tree_number_other_variables_min = 1
mutation_stresstest_transition_tree_number_other_variables_max = 2  # don't make it too big => it dramatically slows down fuzzing
mutation_stresstest_transition_likelihood_use_new_variable = 0.5
mutation_stresstest_transition_likelihood_second_additional_mutation = 0.5
mutation_stresstest_transition_likelihood_shuffle_order_of_mutations = 0.4


# Synchronisation configuration:
synchronization_enabled = False
# Hack to disable synchronization on local machine during development
if platform.node() == "fuzzer-dev":
    synchronization_enabled = False


# Hint 1:
# To use synchronization you need to create a bucket in GCE
# Here is a short video which I used to create the bucket: https://www.youtube.com/watch?v=yStmKhLvay4
# If you access the bucket from systems on GCE you don't need the service account json keyfile
# This file is just required if you want to view the files from a local system
# The code in this fuzzer assumes that all fuzzing instances run in GCE and therefore doesn't use the json file

# Hint 2:
# I would recommend to double-check the ACL of the bucket to ensure that it's not public and world-viewable
# You can do this with the following commands:
# gcloud auth activate-service-account --key-file=<path_to_key_file.json>
# gsutil acl get gs://<bucket_name>

# Hint 3:
# The code assumes that the required folder structure already exists
# So folders like "crashes",  "stats", ... must manually be created before the fuzzer is started
bucket_name = "your_bucket_name_goes_here"
bucket_crashes_folder = "crashes"
bucket_new_behavior_folder = "new_behavior"
bucket_new_corpus_files_folder = "new_corpus_files"
bucket_stats_folder = "stats"


# When I start fuzzing, I measure which files result how often in
# a hang or an exception. Files with lots of hangs or exceptions are slow/inefficient
# and I therefore disable them.
# However, I can just perform these checks when the files were already executed at least 10 times or something like that
# When I have a corpus of 18 000 files, then executing every of these files can take approximately 180 000 executions
# (or 90 000 execs if I merge 2 files with 1 execution) => That means the files will just get disabled after several hours
# since I'm fuzzing with a lot of VM's like 500 VM's, all 500 VM's would need to do these 180 000 executions before
# files get disabled. Moreover, this requires tagging to be enabled because I check the exception/hang currently via tagging
# So, the idea is to permanently disable corpus files and store them in a .pickle file
# so that they are not loaded at all when I start a new fuzzing session
# Another benefit: When injecting callbacks to create template files I don't want to inject into such testcases which often
# result in a hang/exception => I can just ignore the permanently disabled files
# Important: Disabling files at runtime just works if tagging is enabled (tagging_enabled=True)
# because tags are required to detect faulty testcases
enable_permanently_disabled_files = True

permanently_disabled_files_file = "disabled_files.pickle"

# In case I test new mutation strategies and they contain a bug, they would disable a lot of testcases
# In such a case, the following variable can be changed to True which means that no more files will get disabled!
permanently_disabled_files_disable_new_files = False


# This value also depends on the following variable (min_number_testcase_executions_before_disable_check)
# Let's assume >min_number_testcase_executions_before_disable_check< is 10
# and my corpus size is 14 000 testcases
# Then I need to perform at least 10 * 14 000 = 140 000 executions before it would make sense
# to implement the "should testcase be disabled check". But since some testcases will occur more frequently (statistics) it
# may already make sense to implement the check after 100 000 executions instead of 140 000
# => Note: Since the fuzzer also combines testcases (e.g. combine 2 testcases into 1 fuzzing execution)
# this also needs to be considered. That's why I changed below min executions from 10 to 16
# 100 000 executions should take in the slow, fully instrumented engine approximately 1,5 - 2 hours runtime
invoke_check_to_disable_testcases_all_X_executions = 40000  # old value: 100000


# I keep the following setting currently low because I fuzz on several machines for a short time (e.g. preemptive machines on GCE
# or spot machines on AWS)
# If you fuzz on a single system for a longer time like several weeks this value can (and maybe should) be increased
min_number_testcase_executions_before_disable_check = 10    # 10

# 0.75 => testcases which result in more than 75% of the time in exceptions will get disabled
disable_check_min_percent_exceptions = 0.75

# testcases which result in more than X% of the time in hangs get disabled
# 0.31 => ~ 250 testcases will be disabled; 0.20 => ~1000 testcases will be disabled;
disable_check_min_percent_hangs = 0.31

gce_bucket_credential_path = None     # not required if fuzzer runs on GCE system;
# Just needs to be set if fuzzing instance runs on a different (e.g.: local) system
# gce_bucket_credential_path = "/path/to/key/bucket_service_account_credentials.json"


synchronization_already_imported_files_filepath = "imported.pickle"
tmp_file_to_import_states = "temp_state.pickle"
sync_after_X_seconds = 10*60    # Sync with the GCE bucket every 10 minutes



# Before I clear a directory the user must first configure the directory manually as a safeguard
output_directory_for_safecheck = "/home/user/Desktop/input/OUTPUT"
autoclear_output_directory = False    # True for debugging, set it to false for production (safety)



# The following configurations will be set when the fuzzer starts
# They are basically my global variables made available to all modules/functions
logfile_filepath = ""
logfile_filename = ""
tagging_filename = ""
output_dir_tagging_results_file = ""
status_result_filename = ""
output_dir_status_result_file = ""
output_dir = ""
output_dir_current_corpus = ""
output_dir_new_files = ""
output_dir_crashes = ""
output_dir_crashes_exception = ""
output_path_final_coverage_map_file = ""
output_path_previous_coverage_map_file = ""
adjustment_factor_code_snippet_corpus = 1
adjustment_factor_template_files_self_created_files = 1
adjustment_factor_template_files_injected_callbacks = 1
exec_engine = None
my_status_screen = None
skip_executions = False
fuzzer_arguments = None
perform_execution_func = lambda testcase_content, state: None
deterministically_preprocess_queue_func = lambda: None
corpus_js_snippets = None
corpus_template_files = None


# Some safety checks => TODO: Move into JS_Fuzzer or template corpus
if percent_of_templates_self_created > 1:
    print("Error, >cfg.percent_of_templates_self_created< must be below 1!")
    sys.exit(-1)
