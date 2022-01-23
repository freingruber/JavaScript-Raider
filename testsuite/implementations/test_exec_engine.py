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



import config as cfg
import utils
import testsuite.testsuite_helpers as helper


# If the d8 version is vuln to issue 992914 it should crash
prone_to_issue_992914 = False       # You need a pretty old v8 for this testcase, so keep it disabled for current d8 versions
poc_for_issue_992914 = """
function main() {
          const obj1 = {foo:1.1};
          Object.seal(obj1);

          const obj2 = {foo:2.2};
          Object.preventExtensions(obj2);
          Object.seal(obj2);

          const obj3 = {foo:Object};

          obj2.__proto__ = 0;

          obj1[5] = 1;
}
main();
"""


def test_exec_engine():
    utils.msg("\n")
    utils.msg("[i] " + "-" * 100)
    utils.msg("[i] Going to start exec engine tests (expected runtime: several minutes)...")
    helper.reset_stats()

    helper.restart_exec_engine()    # Start the tests with a restarted engine

    # Test with an engine restart
    result = helper.execute_program_from_restarted_engine("var x = 1; print(x+x);\n")
    helper.assert_success(result)

    # Test 2 times without an engine restart
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)

    # Now test with an engine restart again:
    result = helper.execute_program_from_restarted_engine("var x = 1; print(x+x);\n")
    helper.assert_success(result)


    # Trigger an exception
    result = helper.execute_program("throw 42;\n")
    helper.assert_exception(result)

    # Should execute a little bit slower, but should still not trigger a timeout (at least on my slow VM CPU)
    result = helper.execute_program("for(var i = 0; i < 10000; ++i) {} \n" * 2)
    helper.assert_success(result)

    # Now a very slow example which should timeout (at least on my slow VM CPU)
    # Edit: Depending on CPU the number of iterations must be modified, e.g. on
    # a slow CPU 50 000 iterations is enough for the timeout, but on a good CPU a TIMEOUT
    # will not be created
    # Edit2: It seems that v8 was also upgraded. Empty loops are now skipped (?) and
    # need to have at least a body to trigger a timeout
    result = helper.execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 500)
    helper.assert_timeout(result)

    # Test if we find a SUCCESS after a timeout:
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)


    # now check for 2 timeouts after each other:
    result = helper.execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 500)
    helper.assert_timeout(result)
    result = helper.execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 500)
    helper.assert_timeout(result)

    # Test for an exception after a timeout
    result = helper.execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 500)
    helper.assert_timeout(result)
    result = helper.execute_program("throw 42;\n")
    helper.assert_exception(result)


    # Test for a timeout after an exception
    result = helper.execute_program("throw 42;\n")
    helper.assert_exception(result)
    result = helper.execute_program("for(var i = 0; i < 11150000; ++i) { let x = 5;} \n" * 500)
    helper.assert_timeout(result)



    # Check if output can be extracted
    result = helper.execute_program("%s('%s', 'Check if output is working')\n" % (cfg.v8_fuzzcommand, cfg.v8_print_command))
    helper.assert_success(result)
    helper.assert_output_equals(result, 'Check if output is working')


    # This testcase will put v8 engine in a bad "state" (=> this should be fixed in most recent v8)
    # The test checks if this really works
    helper.execute_program("Promise.all();")  # can lead to a "bad" state
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)  # verify if execution is SUCCESSFUL after a "bad state"

    helper.execute_program("var var_1_ = new Intl.DisplayNames();")  # can lead to a "bad state"
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)  # verify if execution is SUCCESSFUL after a "bad state"


    # Check if the output can reflect the result of some simple calculations
    result = helper.execute_program("var x = 0;\n" + "x += 1;" * 1337 + "%s('%s', x)\n" % (cfg.v8_fuzzcommand, cfg.v8_print_command))
    helper.assert_success(result)
    helper.assert_output_equals(result, '1337')

    # Check if we can detect crashes:

    # Crash with an illegal memory access
    result = helper.execute_program("%s('%s', 0);\n" % (cfg.v8_fuzzcommand, cfg.v8_crash_command))
    helper.assert_crash(result)

    # Crash with a DCHECK
    result = helper.execute_program("%s('%s', 1);\n" % (cfg.v8_fuzzcommand, cfg.v8_crash_command))
    helper.assert_crash(result)

    # Now check for a CRASH with some code which crashes the current v8:
    result = helper.execute_program("'x'.repeat(318909513).split('')")
    helper.assert_crash(result)

    # Some crash for an older v8 version
    result = helper.execute_program(poc_for_issue_992914)
    if prone_to_issue_992914:
        helper.assert_crash(result)
    else:
        helper.assert_success(result)

    # And check if the engine is restarted correctly after a crash and is functional
    result = helper.execute_program("'x'.repeat(318909513).split('')")
    helper.assert_crash(result)
    result = helper.execute_program("var x = Math.PI*2;\n")
    helper.assert_success(result)

    # Check that an exception is correctly caught after a crash:
    result = helper.execute_program("'x'.repeat(318909513).split('')")
    helper.assert_crash(result)
    result = helper.execute_program("throw 42;\n")
    helper.assert_exception(result)

    # Now check if an exception is correctly caught:
    result = helper.execute_program("try { throw 42; } catch { print(1)};\n")
    helper.assert_success(result)

    # This code will lead to an "exception crash" because of the worker
    test = """const var_1_ = `
          };`;
        const var_2_ = new Worker(var_1_, {
        type: 'string'
        }
        );
        const var_3_ = new Int32Array( new SharedArrayBuffer() );
        var_2_.postMessage([var_3_.buffer]);"""
    result = helper.execute_program(test)
    helper.assert_exception(result)

    # check if the engine correctly restarts after the "exception crash"
    result = helper.execute_program("var x = 1; print(x+x);\n")
    helper.assert_success(result)


    # TODO: Type Errors are currently not caught! The corpus can therefore contain such testcases
    # the code should be adapted so that these testcases also return "exception"
    # result = helper.execute_program("Promise.all();")
    # helper.assert_exception(result)
    # result = helper.execute_program("var var_1_ = new Intl.DisplayNames();")
    # helper.assert_exception(result)

    utils.msg("[+] SUCCESS: All %d performed exec engine tests worked as expected!" % helper.get_number_performed_tests())
    utils.msg("[i] " + "-" * 100)
