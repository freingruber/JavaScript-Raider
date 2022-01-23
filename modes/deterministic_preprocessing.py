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


# This script implements deterministic operations
# The idea is to perform 20-30 operation, which commonly result in new behavior, on every
# new testcase in the corpus.
# E.g: it tries to trigger garbage collection in every possible code line in a testcase
# and it checks if this leads to new behavior / coverage.
# 
# Deterministic preprocessing can have a very very long runtime.
# I started it for my (old) full corpus for 16 days and then canceled the script for the last files
# In total I processed 9105 of 9160 files. I canceled it because later files are a lot bigger 
# which means the runtime would even be longer.
# I stopped preprocessing after all files smaller than 7 KB were preprocessed.
# It's therefore recommended to maybe limited the maximum corpus file size to 7 KB (?)
# Preprocessing bigger files makes no sense because the time is better spend in real fuzzing.
# Note: my current corpus contains 18 000 files. Deterministic preprocessing would take very long with this corpus...
# I therefore currently have this setting disabled

# The code in this file is therefore not really refactored (because I don't use it anymore) and not well tested.

# TODO: Maybe move some of the functions in this script to a generic js_helper.py file?
# => Some of these functions could also be useful for the mutate_js.py script!

# TODO: PyCharm tells me that strings like "\(\)" contain invalid escape sequences. I think PyCharm is right,
# but the code currently works. When I have time, I should test and fix this.

import re
import utils
import config as cfg


# This is a function which performs the real execution.
# The caller of this script must pass a callback to this function.
queue_to_preprocess = []


def check_if_code_triggers_new_behavior(testcase_content, state):
    # Call the perform_execution() function from the main module
    # This function handles everything else (do the execution and check if triggers new coverage,
    # if yes, then standardize the testcase, minimize it and create a state file and add it to the corpus)
    cfg.perform_execution_func(testcase_content, state)         # the real function implementation is in JS_FUZZER.py


def get_code_with_inserted_codeline(code_lines, line_number_to_insert, number_of_lines, codeline_to_insert):
    tmp = ""
    # Add the code before the code line
    for idx in range(line_number_to_insert):
        tmp += code_lines[idx] + "\n"
    # Now the added code line
    tmp += codeline_to_insert + "\n"
    # And now add all the other code lines:
    for idx in range(line_number_to_insert, number_of_lines):
        tmp += code_lines[idx] + "\n"
    return tmp


def get_code_before_pos_until_previous_newline(code, pos):
    pos -= 1
    tmp = ""
    while True:
        if pos < 0:
            break
        if code[pos] == "\n":
            break
        tmp += code[pos]
        pos -= 1
    return tmp[::-1].strip()    # reverse it because of backwards iteration in the loop


def add_codeline_as_function_arguments(codeline, code, state):
    # First add the additional argument in function calls where no argument is passed yet
    # e.g.: in calls to "func_1_()" I need to patch to "func_1_(*codeline*)"

    matches = re.finditer(r"\(\)", code)
    matches_positions = [match.start() for match in matches]
    matches2 = re.finditer(r"\( \)", code)
    matches_positions2 = [match.start() for match in matches2]
    matches_positions_together = matches_positions + matches_positions2
    # utils.dbg_msg("MATCH POSITIONS:")
    # utils.dbg_msg(matches_positions_together)
    for pos in matches_positions_together:
        idx_before = pos-len("function func_9999_")
        if idx_before < 0:
            idx_before = 0
        part_before = code[idx_before:pos]      # this returns a possible "function func_XXX_" string
        if "function" in part_before:
            continue    # skip the function declaration, I just want to add the code in function calls!
        if get_code_before_pos_until_previous_newline(code, pos).startswith("%"):
            # this would be an injection into a native function which often leads to a crash
            # For example:
            # %PrepareFunctionForOptimization(func_1_, "")          # NOTE at this code location the function call doesn't receive an argument
            # If we inject here an additional argument like:
            # %PrepareFunctionForOptimization(func_1_, "", %DeoptimizeNow());
            # => it immediately crashes. I therefore don't inject arguments to native functions to avoid these crashes
            continue
        new_code = code[:pos+1]     # +1 to add the ( in the first part
        new_code += codeline
        new_code += code[pos+1:]    # now the ) and the other part or " )"
        check_if_code_triggers_new_behavior(new_code, state)

    # And now patch function calls for which arguments are already passed
    # I pass it as last argument which should in most cases not influence the code
    # and should just add another effect edge in the sea-of-nodes
    matches3 = re.finditer(r"\)", code)
    matches_positions3 = [match.start() for match in matches3]
    for pos in matches_positions3:
        if (pos-1) in matches_positions:        # -1 because "matches_positions" stores the start of "()" and "pos" is the start of ")"
            continue    # it was already patched
        if (pos-2) in matches_positions2:        # -2 because "matches_positions2" contains an additional space
            continue    # it was already patched

        if get_code_before_pos_until_previous_newline(code, pos).startswith("%"):
            # this would be an injection into a native function which often leads to a crash
            # For example:
            # %PrepareFunctionForOptimization(func_1_, "")
            # If we inject here an additional argument like:
            # %PrepareFunctionForOptimization(func_1_, "", %DeoptimizeNow());
            # => it immediately crashes. I therefore not inject arguments to native functions to avoid these crashes
            continue
        # the check for the "functions" keyword is here not working because I don't know the length of the arguments
        # it would require complex parsing to go backwards to find the last "(" symbol
        # therefore I skip this check here and just try at all possible locations
        # this includes maybe some not required executions...
        new_code = code[:pos]
        new_code += ","+codeline            # now coma separated to separate it from other arguments
        new_code += code[pos:]    # now the ) and the other part
        check_if_code_triggers_new_behavior(new_code, state)


# Giving the "pos" (position) of a "(" symbol in the code-string,
# this function will go backwards and extracts the name of the function to get the
# function invocation name.
# Important: This is just for function INVOCATIONS. If it's a function definition, an empty string will be returned
# (This is used to filter out function definitions)
def get_function_name_before_arguments(code, pos):
    tmp = ""
    if code[pos] != "(":
        utils.msg("[-] Logic error in get_function_name_before_arguments() => incorrect call")
        return ""
    while True:
        pos = pos - 1
        if pos < 0:
            break
        if code[pos] == "," or code[pos] == ":" or code[pos] == "(" or code[pos] == ";" or code[pos] == ")" or code[pos] == "{" or code[pos] == "}" or code[pos] == "'" or code[pos] == '"' or code[pos] == "`" or code[pos] == "/" or code[pos] == "?" or code[pos] == "!" or code[pos] == "\\" or code[pos] == "|":
            break  
        if code[pos] == " " or code[pos] == "\t" or code[pos] == "\n":
            # found the split character
            if tmp == "":
                continue    # don't break
            else:
                # it's now at the end
                pos_before = pos - len("function") - 3  # 3 if they used more spaces between the function keyword and the function name...
                if pos_before < 0:
                    pos_before = 0
                part_before = code[pos_before:pos]
                if "function" in part_before:
                    return ""   # this is a stupid hack: I want to ensure that I just get function names of invocations and not of function definitions
                break
        tmp += code[pos]    # add the character
    return tmp[::-1].strip()        # return the reversed string (because I iterated backwards)


def change_function_calls_to_call_syntax(code, state):
    # For example, a Math.
    matches = re.finditer(r"\(", code)
    matches_positions = [match.start() for match in matches]
    for pos in matches_positions:
        func_name = get_function_name_before_arguments(code, pos)
        if func_name == "":
            continue
        # utils.dbg_msg("FUNCTION NAME IS: %s" % func_name)
        new_code = code[:pos]
        new_code += ".call(%s," % func_name     # add the .call syntax
        new_code += code[pos+1:]    # now the other part; the +1 ensures that "(" is not added because the "(" is already added by the call syntax substring
        check_if_code_triggers_new_behavior(new_code, state)


def try_to_add_codeline(codeline, code, state):
    # First try to add it in every line
    code_splitted = code.split("\n")
    number_of_lines = len(code_splitted)

    for line_number in state.lines_where_code_can_be_inserted:
        if line_number not in state.lines_which_are_not_executed:
            check_if_code_triggers_new_behavior(get_code_with_inserted_codeline(code_splitted, line_number, number_of_lines, codeline + ";"), state)
    for line_number in state.lines_where_code_with_coma_can_be_inserted:
        if line_number not in state.lines_which_are_not_executed:
            check_if_code_triggers_new_behavior(get_code_with_inserted_codeline(code_splitted, line_number, number_of_lines, codeline + ","), state)
   
    add_codeline_as_function_arguments(codeline, code, state)


def get_code_with_wrapped_codeline(code_lines, code_line_number_to_wrap, number_of_lines, prefix, suffix):
    tmp = ""
    # Add the code before the code line
    for idx in range(code_line_number_to_wrap):
        tmp += code_lines[idx] + "\n"
    # Now the added code line
    tmp += prefix + code_lines[code_line_number_to_wrap] + suffix + "\n"
    # And now add all the other code lines:
    for idx in range(code_line_number_to_wrap+1, number_of_lines):
        tmp += code_lines[idx] + "\n"
    return tmp


def wrap_code_in(code, state, prefix, suffix):
    lines_merged = set()
    lines_merged |= set(state.lines_where_code_can_be_inserted)
    lines_merged |= set(state.lines_where_code_with_coma_can_be_inserted)
    lines_merged = lines_merged - set(state.lines_which_are_not_executed)

    code_splitted = code.split("\n")
    number_of_lines = len(code_splitted)
    if number_of_lines in lines_merged:
        # This is the code line which would be appended at the end of the testcase
        # Since this code line can't exist, we can remove it because we can't wrap it
        lines_merged.remove(number_of_lines)

    for code_line_number_to_wrap in lines_merged:
        extension = ""
        if code_line_number_to_wrap in state.lines_where_code_can_be_inserted:
            extension = ";"
        elif code_line_number_to_wrap in state.lines_where_code_with_coma_can_be_inserted:
            extension = ","
        code = get_code_with_wrapped_codeline(code_splitted, code_line_number_to_wrap, number_of_lines, prefix, suffix + extension)
        check_if_code_triggers_new_behavior(code, state)



def try_deoptimize(code, state):
    try_to_add_codeline("%DeoptimizeNow()", code, state)


def try_gc(code, state):
    try_to_add_codeline("gc()", code, state)
    try_to_add_codeline("{gc(); gc()}", code, state)  # two times gc() can be important to shift it to OLD SPACE; wrapped in {} to ensure it also works in a coma-separated context


def try_super(code, state):
    # Does it really make sense to call super() at all possible code lines? Not really
    try_to_add_codeline("super()", code, state)


def try_try_catch_block(code, state):
    # Force the turbofan compiler (I think this only helps in old v8 builds which use Crankshaft, but I'm not sure)
    try_to_add_codeline("try { } finally { }", code, state)


def try_empty_control_flows(code, state):
    try_to_add_codeline("for(;;) {break;}", code, state)    # empty for loop
    try_to_add_codeline("for(;false;) {}", code, state) 
    try_to_add_codeline("if(1 == 0) {}", code, state)
    try_to_add_codeline("if(1 == 1) {} else {}", code, state)

    # TODO add code like:
    # for(;0<0;)
    #   while(1 === 1) {}
    # see: Firefox bug 1493900, CVE-2018-12386 


def try_delete_this(code, state):
    try_to_add_codeline("delete this", code, state)
    try_to_add_codeline("this.__proto__ = undefined", code, state)
    try_to_add_codeline("this.__proto__ = 0", code, state)
    try_to_add_codeline("this.__proto__ = {}", code, state)
    try_to_add_codeline("delete this.__proto__", code, state)
    try_to_add_codeline("Object.create(this)", code, state)
    
    
def try_special_stuff(code, state):
    try_to_add_codeline("Array(2**30)", code, state)    # Ensures that TurboFan won't inline array constructors
    try_to_add_codeline("parseInt()", code, state)     # This prevents functions from getting inlined
    try_to_add_codeline("for (let i = 0; i < 0x100000; i++) { parseInt(); }", code, state) 
    try_to_add_codeline('"use strict"', code, state)
    try_to_add_codeline("break", code, state) 
    try_to_add_codeline("continue", code, state) 


def try_arguments(code, state):
    try_to_add_codeline("arguments", code, state)
    try_to_add_codeline("Object.create(arguments)", code, state)
    try_to_add_codeline("delete arguments", code, state)
    try_to_add_codeline("arguments.__proto__ = 0", code, state)


def test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line):
    if line_number in state.lines_where_code_can_be_inserted:
        code_line += ";"
    elif line_number in state.lines_where_code_with_coma_can_be_inserted:
        code_line += ","
    else:
        print("Unkown codeline number %d, logic error? Stopping..." % line_number)
    code_to_test = get_code_with_inserted_codeline(code_splitted, line_number, number_of_lines, code_line)
    check_if_code_triggers_new_behavior(code_to_test, state)


def add_testcase_to_preprocessing_queue(code, state, filename):
    global queue_to_preprocess
    utils.msg("[i] Testcase %s (length %d) was added to preprocessing queue" % (filename, len(code)))
    queue_to_preprocess.append((code, state, filename, len(code)))


def process_preprocessing_queue():
    if len(queue_to_preprocess) == 0:
        return  # return without showing a message
    utils.msg("[i] Process preprocessing queue called, current queue length: %d" % len(queue_to_preprocess))
    while len(queue_to_preprocess) != 0:
        queue_to_preprocess.sort(key=lambda x: x[3])     # Sort based on testcase size => start with the small files! This will later require less minimization and is therefore faster
        (code, state, filename, content_length) = queue_to_preprocess.pop(0)
        utils.msg("[i] Handling next entry (%s) in preprocessing queue, current length is: %d" % (filename, len(queue_to_preprocess) + 1))
        deterministic_preprocess_testcase(code, state)  # currently the returned state is ignored; TODO: Maybe later fix it and save the updated state?
    utils.msg("[i] Finished handling the preprocessing queue!")



def deterministic_preprocess_testcase(code, state):
    # The length in the following message helps to approx. guess how long it will take to finish preprocessing
    utils.msg("[i] Starting to deterministically preprocess testcase (length: %d)" % len(code))

    if len(code) >= 6000:
        utils.msg("[i] Testcase is bigger than 6000 bytes (%d bytes), preprocessing would take too long, so it's skipped.." % len(code))
        return state
    
    # Note: removing 1 line in the testcase could also be an interesting operation
    # However, this would already be done during testcase minimization
    # So it must not be done again

    code_splitted = code.split("\n")
    number_of_lines = len(code_splitted)

    # Test when codeline is just interpreted or executed by compiled code
    wrap_code_in(code, state, prefix="if (%IsBeingInterpreted()) {\n", suffix="\n}")
    wrap_code_in(code, state, prefix="if (!%IsBeingInterpreted()) {\n", suffix="\n}")

    wrap_code_in(code, state, prefix="eval(`", suffix="`)")
    wrap_code_in(code, state, prefix="if(true) {\n", suffix="\n}")
    # Wrap inside a 1-iteration loop
    wrap_code_in(code, state, prefix="do {\n", suffix="\n} while(false)")
    wrap_code_in(code, state, prefix="for (let unused_variable_idx = 0; unused_variable_idx  < 1; unused_variable_idx ++) {\n", suffix="\n}")

    # Now into 2 loop iterations
    wrap_code_in(code, state, prefix="for (let unused_variable_idx = 0; unused_variable_idx  < 2; unused_variable_idx ++) {\n", suffix="\n}")

    wrap_code_in(code, state, prefix="return", suffix="")

    wrap_code_in(code, state, prefix="try{\n", suffix="\n} catch  {\n}")
    wrap_code_in(code, state, prefix="try{\n", suffix="} finally {\n}")
    wrap_code_in(code, state, prefix="try{\n} finally {\n", suffix="\n}")

    try_to_add_codeline("%SimulateNewspaceFull()", code, state)
    try_deoptimize(code, state)
    try_gc(code, state)
    try_super(code, state)
    try_try_catch_block(code, state)
    try_empty_control_flows(code, state)
    try_delete_this(code, state)
    try_special_stuff(code, state)
    try_arguments(code, state)

    change_function_calls_to_call_syntax(code, state)

    # Perform deterministic operations on the variables
    for variable_name in state.variable_types:
        # Try to add the variable as additional argument to function invocations
        # This can create additional effect edges
        add_codeline_as_function_arguments(variable_name, code, state)

        # And now perform typ-specific operations, e.g. to detach array buffers
        for entry in state.variable_types[variable_name]:
            (line_number, variable_type) = entry

            # Operations on arrays
            if "array" in variable_type and variable_type != "array":   # so stuff like UInt32Array or bigint64array but not "array"
                code_line = "%%ArrayBufferDetach(%s.buffer)" % variable_name
                test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)
 
            # Operations on all variables
            code_line = "%%HeapObjectVerify(%s)" % variable_name
            test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)
 
            if variable_name != "this":
                # "delete this" was already tested with another deterministic preprocessing operation
                code_line = "delete %s" % variable_name
                test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)

            code_line = "%s.__proto__ = 0" % variable_name
            test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)

            code_line = "%s.__proto__ = {}" % variable_name
            test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)
   
            code_line = "%s.constructor = () => {}" % variable_name
            test_insertion_of_codeline_at_line_number(code_splitted, line_number, number_of_lines, state, code_line)

    # Now the optimization stuff
    for function_id in range(state.number_functions):
        func_name = "func_%d_" % (function_id+1)
        try_to_add_codeline("%%OptimizeFunctionOnNextCall(%s)" % func_name, code, state)
        try_to_add_codeline("%%DeoptimizeFunction(%s)" % func_name, code, state)
        try_to_add_codeline("%%NeverOptimizeFunction(%s)" % func_name, code, state)
        try_to_add_codeline("%%PrepareFunctionForOptimization(%s)" % func_name, code, state)
        try_to_add_codeline("%%ClearFunctionFeedback(%s)" % func_name, code, state)
    try_to_add_codeline("%%UnblockConcurrentRecompilation()", code, state)

    # TODO: Maybe it makes sense to change every numeric value in the testcase to -0
    # Maybe implement this later as deterministic step

    # I'm marking here that preprocessing was done, however, currently I'm not storing the state afterwards to the file..
    state.deterministic_processing_was_done = True

    utils.msg("[i] Finished deterministically preprocessing testcase")
    return state
