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


# This mode can be started by passing the "--import_corpus_mode" flag to the fuzzer
# or by starting the fuzzer the first time (when no OUTPUT directory exists yet).
#
# The script imports new testcases into the current corpus.
# Please note that the progress of the script is not linear (especially when creating an initial corpus).
# The script will start slow (because it will find a lot of testcases with new behavior and this requires
# standardization, minimization  & state creation.
# These operations are slow because they require to restart the JS engine multiple times,
# and therefore it will take a longer time. After some time, the import-mode will be faster because it finds less files
# with new coverage. At the end, the mode will again be slow (or maybe very slow) because it's processing the
# bigger testcases (testcases are sorted based on file size and handled from small files to big files).
# State creation for big input files is extremely slow.
# It's maybe better to skip these big testcases and continue because later testcases can maybe further be
# minimized (which would then be again fast). => I created my initial corpus with a different script,
# skipping the big testcases is therefore not implemented here yet (and must manually be done).

# TODO: In my original code I also removed v8 native functions because they quickly lead to crashes
# But I couldn't find the code anymore. I guess this should be implemented in this file somewhere at the end?
# This affect at least the functions:
# %ProfileCreateSnapshotDataBlob
# %LiveEditPatchScript
# %IsWasmCode
# %IsAsmWasmCode
# %ConstructConsString
# %HaveSameMap
# %IsJSReceiver
# %HasSmiElements
# %HasObjectElements
# %HasDoubleElements
# %HasDictionaryElements
# %HasHoleyElements
# %HasSloppyArgumentsElements
# %HaveSameMap
# %HasFastProperties
# %HasPackedElements
#
# More information can be found in my master thesis page 115.


import utils
import os
import config as cfg

import native_code.speed_optimized_functions as speed_optimized_functions
from native_code.executor import Execution_Status
import sys
import random
import string
import re


code_prefix = "function my_opt_func() {\n"
code_suffix1 = """
}
%OptimizeFunctionOnNextCall(my_opt_func);
my_opt_func();
"""
code_suffix2 = """
}
%PrepareFunctionForOptimization(my_opt_func);
%OptimizeFunctionOnNextCall(my_opt_func);
my_opt_func();
"""

code_suffix3 = """
}
my_opt_func();
%PrepareFunctionForOptimization(my_opt_func);
%OptimizeFunctionOnNextCall(my_opt_func);
my_opt_func();
"""


# These are just used for debugging
debugging_number_exceptions = 0
debugging_number_success = 0
debugging_number_new_coverage = 0


def import_corpus_mode(input_dir_to_import):
    global code_prefix, code_suffix1, code_suffix2, code_suffix3
    utils.msg("[i] Going to import another corpus to the current corpus...")
    utils.msg("[i] Corpus dir which will be imported is: %s" % input_dir_to_import)

    files_to_handle = []
    already_seen_file_hashes = set()

    utils.msg("[i] Going to read all files in directory... (this can take some time)")
    for filename_to_import in os.listdir(input_dir_to_import):
        if filename_to_import.endswith(".js"):
            input_file_to_import = os.path.join(input_dir_to_import, filename_to_import)

            # Just get file size
            with open(input_file_to_import, 'r') as fobj:
                content = fobj.read().rstrip()
                sample_hash = utils.calc_hash(content)
                if sample_hash not in already_seen_file_hashes:
                    # new file
                    files_to_handle.append((input_file_to_import, len(content)))
                    already_seen_file_hashes.add(sample_hash)

    utils.msg("[i] Finished reading files. Going to sort files based on file size...")
    # Sort based on filesize => start with small files => this ensures that the minimizer is faster
    files_to_handle.sort(key=lambda x: x[1])

    utils.msg("[i] Finished sorting, going to start importing...")

    # Now start to import file by file
    cfg.my_status_screen.set_current_operation("Importing")
    total_number_files_to_import = len(files_to_handle)
    number_files_already_imported = 0
    for entry in files_to_handle:
        (input_file_to_import, filesize) = entry
        number_files_already_imported += 1
        utils.msg("[i] Importing file (%d/%d): %s" % (number_files_already_imported, total_number_files_to_import, input_file_to_import))
        with open(input_file_to_import, 'r') as fobj:
            content = fobj.read().rstrip()

        if len(content) > 200000:  # 200 KB
            continue  # big files are too slow and are bad for mutation, so skip them
        if '\x00' in content:
            continue  # ignore files with null bytes for the moment because the Python to C conversation does not support this

        # Check normal execution:
        check_if_testcase_triggers_new_behavior(content)

        # Check adapted execution (e.g. with removed testsuite functions)
        samples = preprocess_testcase(content)
        for sample in samples:
            check_if_testcase_triggers_new_behavior(sample)
            # Now check if it triggers more coverage if the code gets compiled:
            check_if_testcase_triggers_new_behavior(code_prefix + sample + code_suffix1)
            check_if_testcase_triggers_new_behavior(code_prefix + sample + code_suffix2)
            check_if_testcase_triggers_new_behavior(code_prefix + sample + code_suffix3)

    if cfg.deterministic_preprocessing_enabled:
        # And now start to preprocess all imported files! This can take a VERY long runtime
        # => I would not recommend running this because it can easily take several weeks of runtime.
        # It maybe makes sense for the first small testcases
        cfg.deterministically_preprocess_queue_func()

    return total_number_files_to_import




def check_if_testcase_triggers_new_behavior(content):
    if len(content) > 10000:  # 10 KB
        # big files are too slow and are bad for mutation, so skip them
        # Side note: I'm checking here for 10KB and in the above function for 200KB
        # because this function is maybe invoked with sub-functionality from the main script
        # which can be a lot smaller
        return

    previous_stats_new_behavior = cfg.my_status_screen.get_stats_new_behavior()

    # Restart the engine so that every testcase starts in a new v8 process
    # (=> this slows down the process but having a good input corpus is important)
    # If you want to be faster, you can maybe skip the engine restart here
    cfg.exec_engine.restart_engine()

    cfg.perform_execution_func(content, state=None)
    current_stats_new_behavior = cfg.my_status_screen.get_stats_new_behavior()
    if current_stats_new_behavior == previous_stats_new_behavior:
        # File didn't result in new coverage and was therefore not imported (importing would be done by perform_execution() )!
        # Just to get sure that there was not a flawed execution, I try it again here
        cfg.perform_execution_func(content, state=None)


# This is a debug version of the above one.
# The above one does all the required calculations (standardization, minimization, state creation)
# which is very slow. But If I just want to quickly check how many files I can import,
# then I'm using this debugging versions (which skips all these steps)
# This version does also not restart the exec engine.
# To use it, just replace the call with this function
def check_if_testcase_triggers_new_behavior_debugging(content):
    global debugging_number_exceptions, debugging_number_success, debugging_number_new_coverage

    if len(content) > 10000:  # 10 KB
        return

    result = cfg.exec_engine.execute_safe(content)
    if result.status == Execution_Status.SUCCESS:
        debugging_number_success += 1
        if result.num_new_edges > 0:
            debugging_number_new_coverage += 1

            # Dump the new coverage statistics
            number_triggered_edges, total_number_possible_edges = cfg.exec_engine.get_number_triggered_edges()
            if total_number_possible_edges == 0:
                total_number_possible_edges = 1  # avoid division by zero
            triggered_edges_in_percent = (100 * number_triggered_edges) / float(total_number_possible_edges)

            utils.msg("[i] Found new coverage! (%d success, %d exceptions, %d new coverage); New Coverage: %.4f %%" % (debugging_number_success, debugging_number_exceptions, debugging_number_new_coverage, triggered_edges_in_percent))
    elif result.status == Execution_Status.EXCEPTION_THROWN:
        debugging_number_exceptions += 1


# TODO: This is pretty old code and needs a lot of refactoring/improvement ...
# TODO: Also better implement these whole "\t" and " " and "\ņ" checking...
# One testcase file can contain multiple testcases
# That's why this function returns a list of samples
def preprocess_testcase(code):
    ret = []

    tmp = ""
    for line in code.split("\n"):
        line_check = line.strip()

        if line_check.startswith("import ") \
                or line_check.startswith("import(") \
                or line_check.startswith("export ") \
                or line_check.startswith("loaded++") \
                or line_check.startswith("await import"):
            continue  # remove import and export statements
        tmp += line + "\n"
    code = tmp

    # All the following function replacements where manually found
    # The replacements can be found by starting this script and
    # dumping all testcases which trigger an exception
    # Then the testcases can manually be analyzed to understand
    # why they lead to an exception. By doing this, the following
    # functions were identified which are not defined as default
    # JavaScript functions (in v8).
    # Identification of these functions took a long time and corpus
    # coverage can still greatly be improved by identifying more such
    # functions. However, this is a time consuming task.

    # Example: Replace wscript.echo() function calls with console.log()
    pattern = re.compile("wscript.echo", re.IGNORECASE)
    code = pattern.sub("console.log", code)

    pattern = re.compile("CollectGarbage", re.IGNORECASE)
    code = pattern.sub("gc", code)
    code = code.replace("writeLine", "console.log")
    code = code.replace("WScript.SetTimeout", "setTimeout")
    code = code.replace("helpers.writeln", "console.log")
    code = code.replace("$ERROR", "console.log")
    code = code.replace("helpers.printObject", "console.log")
    code = code.replace("WScript.Arguments", "[]")
    code = code.replace("assert.unreachable()", "")
    code = code.replace("assertUnreachable()", "")
    code = code.replace("$DONOTEVALUATE()", "")
    code = code.replace("assertStmt", "eval")
    code = code.replace("inSection", "Number")
    code = code.replace("numberOfDFGCompiles", "Number")
    code = code.replace("optimizeNextInvocation", "%OptimizeFunctionOnNextCall")
    code = code.replace("printBugNumber", "console.log")
    code = code.replace("printStatus", "console.log")
    code = code.replace("saveStack()", "0")
    code = code.replace("gcPreserveCode()", "gc()")
    code = code.replace("platformSupportsSamplingProfiler()", "true")

    # Example:
    # var OProxy = $262.createRealm().global.Proxy;
    # =>
    # var OProxy = Proxy;
    code = code.replace("$262.createRealm().global.", "")

    # Quit() is detected as a crash because v8 is closed, therefore I remove it
    # However, there can be functions like test_or_quit() where it could incorrectly remove quit()
    # Therefore I check for a space or a tab before. This is not a perfect solution, but filters
    # out some crashes
    # TODO: I now implemented better JavaScript parsing and should use the fuzzer functionality to replace it..
    code = code.replace(" quit()", "")
    code = code.replace("\tquit()", "")
    code = code.replace("\nquit()", "\n")
    code = code.replace(" quit(0)", "")
    code = code.replace("\tquit(0)", "")
    code = code.replace("\nquit(0)", "\n")
    code = code.replace("trueish", "true")  # it seems like SpiderMonkey accepts "trueish" as argument to asserEq oder reportCompare functions...
    code = remove_function_call(code, "this.WScript.LoadScriptFile")
    code = remove_function_call(code, "wscript.loadscriptfile")
    code = code.replace("WScript.LoadScript(", "eval(")
    code = code.replace("evalcx(", "eval(")  # from SpiderMonkey, however, it can have a 2nd argument for the context; so this modification is not 100% correct
    code = remove_function_call(code, "WScript.LoadModuleFile")
    code = remove_function_call(code, "WScript.LoadModule")
    code = remove_function_call(code, "WScript.Attach")
    code = remove_function_call(code, "WScript.Detach")
    code = remove_function_call(code, "saveStack")  # I already removed "saveStack()" but this here is to remove saveStack calls where an argument is passed
    code = remove_function_call(code, "WScript.FalseFile")
    code = remove_function_call(code, "assert.fail")
    code = remove_function_call(code, "assert.isUndefined")
    code = remove_function_call(code, "description")
    code = remove_function_call(code, "assertOptimized")
    code = remove_function_call(code, "assertDoesNotThrow")
    code = remove_function_call(code, "assertUnoptimized")
    code = remove_function_call(code, "assertPropertiesEqual")
    code = remove_function_call(code, "$DONE")
    code = code.replace("$DONE", "1")
    code = remove_function_call(code, "assertParts")
    code = remove_function_call(code, "verifyProperty")
    code = remove_function_call(code, "verifyWritable")
    code = remove_function_call(code, "verifyNotWritable")
    code = remove_function_call(code, "verifyEnumerable")
    code = remove_function_call(code, "verifyNotEnumerable")
    code = remove_function_call(code, "verifyConfigurable")
    code = remove_function_call(code, "verifyNotConfigurable")
    code = remove_function_call(code, "assertThrowsInstanceOf")
    code = remove_function_call(code, "testOption")
    code = remove_function_call(code, "assert.calls")
    code = remove_function_call(code, "generateBinaryTests")
    code = remove_function_call(code, "crash")  # TODO , does this detect too many functions which end with "crash"?
    # can also be code like =>crash("foo");

    # This is a special function in SpiderMonkey which supports fuzzing (?)
    code = remove_function_call(code, "offThreadCompileScript")

    code = remove_function_call(code, "startgc")  # maybe I should change it with the gc() function? But then I need to remove the startgc() argument
    code = remove_function_call(code, "gczeal")  # some other garbage collection related stuff in SpiderMonkey
    code = remove_function_call(code, "gcslice")
    code = remove_function_call(code, "schedulezone")
    code = remove_function_call(code, "schedulegc")
    code = remove_function_call(code, "unsetgczeal")
    code = remove_function_call(code, "gcstate")

    # The following is for checks like:
    # if (this.WScript && this.WScript.LoadScriptFile) {
    # Which should become:
    # if (False && False) {
    code = code.replace("WScript.LoadScriptFile", "False")
    code = code.replace("WScript.LoadScript", "False")
    code = code.replace("WScript.LoadModuleFile", "False")
    code = code.replace("WScript.LoadModule", "False")
    code = code.replace("this.WScript", "False")
    code = code.replace("this.False", "False")
    code = code.replace("WScript", "False")
    code = code.replace("$MAX_ITERATIONS", "5")

    code = remove_function_call(code, "utils.load")
    if " load" not in code and "\tload" not in code:
        # Little hack, I want to remove load function calls at the start of a file which load other JS files
        # But if load is used as a function e.g.: as code like:
        # function load(a) {
        # I don't want to remove it
        code = remove_function_call(code, "load")
    code = remove_function_call(code, "assert.isnotundefined")
    code = remove_function_call(code, "assert.isdefined")
    code = remove_function_call(code, "assert.throws")
    code = remove_function_call(code, "assert_throws")
    code = remove_function_call(code, "assertThrows")
    code = remove_function_call(code, "assertDoesNotThrow")
    code = remove_function_call(code, "shouldThrow")
    code = remove_function_call(code, "assertNull")
    code = remove_function_call(code, "shouldBeEqualToString")
    code = remove_function_call(code, "assertThrowsEquals")
    code = remove_function_call(code, "new BenchmarkSuite")  # This is not a function but it works
    code = remove_function_call(code, "assertNoEntry")
    code = remove_function_call(code, "assertEntry")
    code = remove_function_call(code, " timeout")
    code = remove_function_call(code, "\ttimeout")
    code = remove_function_call(code, "\ntimeout")
    code = remove_function_call(code, "testFailed")
    code = remove_function_call(code, "finishJSTest")
    code = remove_function_call(code, "assertIteratorDone")
    code = remove_function_call(code, "assertIteratorNext")
    code = remove_function_call(code, "assertThrowsValue")
    code = remove_function_call(code, "Assertion")
    code = remove_function_call(code, "assertStackLengthEq")
    code = remove_function_call(code, "noInline")
    code = remove_function_call(code, "enableGeckoProfiling")
    code = remove_function_call(code, "enableSingleStepProfiling")
    code = remove_function_call(code, "enableSingleStepProfiling")
    code = remove_function_call(code, "disableSingleStepProfiling")
    code = remove_function_call(code, "enableGeckoProfilingWithSlowAssertions")
    code = remove_function_call(code, "assertThrownErrorContains")
    code = remove_function_call(code, "assertDecl")  # can maybe be fixed better
    code = remove_function_call(code, "assertExpr")
    code = remove_function_call(code, "assert.compareIterator")
    code = remove_function_call(code, "$DETACHBUFFER")
    code = remove_function_call(code, "checkSpeciesAccessorDescriptor")
    code = remove_function_call(code, "assertPropertyExists")
    code = remove_function_call(code, "assertPropertyDoesNotExist")
    code = remove_function_call(code, "assert_equal_to_array")
    code = replace_assert_function(code, "assert.sameValue", "==")
    code = replace_assert_function(code, "reportCompare", "==")
    code = replace_assert_function(code, "assert.areNotEqual", "!=")
    code = replace_assert_function(code, "assert.areEqual", "==")
    code = replace_assert_function(code, "assert.equals", "==")
    code = replace_assert_function(code, "assert.strictEqual", "===")
    code = replace_assert_function(code, "assert_equals", "==")
    code = replace_assert_function(code, "assertMatches", "==")
    code = replace_assert_function(code, "assertSame", "==")
    code = replace_assert_function(code, "assertEqualsDelta", "==")
    code = replace_assert_function(code, "assertNotEquals", "!=")
    code = replace_assert_function(code, "assert.notSameValue", "!=")
    code = replace_assert_function(code, "assertEq", "==")
    code = replace_assert_function(code, "verifyEqualTo", "==")
    code = replace_assert_function(code, "assert.compareArray", "==")
    code = replace_assert_function(code, "compareArray", "==")
    code = replace_assert_function(code, "assertDeepEq", "==")
    code = replace_assert_function(code, "assertArrayEquals", "==")
    code = replace_assert_function(code, "assertArray", "==")
    code = replace_assert_function(code, "assertEqArray", "==")

    # They must not be patched if only v8 is checked, they don't lead to a crash
    # Only the static assert lead to a crash
    # code = replace_assert_function(code, "%StrictEqual", "===")
    # code = replace_assert_function(code, "%StrictNotEqual", "!==")
    # code = replace_assert_function(code, "%Equal", "==")
    # %GreaterThanOrEqual
    # %LessThan
    # %GreaterThan
    # %LessThanOrEqual
    #

    # TODO:
    # patching "assertIteratorResult" is more complicated..

    # TODO: More complicated :
    # verifySymbolSplitResult

    # TODO WebKit:
    # assert.var fhgjeduyko=array[i];
    # => var fhgjeduyko=array[i];

    code = replace_assert_function(code, "assertInstanceof", "instanceof")
    code = replace_assert_function(code, "assertEquals", "==")
    code = replace_assert_function(code, "assertNotSame", "!=")  # assertNotSame(Atomics.wake, Atomics.notify);

    # The remove_assert_function() calls are for assert functions which just have 1 argument
    code = remove_assert_function(code, "assert.isTrue")
    code = remove_assert_function(code, "assert.isFalse")
    code = remove_assert_function(code, "assert.assertFalse")
    code = remove_assert_function(code, "assertFalse")
    code = remove_assert_function(code, "assertTrue")
    code = remove_assert_function(code, "assert_true")
    code = remove_assert_function(code, "%TurbofanStaticAssert")
    code = remove_assert_function(code, "assert.shouldBeTrue")
    code = remove_assert_function(code, "assert.shouldBeFalse")
    code = remove_assert_function(code, "assert.shouldBe")
    code = remove_assert_function(code, "assert.assertNotNull")
    code = remove_assert_function(code, "shouldBeTrue")
    code = remove_assert_function(code, "shouldBeFalse")
    code = remove_assert_function(code, "shouldBe")
    code = remove_assert_function(code, "assertNotNull")
    code = remove_assert_function(code, "testJSON")
    code = remove_assert_function(code, "assertNativeFunction")
    code = remove_assert_function(code, "assert_malformed")
    code = remove_assert_function(code, "assertIteratorResult")
    code = remove_assert_function(code, "assert.doesNotThrow")
    code = remove_assert_function(code, "assert")  # This should be one of the last replacements!

    # This is a stupid last hack, in some cases assert.throws is not correctly detected because it's inside a string
    # which is later evaluated. That means the logic to detect the end of the function call does not correctly work
    # Therefore it's not removed above, here I just replace it with a call to Number to ensure that it does not crash
    code = code.replace("assert.throws", "Number")

    if "testRunner.run" in code:
        # TODO I also need to add function definitions from the start
        # E.g.: WebKit testcase: tc50725.js
        # or tc1061.js from ChakraCore

        start_testcases = ["body: function () {", "body() {"]
        while True:

            finished = True
            for start_testcase in start_testcases:
                if start_testcase in code:
                    finished = False
            if finished:
                break

            for start_testcase in start_testcases:
                if start_testcase not in code:
                    continue
                idx = code.index(start_testcase)
                rest = code[idx + len(start_testcase):]

                idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "}")
                testcase_code = rest[:idx_end]
                code = rest[idx_end + 1:]
                ret.append(testcase_code)
    elif "oomTest" in code:
        code = "function oomTest(func_name) { func_name(); }\n" + code
        ret.append(code)
    elif "runtest" in code:
        code = "function runtest(func_name) { func_name(); }\n" + code
        ret.append(code)
    else:
        # Just add it
        ret.append(code)

    return ret


def remove_function_call(code, function_call_str):
    if function_call_str[-1] != "(":
        function_call_str = function_call_str + "("
    function_call_str = function_call_str.lower()

    while True:
        code_lowered = code.lower()
        if function_call_str not in code_lowered:
            return code
        idx = code_lowered.index(function_call_str)
        if idx != 0:
            previous_char = code[idx-1]
            if previous_char != "\n" and previous_char != " " and previous_char != "\t":
                return code
        before = code[:idx]
        tmp = code[idx + len(function_call_str):]

        idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(tmp, ")")
        if idx_end == -1:
            # print("TODO Internal error in remove_function_call():")
            # print("function_call_str:")
            # print(function_call_str)
            # print("code:")
            # print(code)
            # sys.exit(-1)
            return code
        try:
            after = tmp[idx_end+1:]
        except:
            # The ")" symbol was the last symbol in the string
            after = ""
        code = before+after


def replace_assert_function(code, assert_function_str, comparison_str):
    if assert_function_str[-1] != "(":
        assert_function_str = assert_function_str + "("

    original_code = code
    original_code_len = len(original_code)
    while True:
        if len(code) > original_code_len:
            # This means the last iterations contained a bug
            # E.g.: if I replaced something like reportCompare(1,2) but the
            # actual JavaScript code didn't contain a second argument =>
            # reportCompare(1)
            # Then this code can be incorrect and start to create bigger samples
            # I catch this here and just return the unmodified code
            # Another option is that a regex string is not correctly detected
            return original_code
        if assert_function_str not in code:
            return code
        # Examples:
        # assert.sameValue(typeof f, 'function');
        # assert.sameValue(f(), 'function declaration');
        idx = code.index(assert_function_str)
        before = code[:idx]
        rest = code[idx + len(assert_function_str):]

        idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ",")
        part1 = rest[:idx_end]
        rest = rest[idx_end + 1:]
        idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ")")
        if idx_end == -1:
            return code  # return the unmodified code; this is most likely because the regex string was not correctly detected
            # and inside the regex string a symbol from another string was used...

        idx_command = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ",")
        if idx_command == -1:
            idx_command = idx_end
        elif idx_command > idx_end:
            idx_command = idx_end

        if idx_end == 0:
            return code  # some buggy case
        part2 = rest[:idx_command]
        rest = rest[idx_end + 1:]

        if len(rest) == 0:
            # can happen with some funny unicode testcases
            return original_code

        if rest[0] == ";":
            rest = rest[1:]  # remove the ";"
            code = before + part1.strip() + " " + comparison_str + " " + part2.strip() + ";" + rest
        else:
            code = before + part1.strip() + " " + comparison_str + " " + part2.strip() + " " + rest


def remove_assert_function(code, assert_function_str):
    if assert_function_str[-1] != "(":
        assert_function_str = assert_function_str + "("

    while True:
        if assert_function_str not in code:
            return code
        # Examples:
        # assert.isTrue(/error in callback/.test(frames[0]), `Invalid first frame "${frames[0]}" for ${builtin.name}`);

        idx = code.index(assert_function_str)
        before = code[:idx]
        rest = code[idx + len(assert_function_str):]

        idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ")")
        idx_command = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ",")
        if idx_end == -1:
            # print("TODO Internal coding error in remove_assert_function():")
            # print("assert_function_str: %s" % assert_function_str)
            # print(code)
            # print("----------------------")
            # print("Rest:")
            # print(rest)
            # sys.exit(-1)
            return code

        if idx_command == -1:
            idx_command = idx_end
        elif idx_command > idx_end:
            idx_command = idx_end

        assert_statement = rest[:idx_command]
        rest = rest[idx_end+1:]

        # I add here a var *varname* statement because functions can not be standalone.
        # E.g.:
        # assert.doesNotThrow(function() { Object.defineProperty(obj, key, { value: 'something', enumerable: true }); }, "Object.defineProperty uses ToPropertyKey. Property is added to the object");
        # would result in:
        # function() { ....}
        # this would throw an exception, but
        # var xyz = function() { ... }
        # doesn't throw
        random_variable_name = ''.join(random.sample(string.ascii_lowercase, 10))
        if rest[0] == ";":
            rest = rest[1:]     # remove the ";"
            code = before + "var " + random_variable_name + "=" + assert_statement.strip() + ";" + rest
        else:
            code = before + "var " + random_variable_name + "=" + assert_statement.strip() + " " + rest
