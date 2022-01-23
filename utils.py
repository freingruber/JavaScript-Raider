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



# Some utilities which are used during fuzzing.

import random
import sys
import os
import shutil
import string
import difflib
import config as cfg
import hashlib


verbose_level = 0

# Every time I print a msg prefixed with "[-]", it indicates a problem occurred
# This variable counts how often this happens
# It's used in the status-update messages to show how often such problems occur
# to detect if something strange is going on with the fuzzer
# To analyze the problem, the log file can be opened (which contains the problem-related messages)
number_of_occurred_problems = 0

logfile = None


class bcolors:
    # https://godoc.org/github.com/whitedevops/colors#pkg-constants
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    RED = "\033[31m"
    MAGENTA = "\033[35m"
    ORANGE = "\033[33m"


# The fuzzer seed value is used to ensure that fuzzing runs are repeatable
# Typically I start fuzzing with a random seed. If I find after e.g. 5 minutes a
# crash, then I can extract the seed value from the fuzzer log and repeat the same
# fuzzing session to find the same bug again after 5 minutes (if the corpus or other files
# don't change in the meantime!)
# It also helps to analyse bugs which trigger just from time to time
def set_fuzzer_seed():
    my_seed = cfg.fuzzer_arguments.seed
    msg("[i] Setting seed value to: %d" % my_seed)
    random.seed(my_seed)


def set_verbose_level():
    global verbose_level
    verbose_level = cfg.fuzzer_arguments.verbose


# Red: new or changed
# Blue: Removed
# Green: Same
def get_colorized_diff_of_strings(old, new):
    result = ""
    codes = difflib.SequenceMatcher(a=old, b=new).get_opcodes()
    for code in codes:
        if code[0] == "equal": 
            result += bcolors.GREEN + old[code[1]:code[2]]
        elif code[0] == "delete":
            result += bcolors.BLUE + old[code[1]:code[2]]
        elif code[0] == "insert":
            result += bcolors.RED + new[code[3]:code[4]]
        elif code[0] == "replace":
            result += bcolors.BLUE + old[code[1]:code[2]] + bcolors.RED + new[code[3]:code[4]]
    return result + bcolors.ENDC


def print_diff_with_line_numbers(label, old_str, new_str):
    diff = get_colorized_diff_of_strings(old_str, new_str)
    diff_lines = diff.split("\n")
    tmp = ""
    idx = 0
    for line in diff_lines:
        tmp += "%02d: %s\n" % (idx, line)
        idx += 1
    msg("[i] %s:\n%s\n" % (label, tmp))


def enable_color_support():
    # Enables color support for output
    # On windows it must be enabled with the "color" command
    # On Linux it's working per default
    if os.name == 'nt':
        os.system('color') 


def get_random_seed():
    seed1 = os.urandom(128)
    
    random.seed(seed1)
    seed = random.randrange(sys.maxsize)
    random.seed(seed)
    return seed


def get_random_token_string(length):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))


def get_random_bool():
    return bool(random.getrandbits(1))


def get_random_int(min_value_inclusive, max_value_inclusive):
    if max_value_inclusive < min_value_inclusive:
        # for some strange reason my fuzzer creates such code
        # this would lead to an ValueError Exception
        if get_random_bool() is True:
            return min_value_inclusive
        else:
            return max_value_inclusive
    try:
        return random.randint(min_value_inclusive, max_value_inclusive)
    except:    # just to get sure the fuzzer keeps running
        if get_random_bool() is True:
            return min_value_inclusive
        else:
            return max_value_inclusive
    

def get_random_float(min_value_inclusive, max_value_inclusive):
    return random.uniform(min_value_inclusive, max_value_inclusive)


def get_random_float_as_str(min_value_inclusive, max_value_inclusive):
    return "%.20f" % get_random_float(min_value_inclusive, max_value_inclusive)


def get_random_entry(arg_list):
    if type(arg_list) == set:
        arg_list = list(arg_list)    # make it a list so that random.choice() works
    return random.choice(arg_list)


def calc_hash(content):
    # We can use MD5 here because it's not security related,
    # I'm using the hashes just to remove duplicates
    m = hashlib.md5()
    m.update(content.encode("utf-8"))
    sample_hash = str(m.hexdigest())
    return sample_hash


def check_outdir(outdir):
    if os.path.exists(outdir) and os.path.isdir(outdir):
        # Output dir exists
        if len(os.listdir(outdir)) != 0:
            # output directory is not empty
            outdir = os.path.abspath(outdir)
            
            clear_output_directory = False
            if cfg.autoclear_output_directory:
                clear_output_directory = True
            else:
                answer = input(bcolors.BLUE + "[?] Clear output directory (>%s<)? (yes|no)" % outdir + bcolors.ENDC)
                if answer.lower().strip() == "yes":
                    clear_output_directory = True
            if clear_output_directory is False:
                return False    # output dir is not empty and user doesn't want to clear it
            else:
                if outdir.lower().strip().startswith(cfg.output_directory_for_safecheck.lower()) is False:
                    perror("[-] STOPPING, SAFE CHECK (is >output_directory_for_safecheck< correctly configured in config.py?)")
                    
                # output dir should be cleared:
                for root, dirs, files in os.walk(outdir):
                    for f in files:
                        os.unlink(os.path.join(root, f))
                    for d in dirs:
                        shutil.rmtree(os.path.join(root, d))
        return True
    return False


def make_dir_if_not_exists(dir_path):
    if not os.path.exists(dir_path):
        os.makedirs(dir_path)


def print_code_with_line_numbers(code):
    line_number = 0
    for line in code.split("\n"):
        print("%03d: %s" % (line_number, line))
        line_number += 1


def likely(prob):
    val = random.random()
    if val <= prob:
        return True
    return False


def create_and_open_logfile():
    global logfile
    if cfg.fuzzer_arguments.developer_mode:
        return  # in developer mode I don't want a log file
    logfile = open(cfg.logfile_filepath, 'w')


def store_message_in_logfile(arg_msg):
    global logfile
    if logfile is not None:
        logfile.write(arg_msg + "\n")
        logfile.flush()


def perror(arg_msg):
    print(bcolors.RED + bcolors.BOLD + arg_msg + bcolors.ENDC)
    store_message_in_logfile(arg_msg)
    sys.exit(-1)
    

def dbg_msg(arg_msg):
    if verbose_level >= 1:
        text = "DEBUG: " + arg_msg
        print(bcolors.GREEN + text + bcolors.ENDC)
        store_message_in_logfile(text)


def msg(arg_msg, dump_message_to_logfile=True):
    global number_of_occurred_problems
    if arg_msg.startswith("[+]"):
        print(bcolors.GREEN + arg_msg + bcolors.ENDC)
    elif arg_msg.startswith("[-]"):
        number_of_occurred_problems += 1
        print(bcolors.RED + arg_msg + bcolors.ENDC)
    elif arg_msg.startswith("[i]"):
        print(bcolors.MAGENTA + arg_msg + bcolors.ENDC)
    elif arg_msg.startswith("[!]"):
        print(bcolors.ORANGE + arg_msg + bcolors.ENDC)
    else:
        print(bcolors.ENDC + arg_msg + bcolors.ENDC)
    if dump_message_to_logfile:
        store_message_in_logfile(arg_msg)


# Writes a message and exists the program with return value 0x00
def exit_and_msg(arg_msg, dump_message_to_logfile=True):
    msg(arg_msg, dump_message_to_logfile)
    sys.exit(0)


def covert_runtime_to_string(runtime_in_total_seconds):
    runtime_days = divmod(runtime_in_total_seconds, 86400)
    runtime_hours = divmod(runtime_days[1], 3600)
    runtime_minutes = divmod(runtime_hours[1], 60)
    runtime_seconds = divmod(runtime_minutes[1], 1)
    
    days = runtime_days[0]
    hours = runtime_hours[0]
    minutes = runtime_minutes[0]
    seconds = runtime_seconds[0]

    if days != 0:
        runtime_str = "%d days %d hours %d minutes %d seconds" % (days, hours, minutes, seconds)
    elif hours != 0:
        runtime_str = "%d hours %d minutes %d seconds" % (hours, minutes, seconds)
    elif minutes != 0:
        runtime_str = "%d minutes %d seconds" % (minutes, seconds)
    elif seconds != 0:
        runtime_str = "%d seconds" % seconds
    else:
        runtime_str = "now (0 seconds ago)"
    return runtime_str
    

# Passing a corpus dir path to this function, it will return
# the highest used testcase number
# This can be used in a loop which should iterate from tc1.js to tc<maxId>.js
def get_last_testcase_number(folder_path):
    highest_id = 0
    for filename in os.listdir(folder_path):
        if filename.startswith("tc") and "state" not in filename and "pickle" not in filename and "required_coverage" not in filename:
            testcase_id = int(filename[2:-3], 10)     # 2: to remove "tc" and -3 to remove ".js"
            if testcase_id > highest_id:
                highest_id = testcase_id
    return highest_id


# TODO: This function is old and must be updated
# Can I maybe store all variables from config and arguments via a single code line?
def dump_fuzzer_arguments_and_configuration():
    if cfg.fuzzer_arguments.developer_mode:
        return  # in developer mode I don't want to dump the fuzzer configuration

    msg("[i] Going to dump fuzzer arguments and configuration...")
    msg("[i] " + "="*41 + " Fuzzer arguments: " + "="*41)
    msg("[i] " + "-"*101)
    msg("[i] Seed: %d" % cfg.fuzzer_arguments.seed)
    msg("[i] Verbosity level: %d" % cfg.fuzzer_arguments.verbose)
    msg("[i] Input/output directory JavaScript corpus: %s" % cfg.fuzzer_arguments.corpus_js_files_dir)
    msg("[i] Input/output directory template corpus: %s" % cfg.fuzzer_arguments.corpus_template_files_dir)
    msg("[i] Output/Working directory: %s" % cfg.fuzzer_arguments.output_dir)
    msg("[i] Recalculate globals: %s" % cfg.fuzzer_arguments.recalculate_globals)
    msg("[i] Resume: %s" % cfg.fuzzer_arguments.resume)
    msg("[i] Import Corpus: %s" % cfg.fuzzer_arguments.import_corpus_mode)
    if cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id is None:
        msg("[i] Deterministic preprocessing mode start with testcase ID: -")
    else:
        msg("[i] Deterministic preprocessing mode start with testcase ID: %d" % cfg.fuzzer_arguments.deterministic_preprocessing_mode_start_tc_id)
    msg("[i] " + "-"*101)
    msg("[i] ")    # empty line

    # Only the "important" configuration is dumped here
    msg("[i] " + "="*39 + " Fuzzer configuration: " + "="*39)
    msg("[i] " + "-"*101)
    msg("[i] v8_path_with_coverage: %s" % cfg.v8_path_with_coverage)
    msg("[i] v8_path_without_coverage: %s" % cfg.v8_path_without_coverage)
    msg("[i] v8_path_debug_without_coverage: %s" % cfg.v8_path_debug_without_coverage)
    msg("[i] v8_shm_id: %d" % cfg.v8_shm_id)
    msg("[i] tagging_enabled: %s" % cfg.tagging_enabled)
    msg("[i] v8_restart_engine_after_executions: %d" % cfg.v8_restart_engine_after_executions)
    msg("[i] v8_default_timeout_multiplication_factor: %d" % cfg.v8_default_timeout_multiplication_factor)
    msg("[i] v8_timeout_per_execution_in_ms_min: %d" % cfg.v8_timeout_per_execution_in_ms_min)
    msg("[i] v8_timeout_per_execution_in_ms_max: %d" % cfg.v8_timeout_per_execution_in_ms_max)
    msg("[i] max_runtime_of_input_file_in_ms: %d" % cfg.max_runtime_of_input_file_in_ms)
    msg("[i] status_update_after_x_executions: %d" % cfg.status_update_after_x_executions)
    msg("[i] dump_tags_after_x_executions: %d" % cfg.dump_tags_after_x_executions)
    msg("[i] testcases_to_combine_min: %d" % cfg.testcases_to_combine_min)
    msg("[i] testcases_to_combine_max: %d" % cfg.testcases_to_combine_max)
    msg("[i] number_mutations_min: %d" % cfg.number_mutations_min)
    msg("[i] number_mutations_max: %d" % cfg.number_mutations_max)
    msg("[i] number_late_mutations_min: %d" % cfg.number_late_mutations_min)
    msg("[i] number_late_mutations_max: %d" % cfg.number_late_mutations_max)
    msg("[i] percent_of_templates_self_created: %.2f %%" % (cfg.percent_of_templates_self_created * 100))
    msg("[i] templates_enabled: %s" % cfg.templates_enabled)
    msg("[i] templates_to_combine_min: %d" % cfg.templates_to_combine_min)
    msg("[i] templates_to_combine_max: %d" % cfg.templates_to_combine_max)
    msg("[i] testcases_to_combine_for_insertion_point_in_template_min: %d" % cfg.testcases_to_combine_for_insertion_point_in_template_min)
    msg("[i] testcases_to_combine_for_insertion_point_in_template_max: %d" % cfg.testcases_to_combine_for_insertion_point_in_template_max)
    msg("[i] template_files_how_many_inmemory_files: %d" % cfg.template_files_how_many_inmemory_files)
    msg("[i] template_files_after_how_many_executions_reload_inmemory_files: %d" % cfg.template_files_after_how_many_executions_reload_inmemory_files)
    msg("[i] " + "-"*101)
    msg("[i] ")    # empty line


def check_if_system_is_prepared_for_fuzzing():
    # This is a small hack, I could check all configurations but I just check if ASLR is turned off
    with open("/proc/sys/kernel/randomize_va_space", "r") as fobj:
        content = fobj.read()
    if content.strip() != "0":
        perror("[-] It seems like the system was not prepared for fuzzing yet. Please execute the >prepare_system_for_fuzzing.sh< script.")


# This function stores a crash in the output directory.
# If the exec engine also executed other testcases since the last engine restart,
# the other testcases will also be stored.
def store_testcase_with_crash(content):
    (new_filename, new_filepath) = store_testcase_in_directory(content, cfg.output_dir_crashes)

    # Also store previously executed testcases (in case the crash is not reproducible)
    # maybe the previously executed testcases together with the current crash file lead to a crash
    previous_testcases = cfg.exec_engine.get_testcases_since_last_engine_restart()
    if len(previous_testcases) != 0:
        sample_hash = calc_hash(content)
        foldername = sample_hash + "_previous"
        fullpath = os.path.join(cfg.output_dir_crashes, foldername)
        os.mkdir(fullpath)
        current_id = 0
        for entry in previous_testcases:
            current_id += 1
            filename = "%d.js" % current_id
            fullpath_file = os.path.join(fullpath, filename)
            with open(fullpath_file, "w") as fobj:
                fobj.write(entry)
    return new_filename, new_filepath



def store_testcase_with_crash_exception(content):
    (new_filename, new_filepath) = store_testcase_in_directory(content, cfg.output_dir_crashes_exception)

    # Also store previously executed testcases (in case the crash is not reproducible)
    # maybe the previously executed testcases together with the current crash file lead to a crash
    previous_testcases = cfg.exec_engine.get_testcases_since_last_engine_restart()
    if len(previous_testcases) != 0:
        sample_hash = calc_hash(content)
        foldername = sample_hash + "_previous"
        fullpath = os.path.join(cfg.output_dir_crashes_exception, foldername)
        os.mkdir(fullpath)
        current_id = 0
        for entry in previous_testcases:
            current_id += 1
            filename = "%d.js" % current_id
            fullpath_file = os.path.join(fullpath, filename)
            with open(fullpath_file, "w") as fobj:
                fobj.write(entry)
    return new_filename, new_filepath


def remove_all_from_list(the_list, the_entry_to_remove):
    try:
        while True:
            the_list.remove(the_entry_to_remove)
    except ValueError:
        pass


def store_testcase_in_directory(content, directory):
    sample_hash = calc_hash(content)
    filename = sample_hash + ".js"

    fullpath = os.path.join(directory, filename)
    with open(fullpath, "w") as fobj:
        fobj.write(content)
    return filename, fullpath