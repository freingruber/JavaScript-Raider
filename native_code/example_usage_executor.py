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



# This program demonstrates how to use the "Executor" with python.
# It was developed mainly to test some edge cases so that I can fully trust the results of
# the Executor and the Executor handles all cases for me (e.g.: unreliable coverage, engine restarts, ..)
# The executor is my python class to capsule the JavaScript engine interaction
# E.g.: If I want to change to a different JS engine than v8, only modifications in this class should
# be required. It implements all details to interact with JS and report the result
#
# This script can also be used to measure execution speed. 
# E.g: if the number of iterations in the loop at the end of the file is increased
# The execution time can be measured. This can be used to find new ways to make the executor faster
# Or to detect if system configurations (see prepare_system_for_fuzzing.sh) really affect the fuzzer speed.
#
# Example invocation:
# python3 example_usage_executor.py
#
# Note: Ensure that the v8/d8 path configured in config.py is correct.
# The v8/d8 binary must first be compiled (see notes in the "Target_v8" folder)
# After that, the Executor library ("libJSEngine.so") must first be compiled
# For this, the "compile.sh" script must be started
# After that, the above example invocation should work.

# Some statistics:
# Inside my (slow) virtual machine I got:
# 33.00 exec/sec with v8 instrumented and 50 executions before v8 engine start
# 34.47 exec/sec with v8 instrumented and 250 executions before v8 engine start
# 13.59 exec/sec with v8 + turbo-instrumentation and 50 executions before v8 engine start
# 13.96 exec/sec with v8 + turbo-instrumentation and 250 executions before v8 engine start

# Running on a faster CPU (still in VM but host has AMD Ryzen 5 5600X)
# and with disabled coverage feedback:
# 310 exec /sec and 100 in-memory executions before v8 engine restart
# => small testcases are executed with a runtime of 1ms per testcase
# Edit: I later modified the script (most tests were moved from this script into the testsuite,
# so the script is now a lot shorter). Currently, I get an execution speed
# with coverage feedback enabled and 100 in-memory executions of ~150 exec / sec


# Hint: also check the script in the testsuite which contains more comprehensive tests


import executor
import datetime
import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import config as cfg


# Without coverage feedback it's faster, but we don't get feedback!
# Changing this flag can mainly be used to compare the fuzzer speed
# Note: The total execution time comparison is not 100% correct
# When coverage feedback is enabled, I do multiple executions to reduce
# in-deterministic behavior. So, I do more executions when coverage is enabled.
# To compare the speed with and without coverage feedback the "exec/sec" time
# should be compared and not the total runtime of this script
should_use_coverage_feedback = True  # Should be set to True


exec_engine = None


def perror(msg):
    print("[-] ERROR: %s" % msg)
    raise Exception()    # Raising an exception shows the stacktrace which contains the line number where a check failed
    # sys.exit(-1)


def execute_program(code_to_execute):
    global exec_engine

    # exec.restart_engine()   # just for testing => but we can restart it before every execution
    starttime = datetime.datetime.now()

    # result = exec.execute_once(code_to_execute) # => execute_once should not be used. Use execute_safe() instead.
    result = exec_engine.execute_safe(code_to_execute)
    endtime = datetime.datetime.now()
    timediff = endtime - starttime

    # print("Execution time was %i microseconds" % timediff.microseconds)
    return result



def main():
    global exec_engine
    # Start testing the executor:
    exec_engine = executor.Executor(timeout_per_execution_in_ms=400, enable_coverage=should_use_coverage_feedback)
    if should_use_coverage_feedback:
        exec_engine.adjust_coverage_with_dummy_executions()
        exec_engine.backup_global_coverage_map()    # Create an in-memory snapshot of the coverage map (to restore it later)

    # Execute some valid testcase and trigger new coverage:
    result = execute_program("var x = 1; print(x+x);\n")
    print("Result of the first testcase:")
    print(result)

    if result.status == executor.Execution_Status.SUCCESS:
        print("=> Return Status Success (This shows how the return status can be checked)")
    else:
        perror("Something went wrong in 1st execution")

    if should_use_coverage_feedback:
        if result.num_new_edges != 0:
            print("=> Success: New Coverage was found!")
        else:
            perror("Something went wrong in 1st execution")


    # Now execute it again, it should not trigger new coverage:
    result = execute_program("var x = 1; print(x+x);\n")
    if result.status == executor.Execution_Status.SUCCESS:
        print("=> Still Success")
    else:
        perror("Something went wrong in 2nd execution")

    if should_use_coverage_feedback:
        if result.num_new_edges == 0:
            print("=> Success. Coverage won't be found again!")
        else:
            perror("Something went wrong in 2nd execution")


    if should_use_coverage_feedback:
        # Now restore to the state after the adjust_coverage_with_dummy_executions() call
        exec_engine.restore_global_coverage_map()

    # And now it should again find the new coverage
    result = execute_program("var x = 1; print(x+x);\n")
    if should_use_coverage_feedback:
        if result.num_new_edges != 0:
            print("=> Success: New Coverage was found!")
        else:
            perror("Something went wrong in 3rd execution")


    # Important: If the execution engine must be re-initialized, then the variable must first be deleted
    # This is important because otherwise the previous process is not shut down
    # Please note: creating another executor with different options maybe does not work 100% correct, I didn't test that yet.
    # This could result in problems when e.g. another d8 path is used in 2nd initialization
    # It's also currently not a good idea to start 2 executors at the same time
    # TODO: Fix this
    del exec_engine
    exec_engine = executor.Executor(timeout_per_execution_in_ms=400, enable_coverage=should_use_coverage_feedback)
    exec_engine.adjust_coverage_with_dummy_executions()

    # Some simple program
    result = execute_program("var x = 1; print(x+x);\n")


    # Trigger an exception
    result = execute_program("throw 42;\n")
    print("Result with an exception:")
    print(result)
    if result.status == executor.Execution_Status.EXCEPTION_THROWN:
        print("This demonstrates how an exception can be detected")




    # Should execute a little bit slower, but should still not trigger a timeout (at least on my slow VM CPU)
    result = execute_program("for(var i = 0; i < 10000; ++i) {} \n" * 2)
    print("Slower testcase had a runtime of %d ms (or more precise of %d usec)" % (result.exec_time, result.exec_time_usec))




    # Now a very slow example which should timeout (at least on my slow VM CPU)
    # Edit: Depending on CPU the number of iterations must be modified, e.g. on
    # a slow CPU 50 000 iterations is enough for the timeout, but on a good CPU a TIMEOUT
    # will not be created
    # Edit2: It seems that v8 was also upgraded. Empty loops are now skipped (?) and
    # need to have at least a body to trigger a timeout
    result = execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 100)
    if result.status == executor.Execution_Status.TIMEOUT:
        print("This code demonstrates how to check for a timeout")


    # Check if output can be received
    result = execute_program("%s('%s', 'Check if output is working')\n" % (cfg.v8_fuzzcommand, cfg.v8_print_command))
    print("This code demonstrates how to return stuff from the JavaScript engine: %s" % result.output)


    number_of_executions = 5000
    print("Going to perform %d executions. This can take a moment..." % number_of_executions)
    # This will run a long time, but will give a better idea about the real exec/sec
    # because it does not crash and does not yield new coverage
    execute_program("var xyz_12415 = 152151;\n")
    for i in range(0, number_of_executions):
        execute_program("var xyz_%d = %d;\n" % (i, i))

    #  Print some execution statistics at the end
    print("\n--------------- Executor Statistics ---------------")
    exec_engine.print_statistics()


if __name__ == "__main__":
    main()
