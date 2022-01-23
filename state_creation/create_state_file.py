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



# This script is used to calculate state-files (it extracts all kind of information from a testcase)
#
# Note: It would make sense to dynamically extract the information using a not instrumented d8 binary.
# During (initial) corpus generation I did this. However, during fuzzing I'm using an instrumented d8 binary.
# I could kill the current d8 process, start an not instrumented d8 binary and calculate the state-file
# and then start the instrumented engine again to continue fuzzing.
#
# However, currently the code can't stop one engine and start another one.
# I think this is because the code uses global variables and therefore it can't be used for two d8 processes.
# TODO: When I have time I will fix the code and implement this.
#
# For the moment it should work fine because the corpus is already big which means new state files will not
# frequently be calculated which means it doesn't matter if it's fast or not (hopefully).
#


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import re
import testcase_state
import config as cfg
import utils
from native_code.executor import Executor, Execution_Status
import traceback
from datetime import datetime
import javascript.js_helpers as js_helpers


def create_state_file_safe(code):
    try:
        state = create_state_file(code, silently_catch_exception=False)
    except:
        # There was an exception during creation of .state file; e.g.: an extracted value like the length of an array
        # was not in the output. I therefore restart .state creation
        # It's unlikely that this will occur again (it was maybe just a read/write error), however, if it occurs again,
        # I silently catch the exception and just skip filling this one .state field
        # (which means the .state file would not be correct, but this should nearly never happen).
        # I think the event that extraction of a field doesn't work (e.g.: output contains just partial data) is very unlikely
        # because the output channels are flushed. However, it still occurred 2-3 times while creating the state of over 15 000 corpus files
        # Instead of directly silently catching it, I restart .state creation and try it a second time. If it occurs two times in a row, I
        # just silently skip setting the field.
        # TODO: Maybe analyze in the future what causes this problem?
        utils.msg("[-] Python Exception during state file creation, going to retry and silently catch exception...")
        traceback.print_exc()
        state = create_state_file(code, silently_catch_exception=True)
    return state


# Hint: Don't call this function directly, instead call create_state_file_safe()
def create_state_file(code, silently_catch_exception):
    utils.msg("[i] Start creation of state file...")

    cfg.exec_engine.restart_engine()  # start every testcase with a new engine

    code = code.rstrip()  # remove possible newlines at the end. Otherwise it would count too many lines for the testcase

    fuzzcommand_str = "%s('%s'" % (cfg.v8_fuzzcommand, cfg.v8_print_command)
    fuzzcommand_str_commented = "//" + fuzzcommand_str
    if fuzzcommand_str in code:
        code = code.replace(fuzzcommand_str, fuzzcommand_str_commented)

    number_functions = js_helpers.get_number_functions_all(code)
    number_variables = js_helpers.get_number_variables_all(code)
    number_classes = js_helpers.get_number_classes_all(code)
    # utils.dbg_msg("number_functions: %d" % number_functions)
    # utils.dbg_msg("number_variables: %d" % number_variables)
    # utils.dbg_msg("number_classes: %d" % number_classes)

    state = testcase_state.Testcase_State(number_variables, number_functions, number_classes)

    code_lines = code.split("\n")
    number_of_lines = len(code_lines)

    state.testcase_size = len(code)
    state.testcase_number_of_lines = number_of_lines

    state.function_arguments = extract_function_arguments(code, number_functions)
    (state.number_total_triggered_edges, state.runtime_length_in_ms, state.unreliable_score) = extract_triggered_edges(code)

    does_try_finally_work = check_if_try_finally_works(code)

    # print("Before: extract_code_lines_where_code_can_be_inserted() %s" % datetime.now().strftime("%H:%M:%S"))
    result = extract_code_lines_where_code_can_be_inserted(number_of_lines, code_lines, does_try_finally_work, silently_catch_exception)

    (state.lines_where_code_can_be_inserted,
     state.lines_where_code_with_coma_can_be_inserted,
     state.lines_where_code_with_start_coma_can_be_inserted,
     state.lines_which_are_executed_at_least_one_thousand_times,
     state.lines_where_inserted_code_leads_to_timeout,
     state.lines_where_inserted_code_leads_to_exception,
     state.lines_which_are_not_executed) = result

    # print("Before: get_variable_types_in_line() %s" % datetime.now().strftime("%H:%M:%S"))
    for line_number in state.lines_where_code_can_be_inserted:
        # print("Line: %d" % line_number)
        variable_types = get_variable_types_in_line(code, code_lines, line_number, number_of_lines, number_variables, does_try_finally_work, silently_catch_exception, "",
                                                    ";")
        for entry in variable_types:
            (variable_name, variable_type) = entry
            # print("\tVariable: %s => %s" % (variable_name, variable_type))
            state.add_variable_type(variable_name, line_number, variable_type)
    for line_number in state.lines_where_code_with_coma_can_be_inserted:
        variable_types = get_variable_types_in_line(code, code_lines, line_number, number_of_lines, number_variables, does_try_finally_work, silently_catch_exception, "",
                                                    ",")
        for entry in variable_types:
            (variable_name, variable_type) = entry
            state.add_variable_type(variable_name, line_number, variable_type)
    for line_number in state.lines_where_code_with_start_coma_can_be_inserted:
        variable_types = get_variable_types_in_line(code, code_lines, line_number, number_of_lines, number_variables, does_try_finally_work, silently_catch_exception,
                                                    ",", "")
        for entry in variable_types:
            (variable_name, variable_type) = entry
            state.add_variable_type(variable_name, line_number, variable_type)

    mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted = dict()

    # print("Before: add_array_length() %s" % datetime.now().strftime("%H:%M:%S"))

    # And now extract the length of arrays at the identified locations:
    for variable_name in state.variable_types:
        for entry in state.variable_types[variable_name]:
            (line_number, variable_type) = entry
            if "array" in variable_type and variable_type != "arraybuffer" and variable_type != "sharedarraybuffer":
                # arraybuffer and sharedarraybuffer have as property ".byteLength" and not ".length"
                # => but I currently don't see an advantage in extracting it because the fuzzer can currently not handle this information
                # The same applies for "DataView" and .byteLength
                # And for the ".size" properties of a set, weakset, map and weakmap
                # => Therefore I currently don't extract this information

                line_start_character = ""
                line_end_character = ""
                if line_number in state.lines_where_code_can_be_inserted:
                    line_start_character = ""
                    line_end_character = ";"
                elif line_number in state.lines_where_code_with_coma_can_be_inserted:
                    line_start_character = ""
                    line_end_character = ","
                elif line_number in state.lines_where_code_with_start_coma_can_be_inserted:
                    line_start_character = ","
                    line_end_character = ""
                else:
                    utils.perror("State file creation: unkown line type2 - should never occur!")
                array_length = get_array_length_in_line(code_lines, line_number, number_of_lines, variable_name, does_try_finally_work, silently_catch_exception,
                                                        line_start_character, line_end_character)
                state.add_array_length(variable_name, line_number, array_length)
                max_value = 0
                for entry_array_length in array_length:
                    if entry_array_length > max_value:
                        max_value = entry_array_length

                array_items_to_extract = []
                if max_value == 0:
                    continue  # nothing to extract
                elif max_value <= 10:
                    for i in range(0, max_value):
                        array_items_to_extract.append("%s[%d]" % (variable_name, i))
                else:
                    # Extraction of all entries would take too long, so focus on just some
                    for i in range(0, 3 + 1):
                        array_items_to_extract.append("%s[%d]" % (variable_name, i))  # the first

                    array_items_to_extract.append("%s[%d]" % (variable_name, max_value - 1))  # last
                    try:
                        occurrences = re.findall(r'%s\[[\d]+\]' % re.escape(variable_name), code)       # TODO: Is this regex pattern correct? PyCharm says no?
                    except:
                        occurrences = []
                    if len(occurrences) <= 8:
                        for entry2 in occurrences:
                            array_items_to_extract.append(entry2)
                    elif len(occurrences) > 8:
                        for i in range(0, 8):
                            entry2 = utils.get_random_entry(occurrences)
                            array_items_to_extract.append(entry2)

                array_items_to_extract = list(set(array_items_to_extract))  # remove duplicates
                if line_number not in mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted:
                    mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted[line_number] = []

                mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted[line_number] += array_items_to_extract

    # Extract all used properties in testcase:
    properties_to_extract = set()
    for variable_name in state.variable_types:
        try:
            occurrences = re.findall(r'%s\.[_\da-zA-z\(]+' % re.escape(variable_name), code)        # TODO: Is this regex pattern correct? PyCharm says no?
        except:
            occurrences = []
        for occurrence in occurrences:
            if "(" in occurrence:
                # small hack, I want to skip function calls, therefore I added "(" in the above pattern and
                # if it contains "(" then I just skip it
                # note: that doesn't catch code like var_1_.function (args)
                # because of the space , but I don't think that's common code, so it's ok to not handle this case (same for newlines..)
                continue
            properties_to_extract.add(occurrence)
    for line_number in range(number_of_lines):
        if line_number not in mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted:
            mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted[line_number] = []
        mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted[line_number] += list(properties_to_extract)

    # print("Before: get_data_types_of_array_items_and_properties() %s" % datetime.now().strftime("%H:%M:%S"))
    # Now extract data type of array items / properties
    state = get_data_types_of_array_items_and_properties(code, code_lines, number_of_lines, mapping_line_number_to_available_tokens_for_which_datatype_must_be_extracted,
                                                         does_try_finally_work, silently_catch_exception, state)

    # print("Before: 2nd get_array_length_in_line() %s" % datetime.now().strftime("%H:%M:%S"))
    # Extract array lengths again:
    # If an array item or property stores an array, then I must extract the array length again
    # Note: I'm not going in-depth and extracting all array items again, I just extract the length
    for variable_name in state.array_items_or_properties:
        for entry in state.array_items_or_properties[variable_name]:
            (line_number, variable_type) = entry
            if "array" in variable_type and variable_type != "arraybuffer" and variable_type != "sharedarraybuffer":
                if line_number in state.lines_where_code_can_be_inserted:
                    line_start_character = ""
                    line_end_character = ";"
                elif line_number in state.lines_where_code_with_coma_can_be_inserted:
                    line_start_character = ""
                    line_end_character = ","
                elif line_number in state.lines_where_code_with_start_coma_can_be_inserted:
                    line_start_character = ","
                    line_end_character = ""
                else:
                    utils.perror("State file creation: unkown line type3 - should never occur!")
                array_length = get_array_length_in_line(code_lines, line_number, number_of_lines, variable_name, does_try_finally_work, silently_catch_exception,
                                                        line_start_character, line_end_character)
                state.add_array_length(variable_name, line_number, array_length)

    # TODO: Data type of function arguments?

    state.recalculate_unused_variables(code)

    # print("Before: calculate_curly_bracket_offsets() %s" % datetime.now().strftime("%H:%M:%S"))
    # Extract the blocks in the testcase
    state.calculate_curly_bracket_offsets(code)

    # utils.dbg_msg("Code:")
    # utils.dbg_msg(code)
    # utils.dbg_msg("------------------------------\n\n")
    # utils.dbg_msg(state)

    utils.msg("[i] Finished creation of state file")
    return state


def extract_function_arguments(code, number_functions):
    function_arguments = dict()
    for idx in range(1, number_functions+1):
        code_tmp = code.replace("\t", " ").replace("\n", " ")   # reset in every iteration
        func_name = "func_%d_" % idx
        for function_decl in ["function ", "function* "]:
            grep_substring = function_decl + func_name
            if grep_substring not in code_tmp:
                continue
            idx = code_tmp.index(grep_substring)
            sub_part = code_tmp[idx + len(grep_substring):]
            if "(" not in sub_part or ")" not in sub_part:
                continue
            idx_1 = sub_part.index("(")
            sub_part = sub_part[idx_1 + 1:]
            idx_2 = sub_part.index(")")
            function_arguments_str = sub_part[:idx_2].strip()
            # utils.dbg_msg("Function arguments are: %s" % function_arguments_str)
            test = function_arguments_str.replace(" ", "").replace("\t", "")
            if test == "":
                number_function_arguments = 0
            else:
                number_function_arguments = len(function_arguments_str.split(","))
            # utils.dbg_msg("Function %s expects %d arguments" % (func_name, number_function_arguments))
            function_arguments[func_name] = number_function_arguments
            break
    return function_arguments


def check_if_try_finally_works(code):
    # Checks code like:
    # var foobar; function foobar() {}

    # This code doesn't throw an exception but inside a try catch block it does:
    # try {
    # var foobar; function foobar() {}
    # }
    # finally {}
    
    # => In this case I must avoid the use of try-finally.
    # However, per default I'm using it. This function detects if I can use it.

    prefix = "try {\n"
    suffix = """
}
finally {
    """+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', 'TESTER');
}"""

    final_code = prefix + code + suffix
    result = cfg.exec_engine.execute_once(final_code, is_query=True)
    if result.status == Execution_Status.SUCCESS:
        if "TESTER" in result.output:
            return True
        else:
            utils.msg("[-] State file creation: check_if_try_finally_works() output is not correct!")
            return False
    elif result.status == Execution_Status.EXCEPTION_THROWN:
        utils.msg("[-] State file creation: check_if_try_finally_works() - Try Finally does not work")
        return False
    else:
        utils.msg("[-] State file creation: check_if_try_finally_works() Unkown status returned!\n%s" % str(result))
        return False


def extract_code_lines_where_code_can_be_inserted(number_of_lines, code_lines, does_try_finally_work, silently_catch_exception):
    # Now extract at which lines code can be inserted
    lines_where_code_can_be_inserted = []
    lines_where_code_with_coma_can_be_inserted = []
    lines_which_are_executed_at_least_one_thousand_times = []
    lines_where_inserted_code_leads_to_timeout = []
    lines_where_inserted_code_leads_to_exception = []
    lines_which_are_not_executed = []
    lines_where_code_with_start_coma_can_be_inserted = []

    line_numbers_to_check = []
    fuzzcommand_str = "%s('%s'" % (cfg.v8_fuzzcommand, cfg.v8_print_command)
    for line_number in range(number_of_lines):
        if fuzzcommand_str in code_lines[line_number]:
            line_numbers_to_check.append(line_number)
    
    if len(line_numbers_to_check) == 0:
        # not a template file, so check every possible code line
        line_numbers_to_check = range(number_of_lines+1)
    else:
        # it's a template file, so also add 0 and the last line for an append operation
        if 0 not in line_numbers_to_check:
            line_numbers_to_check.insert(0, 0)  # first line => add stuff in front of the testcase
        line_numbers_to_check.append(number_of_lines)      # => last line to append stuff after the template

    for line_number in line_numbers_to_check:
        tmp = ""
        # Add the code before the code line
        for idx in range(line_number):
            tmp += code_lines[idx] + "\n"
        
        # Now add the new codeline + newline
        tmp += "line_count += 1;\n"

        # And now add all the other code lines:
        for idx in range(line_number, number_of_lines):
            tmp += code_lines[idx] + "\n"

        if does_try_finally_work:
            prefix = "try {\nvar line_count = 0;\n"
            suffix = """
}
finally {
    """+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+line_count);
}"""
        else:
            prefix = "var line_count = 0;\n"
            suffix = """
"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+line_count);
"""
        
        final_code = prefix + tmp + suffix

        # utils.dbg_msg("Attempting line %d" % line_number)
        # utils.dbg_msg(final_code)
        # utils.dbg_msg("------------------\n")
        result = cfg.exec_engine.execute_once(final_code, is_query=True)
        if result.status == Execution_Status.TIMEOUT:
            # utils.dbg_msg("Line: %d resulted in a timeout" % line_number)
            lines_where_inserted_code_leads_to_timeout.append(line_number)
        elif result.status == Execution_Status.EXCEPTION_THROWN:
            # utils.dbg_msg("Line: %d resulted in an exception" % line_number)
            # In case of an exception I can still try to end the code with a "," instead
            final_code = final_code.replace("line_count += 1;", "line_count += 1,")
            # utils.dbg_msg(final_code)
            result = cfg.exec_engine.execute_once(final_code, is_query=True)
            if result.status == Execution_Status.EXCEPTION_THROWN:
                # utils.dbg_msg("Line: %d coma separated resulted in an exception" % line_number)
                
                # "," at the end also doesn't work, now try it with "," at the start
                final_code = final_code.replace("line_count += 1,", ",line_count += 1")
                result = cfg.exec_engine.execute_once(final_code, is_query=True)
                # print("Result:")
                # print(result)
                if result.status == Execution_Status.EXCEPTION_THROWN:
                    # it's really not possible to add code in this line, so mark it:
                    lines_where_inserted_code_leads_to_exception.append(line_number)
                elif result.status == Execution_Status.TIMEOUT:
                    lines_where_inserted_code_leads_to_timeout.append(line_number)
                elif result.status == Execution_Status.SUCCESS:
                    out = result.output.replace(cfg.v8_temp_print_id, "").replace(cfg.v8_print_id_not_printed, "").strip()
                    if silently_catch_exception:
                        try:
                            # number_of_line_executions = int(out, 10)
                            for entry in out.split("\n"):
                                if entry.startswith("OUT:"):
                                    number_of_line_executions = int(entry[len("OUT:"):], 10) 
                        except:
                            number_of_line_executions = 0
                    else:
                        # number_of_line_executions = int(out, 10)
                        # could lead to an exception
                        for entry in out.split("\n"):
                            if entry.startswith("OUT:"):
                                number_of_line_executions = int(entry[len("OUT:"):], 10) 

                    lines_where_code_with_start_coma_can_be_inserted.append(line_number)
                    if number_of_line_executions == 0:
                        lines_which_are_not_executed.append(line_number)
                    elif number_of_line_executions >= 1000:
                        lines_which_are_executed_at_least_one_thousand_times.append(line_number)

            elif result.status == Execution_Status.TIMEOUT:
                # utils.dbg_msg("Line: %d coma separated resulted in a timeout" % line_number)
                lines_where_inserted_code_leads_to_timeout.append(line_number)
            elif result.status == Execution_Status.SUCCESS:
                out = result.output.replace(cfg.v8_temp_print_id, "").replace(cfg.v8_print_id_not_printed, "").strip()
                if silently_catch_exception:
                    try:
                        # number_of_line_executions = int(out, 10)
                        for entry in out.split("\n"):
                            if entry.startswith("OUT:"):
                                number_of_line_executions = int(entry[len("OUT:"):], 10)
                    except:
                        number_of_line_executions = 0
                else:
                    # number_of_line_executions = int(out, 10)    # could lead to an exception
                    # could lead to an exception
                    for entry in out.split("\n"):
                        if entry.startswith("OUT:"):
                            number_of_line_executions = int(entry[len("OUT:"):], 10) 

                lines_where_code_with_coma_can_be_inserted.append(line_number)
                if number_of_line_executions == 0:
                    lines_which_are_not_executed.append(line_number)
                elif number_of_line_executions >= 1000:
                    lines_which_are_executed_at_least_one_thousand_times.append(line_number)
                # utils.dbg_msg("Line: %d coma separated executed %d times" % (line_number, number_of_line_executions))

        elif result.status == Execution_Status.SUCCESS:
            out = result.output.replace(cfg.v8_temp_print_id, "").replace(cfg.v8_print_id_not_printed, "").strip()
            if silently_catch_exception:
                try:
                    # number_of_line_executions = int(out, 10)
                    number_of_line_executions = 0
                    for entry in out.split("\n"):
                        if entry.startswith("OUT:"):
                            number_of_line_executions = int(entry[len("OUT:"):], 10) 
                except:
                    number_of_line_executions = 0
            else:
                # number_of_line_executions = int(out, 10) # could lead to an exception
                # could lead to an exception
                number_of_line_executions = 0
                for entry in out.split("\n"):
                    if entry.startswith("OUT:"):
                        number_of_line_executions = int(entry[len("OUT:"):], 10) 

            # utils.dbg_msg("Line: %d was executed %d times" % (line_number, number_of_line_executions))
            lines_where_code_can_be_inserted.append(line_number)
            if number_of_line_executions == 0:
                lines_which_are_not_executed.append(line_number)
            elif number_of_line_executions >= 1000:
                lines_which_are_executed_at_least_one_thousand_times.append(line_number)
    
    return lines_where_code_can_be_inserted, lines_where_code_with_coma_can_be_inserted, lines_where_code_with_start_coma_can_be_inserted, lines_which_are_executed_at_least_one_thousand_times, lines_where_inserted_code_leads_to_timeout, lines_where_inserted_code_leads_to_exception, lines_which_are_not_executed


def extract_triggered_edges(code):
    result = cfg.exec_engine.execute_safe(code)
    # TODO: I think during fuzzing this will always result in no new coverage , but currently I don't use the new edges field in the state
    # Later it could be used to improve the testcase selection during fuzzing
    # I would need to load an empty coverage map, then perform the execution and restore the coverage
    # => maybe I implement this later
    return result.num_edges, result.exec_time, result.unreliable_score


def get_array_length_in_line(code_lines, line_number, number_of_lines, variable_name, does_try_finally_work, silently_catch_exception,
                             line_start_character="", line_end_character=";"):
    ret = []

    if does_try_finally_work:
        prefix = """
let array_lengths = new Set();
try {
    function log_array_length(variable_name, real_variable) {
        array_lengths.add(variable_name + "=" + real_variable.length);
    }
"""

        suffix = """
}
finally {
	for (var it = array_lengths.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
}"""
    else:
        prefix = """
let array_lengths = new Set();
function log_array_length(variable_name, real_variable) {
    array_lengths.add(variable_name + "=" + real_variable.length);
}
"""

        suffix = """
	for (var it = array_lengths.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
"""
    tmp = ""
    # Add the code before the code line
    for idx in range(line_number):
        tmp += code_lines[idx] + "\n"
        
    # Now add the new codeline + newline
    logging_code = ""
    logging_code += ("try {log_array_length(\""+variable_name+"\","+variable_name+")} catch(e) {};")

    if line_start_character == "" and line_end_character == ";":
        pass    # it's already in correct format
    elif line_start_character == "" and line_end_character == ",":
        # In this context it's very likely not allowed to execute multiple commands
        # e.g. 
        # functionCall(1,
        # INJECTION_HERE
        # 3)
        # => in this case it's not possible to execute multiple dump-commands or even try-catch at all
        # I'm therefore using a "trick" and wrapping it inside an IIFE (immediately invoked function expression)
        logging_code = "(() => {%s})()," % logging_code
    elif line_start_character == "," and line_end_character == "":
        # Same as above
        logging_code = ",(() => {%s})()" % logging_code
    else:
        utils.perror("Logic flaw, unkown combination of input arguments: %s and %s" % (line_start_character, line_end_character))
    
    logging_code += "\n"
    tmp += logging_code

    # And now add all the other code lines:
    for idx in range(line_number, number_of_lines):
        tmp += code_lines[idx] + "\n"

    final_code = prefix + tmp + suffix
    # utils.dbg_msg("Testing line: %d" % line_number)
    # utils.dbg_msg(final_code)
    # utils.dbg_msg(tmp)
    result = cfg.exec_engine.execute_once(final_code, is_query=True)
    # utils.dbg_msg(result)
    if len(result.output) > 0:
        for entry in result.output.split("\n"):
            if entry.strip() == "":
                continue
            if entry.strip() == cfg.v8_temp_print_id or entry.strip() == cfg.v8_print_id_not_printed:
                continue
            if entry.startswith("OUT:") is False:
                continue
            if "=" not in entry or " " in entry:
                continue

            if silently_catch_exception:
                try:
                    x = entry.split("=")
                    variable_name = x[0][len("OUT:"):]
                    if x[1] == "undefined":
                        array_length = 0
                    else:
                        array_length = int(x[1], 10)
                    ret.append(array_length)
                except:
                    pass
            else:
                x = entry.split("=")
                variable_name = x[0][len("OUT:"):]
                if x[1] == "undefined":
                    array_length = 0
                else:
                    array_length = int(x[1], 10)
                ret.append(array_length)
    return ret
    

def get_data_types_of_array_items_and_properties(code, code_lines, number_of_lines, mapping_line_number_to_tokens, does_try_finally_work, silently_catch_exception, state):
    prefix = """
let variable_types = new Set();"""

    if does_try_finally_work:
        prefix += """
try {"""
    prefix += """
function log_variable(variable_name, real_variable) {
	variable_type = typeof real_variable;
	//print(variable_type);
	if(variable_type == "string" || real_variable instanceof String) {
		variable_types.add(variable_name + "=string");
	} else if(variable_type == "object") {
		// Resolve it more precise
		if(Array.isArray(real_variable) || real_variable instanceof Array) {
			variable_types.add(variable_name + "=array");
        } else if(typeof real_variable == "function") {
            variable_types.add(variable_name + "=function");	
		} else if(real_variable instanceof Int8Array) {
			variable_types.add(variable_name + "=int8array");	
		} else if(real_variable instanceof Uint8Array) {
			variable_types.add(variable_name + "=uint8array");	
		} else if(real_variable instanceof Uint8ClampedArray) {
			variable_types.add(variable_name + "=uint8clampedarray");	
		} else if(real_variable instanceof Int16Array) {
			variable_types.add(variable_name + "=int16array");	
		} else if(real_variable instanceof Uint16Array) {
			variable_types.add(variable_name + "=uint16array");	
		} else if(real_variable instanceof Int32Array) {
			variable_types.add(variable_name + "=int32array");	
		} else if(real_variable instanceof Uint32Array) {
			variable_types.add(variable_name + "=uint32array");	
		} else if(real_variable instanceof Float32Array) {
			variable_types.add(variable_name + "=float32array");	
		} else if(real_variable instanceof Float64Array) {
			variable_types.add(variable_name + "=float64array");	
		} else if(real_variable instanceof BigInt64Array) {
			variable_types.add(variable_name + "=bigint64array");	
		} else if(real_variable instanceof BigUint64Array) {
			variable_types.add(variable_name + "=biguint64array");
		} else if(real_variable instanceof Set) {
			variable_types.add(variable_name + "=set");
		} else if(real_variable instanceof WeakSet) {
			variable_types.add(variable_name + "=weakset");
		} else if(real_variable instanceof Map) {
			variable_types.add(variable_name + "=map");
		} else if(real_variable instanceof WeakMap) {
			variable_types.add(variable_name + "=weakmap");
		} else if(real_variable instanceof RegExp) {
			variable_types.add(variable_name + "=regexp");
		} else if(real_variable instanceof ArrayBuffer) {
			variable_types.add(variable_name + "=arraybuffer");
		} else if(real_variable instanceof SharedArrayBuffer) {
			variable_types.add(variable_name + "=sharedarraybuffer");	
		} else if(real_variable instanceof DataView) {
			variable_types.add(variable_name + "=dataview");
		} else if(real_variable instanceof Promise) {
			variable_types.add(variable_name + "=promise");
		} else if(real_variable instanceof Intl.Collator) {
			variable_types.add(variable_name + "=intl.collator");
		} else if(real_variable instanceof Intl.DateTimeFormat) {
			variable_types.add(variable_name + "=intl.datetimeformat");	
		} else if(real_variable instanceof Intl.ListFormat) {
			variable_types.add(variable_name + "=intl.listformat");	
		} else if(real_variable instanceof Intl.NumberFormat) {
			variable_types.add(variable_name + "=intl.numberformat");	
		} else if(real_variable instanceof Intl.PluralRules) {
			variable_types.add(variable_name + "=intl.pluralrules");	
		} else if(real_variable instanceof Intl.RelativeTimeFormat) {
			variable_types.add(variable_name + "=intl.relativetimeformat");	
		} else if(real_variable instanceof Intl.Locale) {
			variable_types.add(variable_name + "=intl.locale");	
		} else if(real_variable instanceof WebAssembly.Module) {
			variable_types.add(variable_name + "=webassembly.module");	
		} else if(real_variable instanceof WebAssembly.Instance) {
			variable_types.add(variable_name + "=webassembly.instance");	
		} else if(real_variable instanceof WebAssembly.Memory) {
			variable_types.add(variable_name + "=webassembly.memory");	
		} else if(real_variable instanceof WebAssembly.Table) {
			variable_types.add(variable_name + "=webassembly.table");	
		} else if(real_variable instanceof WebAssembly.CompileError) {
			variable_types.add(variable_name + "=webassembly.compileerror");	
		} else if(real_variable instanceof WebAssembly.LinkError) {
			variable_types.add(variable_name + "=webassembly.linkerror");	
		} else if(real_variable instanceof WebAssembly.RuntimeError) {
			variable_types.add(variable_name + "=webassembly.runtimeerror");		
		} else if(real_variable instanceof URIError) {
			variable_types.add(variable_name + "=urierror");	
		} else if(real_variable instanceof TypeError) {
			variable_types.add(variable_name + "=typeerror");	
		} else if(real_variable instanceof SyntaxError) {
			variable_types.add(variable_name + "=syntaxerror");		
		} else if(real_variable instanceof RangeError) {
			variable_types.add(variable_name + "=rangeerror");	
		} else if(real_variable instanceof EvalError) {
			variable_types.add(variable_name + "=evalerror");		
		} else if(real_variable instanceof ReferenceError) {
			variable_types.add(variable_name + "=referenceerror");	
		} else if(real_variable instanceof Error) {
			variable_types.add(variable_name + "=error");
		} else if(real_variable instanceof Date) {
			variable_types.add(variable_name + "=date");
		} else if(real_variable === null) {
			variable_types.add(variable_name + "=null");
		} else if(real_variable === Math) {
			variable_types.add(variable_name + "=math");
		} else if(real_variable === JSON) {
			variable_types.add(variable_name + "=json");
		} else if(real_variable === Reflect) {
			variable_types.add(variable_name + "=reflect");
		} else if(real_variable === globalThis) {
			variable_types.add(variable_name + "=globalThis");		
		} else if(real_variable === Atomics) {
			variable_types.add(variable_name + "=atomics");
		} else if(real_variable === Intl) {
			variable_types.add(variable_name + "=intl");
		} else if(real_variable === WebAssembly) {
			variable_types.add(variable_name + "=webassembly");	
		} else if(real_variable.constructor === Object) {
			variable_types.add(variable_name + "=object1");
		} else if(real_variable instanceof Object) {
			variable_types.add(variable_name + "=object2");		// some object which I currently don't have implemented...	
			// maybe access it via: Object.prototype.toString.call(real_variable);
		} else {
			variable_types.add(variable_name + "=unkown_object");
		}
	} else if(variable_type == "number") {
		if(isFinite(real_variable)) {
			variable_types.add(variable_name + "=real_number");
		} else {
			variable_types.add(variable_name + "=special_number");	// e.g. NaN or Infinity
		}
	} else {
		// e.g.: "function", "boolean", 'symbol', "undefined", "bigint"
		variable_types.add(variable_name + "=" + variable_type);
	}
}
"""

    if does_try_finally_work:
        suffix = """
}
finally {
	for (var it = variable_types.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
}"""
    else:
        suffix = """
	for (var it = variable_types.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
"""
    
    for line_number in range(number_of_lines):
        tokens = mapping_line_number_to_tokens[line_number]
        if len(tokens) == 0:
            continue
        if line_number in state.lines_where_inserted_code_leads_to_timeout or line_number in state.lines_where_inserted_code_leads_to_exception:
            continue

        tmp = ""
        # Add the code before the code line
        for idx in range(line_number):
            tmp += code_lines[idx] + "\n"
        
        logging_code = ""
        # Now add the new codeline + newline
        for variable_name in tokens:
            # print("LINE: %d extracting token: %s" % (line_number, variable_name))
            logging_code += ("try {log_variable(\"%s\",%s)} catch(e) {};" % (variable_name, variable_name))

        if line_number in state.lines_where_code_can_be_inserted:
            line_start_character = ""
            line_end_character = ";"
        elif line_number in state.lines_where_code_with_coma_can_be_inserted:
            line_start_character = ""
            line_end_character = ","
        elif line_number in state.lines_where_code_with_start_coma_can_be_inserted:
            line_start_character = ","
            line_end_character = ""
        else:
            print("Line: %d" % line_number)
            utils.perror("State file creation: unkown line type1 - should never occur!")

        if line_start_character == "" and line_end_character == ";":
            pass    # it's already in correct format
        elif line_start_character == "" and line_end_character == ",":
            # In this context it's very likely not allowed to execute multiple commands
            # e.g. 
            # functionCall(1,
            # INJECTION_HERE
            # 3)
            # => in this case it's not possible to execute multiple dump-commands or even try-catch at all
            # I'm therefore using a "trick" and wrapping it inside an IIFE (immediately invoked function expression)
            logging_code = "(() => {%s})()," % logging_code
        elif line_start_character == "," and line_end_character == "":
            # Same as above
            logging_code = ",(() => {%s})()" % logging_code
        else:
            utils.perror("Logic flaw, unkown combination of input arguments: %s and %s" % (line_start_character, line_end_character))
    
        logging_code += "\n"

        tmp += logging_code

        # And now add all the other code lines:
        for idx in range(line_number, number_of_lines):
            tmp += code_lines[idx] + "\n"

        final_code = prefix + tmp + suffix
        # utils.msg("Testing line: %d" % line_number)
        # print(final_code)
        # print("------------")
        result = cfg.exec_engine.execute_once(final_code, is_query=True)
        # print(result)
        if len(result.output) > 0:
            # utils.dbg_msg("OUTPUT IS:")
            # utils.dbg_msg(result.output)
            # utils.dbg_msg("-------")
            for entry in result.output.split("\n"):
                if entry.strip() == "":
                    continue
                if entry.strip() == cfg.v8_temp_print_id or entry.strip() == cfg.v8_print_id_not_printed:
                    continue
                if entry.startswith("OUT:") is False:
                    continue
                if "=" not in entry or " " in entry:
                    continue
                if silently_catch_exception:
                    try:
                        x = entry.split("=")
                        variable_name = x[0][len("OUT:"):]
                        variable_type = x[1]
                        # utils.dbg_msg("Variable: %s has type %s" % (variable_name, variable_type))
                        # ret.append((variable_name, variable_type))
                        if variable_type != "undefined":
                            # for array items I'm filtering out undefined, otherwise it would be too many useless entries
                            state.add_array_item_or_property_type(variable_name, line_number, variable_type)
                    except:
                        pass
                else:
                    x = entry.split("=")
                    variable_name = x[0][len("OUT:"):]
                    variable_type = x[1]
                    # utils.dbg_msg("Variable: %s has type %s" % (variable_name, variable_type))
                    # ret.append((variable_name, variable_type))
                    if variable_type != "undefined":
                        # for array items I'm filtering out undefined, otherwise it would be too many useless entries
                        state.add_array_item_or_property_type(variable_name, line_number, variable_type)

    state.recalculate_unused_variables(code)
    return state


def get_variable_types_in_line(code, code_lines, line_number, number_of_lines, number_variables, does_try_finally_work, silently_catch_exception,
                               line_start_character="", line_end_character=";"):
    ret = []
    
    # if number_variables == 0:
    #    return ret  # nothing to extract ; EDIT: This is not really true because I could extract the "this" variable, but small testcases typically don't have this then... so ignore it

    prefix = """
let variable_types = new Set();"""

    if does_try_finally_work:
        prefix += """
try {"""
    prefix += """
function log_variable(variable_name, real_variable) {
	variable_type = typeof real_variable;
	//print(variable_type);
	if(variable_type == "string" || real_variable instanceof String) {
		variable_types.add(variable_name + "=string");
	} else if(variable_type == "object") {
		// Resolve it more precise
		if(Array.isArray(real_variable) || real_variable instanceof Array) {
			variable_types.add(variable_name + "=array");
        } else if(typeof real_variable == "function") {
            variable_types.add(variable_name + "=function");	
		} else if(real_variable instanceof Int8Array) {
			variable_types.add(variable_name + "=int8array");	
		} else if(real_variable instanceof Uint8Array) {
			variable_types.add(variable_name + "=uint8array");	
		} else if(real_variable instanceof Uint8ClampedArray) {
			variable_types.add(variable_name + "=uint8clampedarray");	
		} else if(real_variable instanceof Int16Array) {
			variable_types.add(variable_name + "=int16array");	
		} else if(real_variable instanceof Uint16Array) {
			variable_types.add(variable_name + "=uint16array");	
		} else if(real_variable instanceof Int32Array) {
			variable_types.add(variable_name + "=int32array");	
		} else if(real_variable instanceof Uint32Array) {
			variable_types.add(variable_name + "=uint32array");	
		} else if(real_variable instanceof Float32Array) {
			variable_types.add(variable_name + "=float32array");	
		} else if(real_variable instanceof Float64Array) {
			variable_types.add(variable_name + "=float64array");	
		} else if(real_variable instanceof BigInt64Array) {
			variable_types.add(variable_name + "=bigint64array");	
		} else if(real_variable instanceof BigUint64Array) {
			variable_types.add(variable_name + "=biguint64array");
		} else if(real_variable instanceof Set) {
			variable_types.add(variable_name + "=set");
		} else if(real_variable instanceof WeakSet) {
			variable_types.add(variable_name + "=weakset");
		} else if(real_variable instanceof Map) {
			variable_types.add(variable_name + "=map");
		} else if(real_variable instanceof WeakMap) {
			variable_types.add(variable_name + "=weakmap");
		} else if(real_variable instanceof RegExp) {
			variable_types.add(variable_name + "=regexp");
		} else if(real_variable instanceof ArrayBuffer) {
			variable_types.add(variable_name + "=arraybuffer");
		} else if(real_variable instanceof SharedArrayBuffer) {
			variable_types.add(variable_name + "=sharedarraybuffer");	
		} else if(real_variable instanceof DataView) {
			variable_types.add(variable_name + "=dataview");
		} else if(real_variable instanceof Promise) {
			variable_types.add(variable_name + "=promise");
		} else if(real_variable instanceof Intl.Collator) {
			variable_types.add(variable_name + "=intl.collator");
		} else if(real_variable instanceof Intl.DateTimeFormat) {
			variable_types.add(variable_name + "=intl.datetimeformat");	
		} else if(real_variable instanceof Intl.ListFormat) {
			variable_types.add(variable_name + "=intl.listformat");	
		} else if(real_variable instanceof Intl.NumberFormat) {
			variable_types.add(variable_name + "=intl.numberformat");	
		} else if(real_variable instanceof Intl.PluralRules) {
			variable_types.add(variable_name + "=intl.pluralrules");	
		} else if(real_variable instanceof Intl.RelativeTimeFormat) {
			variable_types.add(variable_name + "=intl.relativetimeformat");	
		} else if(real_variable instanceof Intl.Locale) {
			variable_types.add(variable_name + "=intl.locale");	
		} else if(real_variable instanceof WebAssembly.Module) {
			variable_types.add(variable_name + "=webassembly.module");	
		} else if(real_variable instanceof WebAssembly.Instance) {
			variable_types.add(variable_name + "=webassembly.instance");	
		} else if(real_variable instanceof WebAssembly.Memory) {
			variable_types.add(variable_name + "=webassembly.memory");	
		} else if(real_variable instanceof WebAssembly.Table) {
			variable_types.add(variable_name + "=webassembly.table");	
		} else if(real_variable instanceof WebAssembly.CompileError) {
			variable_types.add(variable_name + "=webassembly.compileerror");	
		} else if(real_variable instanceof WebAssembly.LinkError) {
			variable_types.add(variable_name + "=webassembly.linkerror");	
		} else if(real_variable instanceof WebAssembly.RuntimeError) {
			variable_types.add(variable_name + "=webassembly.runtimeerror");		
		} else if(real_variable instanceof URIError) {
			variable_types.add(variable_name + "=urierror");	
		} else if(real_variable instanceof TypeError) {
			variable_types.add(variable_name + "=typeerror");	
		} else if(real_variable instanceof SyntaxError) {
			variable_types.add(variable_name + "=syntaxerror");		
		} else if(real_variable instanceof RangeError) {
			variable_types.add(variable_name + "=rangeerror");	
		} else if(real_variable instanceof EvalError) {
			variable_types.add(variable_name + "=evalerror");		
		} else if(real_variable instanceof ReferenceError) {
			variable_types.add(variable_name + "=referenceerror");	
		} else if(real_variable instanceof Error) {
			variable_types.add(variable_name + "=error");
		} else if(real_variable instanceof Date) {
			variable_types.add(variable_name + "=date");
		} else if(real_variable === null) {
			variable_types.add(variable_name + "=null");
		} else if(real_variable === Math) {
			variable_types.add(variable_name + "=math");
		} else if(real_variable === JSON) {
			variable_types.add(variable_name + "=json");
		} else if(real_variable === Reflect) {
			variable_types.add(variable_name + "=reflect");
		} else if(real_variable === globalThis) {
			variable_types.add(variable_name + "=globalThis");		
		} else if(real_variable === Atomics) {
			variable_types.add(variable_name + "=atomics");
		} else if(real_variable === Intl) {
			variable_types.add(variable_name + "=intl");
		} else if(real_variable === WebAssembly) {
			variable_types.add(variable_name + "=webassembly");	
		} else if(real_variable.constructor === Object) {
			variable_types.add(variable_name + "=object1");
		} else if(real_variable instanceof Object) {
			variable_types.add(variable_name + "=object2");		// some object which I currently don't have implemented...	
			// maybe access it via: Object.prototype.toString.call(real_variable);
		} else {
			variable_types.add(variable_name + "=unkown_object");
		}
	} else if(variable_type == "number") {
		if(isFinite(real_variable)) {
			variable_types.add(variable_name + "=real_number");
		} else {
			variable_types.add(variable_name + "=special_number");	// e.g. NaN or Infinity
		}
	} else {
		// e.g.: "function", "boolean", 'symbol', "undefined", "bigint"
		variable_types.add(variable_name + "=" + variable_type);
	}
}
"""

    if does_try_finally_work:
        suffix = """
}
finally {
	for (var it = variable_types.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
}"""
    else:
        suffix = """
	for (var it = variable_types.values(), val= null; val=it.next().value; ) {
		"""+cfg.v8_fuzzcommand+"""('"""+cfg.v8_print_command+"""', "OUT:"+val);
	}
"""


    tmp = ""
    # Add the code before the code line
    for idx in range(line_number):
        tmp += code_lines[idx] + "\n"
        
    logging_code = ""
    # Now add the new codeline + newline
    for variable_idx in range(1, number_variables+1):
        variable_name = "var_%d_" % variable_idx
        logging_code += ("try {log_variable(\"%s\",%s)} catch(e) {};" % (variable_name, variable_name))

    # Also add code to extract "this" and "self" variable types
    logging_code += "try {log_variable(\"this\",this)} catch(e) {};"
    logging_code += "try {log_variable(\"self\",self)} catch(e) {};"
    logging_code += "try {log_variable(\"arguments\",arguments)} catch(e) {};"
    logging_code += "try {log_variable(\"args\",args)} catch(e) {};"
    logging_code += "try {eval('log_variable(\"new.target\",new.target)');} catch(e) {};"

    other_variables = js_helpers.get_all_variable_names_in_testcase(code)  # old code
    other_variables2 = js_helpers.get_variable_name_candidates(code)   # new code
    for variable_name in other_variables2:
        if variable_name not in other_variables:
            other_variables.append(variable_name)

    for variable_name in other_variables:
        # utils.msg("[i] NEW VARIABLE: %s" % variable_name)
        if variable_name.startswith("var_"):
            continue    # already added
        if variable_name == "this" or variable_name == "self" or variable_name == "arguments" or variable_name == "args" or variable_name == "new.target" or variable_name == "fuzzilli":
            continue
        logging_code += ("try {log_variable(\"%s\",%s)} catch(e) {};" % (variable_name, variable_name))
    
    if line_start_character == "" and line_end_character == ";":
        pass    # it's already in correct format
    elif line_start_character == "" and line_end_character == ",":
        # In this context it's very likely not allowed to execute multiple commands
        # e.g. 
        # functionCall(1,
        # INJECTION_HERE
        # 3)
        # => in this case it's not possible to execute multiple dump-commands or even try-catch at all
        # I'm therefore using a "trick" and wrapping it inside an IIFE (immediately invoked function expression)
        logging_code = "(() => {%s})()," % logging_code
    elif line_start_character == "," and line_end_character == "":
        # Same as above
        logging_code = ",(() => {%s})()" % logging_code
    else:
        utils.perror("Logic flaw, unkown combination of input arguments: %s and %s" % (line_start_character, line_end_character))
    
    logging_code += "\n"

    tmp += logging_code

    # And now add all the other code lines:
    for idx in range(line_number, number_of_lines):
        tmp += code_lines[idx] + "\n"

    final_code = prefix + tmp + suffix
    # utils.msg("Testing line: %d" % line_number)
    # print(final_code)
    # print("------------")
    result = cfg.exec_engine.execute_once(final_code, is_query=True)
    # print(result)
    if len(result.output) > 0:
        # utils.dbg_msg("OUTPUT IS:")
        # utils.dbg_msg(result.output)
        # utils.dbg_msg("-------")
        for entry in result.output.split("\n"):
            if entry.strip() == "":
                continue
            if entry.strip() == cfg.v8_temp_print_id or entry.strip() == cfg.v8_print_id_not_printed:
                continue
            if entry.startswith("OUT:") is False:
                continue
            if "=" not in entry or " " in entry:
                continue
            if silently_catch_exception:
                try:
                    x = entry.split("=")
                    variable_name = x[0][len("OUT:"):]
                    variable_type = x[1]
                    # utils.dbg_msg("Variable: %s has type %s" % (variable_name, variable_type))
                    ret.append((variable_name, variable_type))
                except:
                    pass
            else:
                x = entry.split("=")
                variable_name = x[0][len("OUT:"):]
                variable_type = x[1]
                # utils.dbg_msg("Variable: %s has type %s" % (variable_name, variable_type))
                ret.append((variable_name, variable_type))
    return ret


def adapt_state_file_in_line_number(code, state, line_number):
    code_lines = code.split("\n")
    number_of_lines = len(code_lines)

    # Extract variables
    # Note: There is a catch. The code below is from the "normal state creation" code which creates a state for every code line
    # for the full testcase. I extract there all available (possible) variable names.
    # This logic can now include stuff like "Number" or other global available tokens like 'this' and
    # that's what I (at least at the moment) want.
    # However, with this function I adapt the state just for a newly injected code line (the template callbacks)
    # => I know that the variable names here must be exactly the same as in the original testcase plus
    # the variable names which I added. Since I just add variables in the format var_XXX_, I can safely calculate which variables
    # should be available. My callback injection code adds "global tokens" like "Number" and in the template callbacks 
    # I don't want them to be available. That's why I'm filtering the variable names in the following code
    # Note: I think the original code also added the "fuzzilli" function as "fuzzilli" variable name... (which is obviously incorrect)
    # Edit: After re-reading the above comment after some months I have no clue what I wanted to say with it...

    should_make_available_variable_names = set(state.variable_types.keys())
    for idx in range(0, 5000):
        variable_name_token = "var_%d_" % idx
        if variable_name_token in code:
            should_make_available_variable_names.add(variable_name_token)
    for idx in range(0, 9+1):
        variable_name_token = "oldObj%d" % idx  # don't ask me why I named it "oldObjXXX" and not "var_XXX_" or at least "oldObj_XXX_" ...
        if variable_name_token in code:
            should_make_available_variable_names.add(variable_name_token)

    if "args" in code:
        should_make_available_variable_names.add("args")

    # Get all variable names available in line:
    variable_types = get_variable_types_in_line(code, code_lines, line_number, number_of_lines, state.number_variables, True, True, "", ";")
    for entry in variable_types:
        (variable_name, variable_type) = entry
        if variable_name in should_make_available_variable_names:    # Filtering to just add the correct variable names (see comment above)
            if variable_type.strip() == "":
                continue
            state.add_variable_type(variable_name, line_number, variable_type)

    # Extract array lengths
    all_array_names = set(state.array_lengths.keys())

    # The new variables can be arrays, especially variables such as "args"
    # I therefore need to check here again if I have new array names
    for tmp_variable_name in state.variable_types:
        for entry in state.variable_types[tmp_variable_name]:
            (tmp_line_number, tmp_variable_type) = entry
        if tmp_variable_type == "array":
            if tmp_variable_name not in all_array_names:
                all_array_names.add(tmp_variable_name)
     
    for array_name in all_array_names:
        array_length = get_array_length_in_line(code_lines, line_number, number_of_lines, array_name, True, True, "", ";")
        if len(array_length) == 0:
            continue
        state.add_array_length(array_name, line_number, array_length)

    # Extract array items / properties
    mapping_line_number_to_tokens = dict()
    for tmp_line_number in range(state.testcase_number_of_lines):
        mapping_line_number_to_tokens[tmp_line_number] = []
    for token_name in state.array_items_or_properties:
        mapping_line_number_to_tokens[line_number].append(token_name)
    state = get_data_types_of_array_items_and_properties(code, code_lines, number_of_lines, mapping_line_number_to_tokens, True, True, state)

    return state
