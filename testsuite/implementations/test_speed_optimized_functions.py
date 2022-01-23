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
import native_code.speed_optimized_functions as speed_optimized_functions
import testsuite.testsuite_helpers as helper


def test_speed_optimized_functions():
    utils.msg("\n")
    utils.msg("[i] " + "-" * 100)
    utils.msg("[i] Going to start speed optimized functions tests...")
    helper.reset_stats()


    # Get the next "{" starting symbol
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar{ xxx };", "{")
    helper.assert_int_value_equals(ret, 6, "Returned index for { is wrong")

    # Since there is no "{" symbol, it should return -1
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar xxx };", "{")
    helper.assert_int_value_equals(ret, -1, "Return value should be -1 because there is no { symbol")


    # Query the next "}" symbol, but it ignores "inner blocks". Since the "}" from the code is
    # from the block "{xxx }", it will be ignored and -1 should be returned
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar{xxx };", "}")
    helper.assert_int_value_equals(ret, -1, "Returned value should be -1 because there is no un-opened } symbol.")


    # Let's consider this (simplified) code:
    # for {
    #       if { blabla }
    #       else { foobar
    #       }
    #       xxxxx
    #  }
    # SomeOtherCode;
    #
    # And then consider that the current position is after the "for {" line (it was already parsed)
    # In this case it should return the index of the last "}" symbol if I query for "}"
    code = "      if { blabla }\nelse { foobar\n}\nxxxxx\n}\nSomeOtherCode;"
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(code, "}")
    helper.assert_int_value_equals(ret, 42, "Returned value is wrong.")

    symbol = code[ret]
    helper.assert_string_value_equals(symbol, "}", "Returned value is wrong.")

    # Since the "{" symbol is within a string, it should return -1
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };'", '{')
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")


    # Same as above, but now I add a "{" after the string "{"
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };'; if { bla }", '{')
    helper.assert_int_value_equals(ret, 28, "Returned value is wrong.")

    # Again, but now with another { afterwards (make sure the code always checks for the first one
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };'; if { bla } else { xyz }", '{')
    helper.assert_int_value_equals(ret, 28, "Returned value is wrong.")

    # Now with an ending }
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };';  if {", '{')
    helper.assert_int_value_equals(ret, 29, "Returned value is wrong.")

    # And now the same if the "}" is missing within the script
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx;'; if {", '{')
    helper.assert_int_value_equals(ret, 26, "Returned value is wrong.")

    # And now with a "}" inside a string:
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar}xxx;'; if {", '{')
    helper.assert_int_value_equals(ret, 26, "Returned value is wrong.")

    # Now with { only within a string but use " as string symbol
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "foobar{xxx };"', '{')
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    # And now with a result after the string:
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "foobar{xxx };"; if { bla } else { xyz }', '{')
    helper.assert_int_value_equals(ret, 28, "Returned value is wrong.")

    # Now with { only within a string but use ` as string symbol
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = `foobar{xxx };`', '{')
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    # And now with a result after the string:
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = `foobar{xxx };`; if { bla } else { xyz }', '{')
    helper.assert_int_value_equals(ret, 28, "Returned value is wrong.")


    # Now some basic tests for the "(" symbol:
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('bblablaba { } { [][ / ,,",', "(")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('bblabl)aba { } { [][ / ,,",', "(")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "foobar"; someFunctionCall(1,2,3); someOtherCall(1);', '(')
    helper.assert_int_value_equals(ret, 34, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "foo(bar"; someFunctionCall(1,2,3); someOtherCall(1);', '(')
    helper.assert_int_value_equals(ret, 35, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "foob)ar"; someFunctionCall(1,2,3)', '(')
    helper.assert_int_value_equals(ret, 35, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var x = "fo(obar)"; someFunctionCall(1,2,3); someOtherCall(1);', '(')
    helper.assert_int_value_equals(ret, 36, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('bblabl) xyz ()', "(")
    helper.assert_int_value_equals(ret, 12, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('(bblabl) xyz ()', "(")
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('(', "(")
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(' (', "(")
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(')(', "(")
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()(', "(")
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(')((', "(")
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('")"((', "(")
    helper.assert_int_value_equals(ret, 3, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"(")(', "(")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str1="foo`bar"; var str2="x)`yz"; someFunction(1,2,3);', "(")
    helper.assert_int_value_equals(ret, 50, "Returned value is wrong.")


    # Check for )
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(')', ")")
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('))', ")")
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(' )', ")")
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    # Should return -1 because the ) belongs to the opening ( and then there is no ) afterwards
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('())', ")")
    helper.assert_int_value_equals(ret, 2, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()  )', ")")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()  ) ', ")")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()  ) )', ")")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('()  ) ()', ")")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"()"  ) ', ")")
    helper.assert_int_value_equals(ret, 6, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"(")  ) ', ")")
    helper.assert_int_value_equals(ret, 3, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('`(`)  ) ', ")")
    helper.assert_int_value_equals(ret, 3, "Returned value is wrong.")

    # try if the full testcase is a string:
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"asganag()aslg)"', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"asganaslg)"', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("'asganag()aslg)'", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("'asganaslg)'", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("`asganag()aslg)`", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("`asganaslg)`", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    # Let's now try some malformed testcases, e.g.: in which a string is not closed
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"()  ) ', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('`()  ) ', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("'()  ) ", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('someStringBefore"()  ) ', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('someStringBefore`()  ) ', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("someStringBefore'()  ) ", ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")


    # Now try an escaped symbol within the string
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(',foo="xyz\\\"",2,3)xyz', ")")
    helper.assert_int_value_equals(ret, 16, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string(',)foo="xyz\\\"",2,3)xyz', ")")
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    # Let's now try to combine string characters like " and `
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"`(`")  ) ', ")")
    helper.assert_int_value_equals(ret, 5, "Returned value is wrong.")


    # Let's now try to see if the function detects if "`" is not the start of a string and just a symbol in the string
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"`(")  ) ', ")")
    helper.assert_int_value_equals(ret, 4, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str1="foo`bar"; var str2="x)`yz"; someFunction(1,2,3);', ")")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str1="foo`bar"; var str2="x)`yz"; someFunction(1,2,3), ) ', ")")
    helper.assert_int_value_equals(ret, 59, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str1="foo`bar"; someFunction(1,2,3), ) ;var str2="x)`yz"; ', ")")
    helper.assert_int_value_equals(ret, 41, "Returned value is wrong.")


    # Some tests for [
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var xyz = [1,2,3];', "[")
    helper.assert_int_value_equals(ret, 10, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var xyz = [1,[2,],3];', "[")
    helper.assert_int_value_equals(ret, 10, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var xyz = "[1,2,3]";', "[")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var xyz = '[1,2,3]';", "[")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var xyz = "[1,2,3]";', "[")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")


    # Some checks for ]
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var xyz = [1,2,3] ];', "]")
    helper.assert_int_value_equals(ret, 18, "Returned value is wrong.")

    # Check if the "incorrect" opening symbol is within a string and is correctly ignored
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('"["];', "]")
    helper.assert_int_value_equals(ret, 3, "Returned value is wrong.")


    # Checks for /
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('foobar / 123', "/")
    helper.assert_int_value_equals(ret, 7, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('foobar "/" 123', "/")
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('foobar "/" 12/3', "/")
    helper.assert_int_value_equals(ret, 13, "Returned value is wrong.")


    # Checks for "
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str = "foobar"', '"')
    helper.assert_int_value_equals(ret, 10, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str = \'"foobar"\'', '"')
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str = \'"foo\'bar"', '"')
    helper.assert_int_value_equals(ret, 19, "Returned value is wrong.")


    # Checks for '
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var str = 'foobar'", "'")
    helper.assert_int_value_equals(ret, 10, "Returned value is wrong.")


    # Checks for `
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('var str = `foobar`', '`')
    helper.assert_int_value_equals(ret, 10, "Returned value is wrong.")

    # Checks for ,
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('1,2,3);', ',')
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('someFunction"foo,",2,3);', ',')
    helper.assert_int_value_equals(ret, 18, "Returned value is wrong.")

    # This one returns -1 because stuff inside ( and ) is not considered because "in the current context"
    # there is no ",". E.g. while parsing function arguments and I want to go to the next function argument,
    # which is separated via ",", then I need to skip possible function arguments to function calls in arg1
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('someFunction(1,2,3);', ',')
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    # TODO: This is currently wrong and returns -1!
    # ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string('someFunction(1,2,3),arg2,arg3)', ',')
    # helper.assert_int_value_equals(ret, 19, "Returned value is wrong.")





    # Some tests for
    testcase = """someCode;
someOtherCode;
foobar"""
    ret = speed_optimized_functions.get_line_number_of_offset(testcase, 0)
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, 1)
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, 9)
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, 10)
    helper.assert_int_value_equals(ret, 1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, len(testcase))
    helper.assert_int_value_equals(ret, 2, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, len(testcase)-1)
    helper.assert_int_value_equals(ret, 2, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset(testcase, len(testcase)+1)
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset("", 0)
    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    ret = speed_optimized_functions.get_line_number_of_offset("", 1)
    helper.assert_int_value_equals(ret, -1, "Returned value is wrong.")


    # TODO: Per definition I return 0 for a negative index input, but it maybe makes sense
    # to change this to -1, but this would require an additional check
    # and I never pass a negative number, so it doesn't really matter
    ret = speed_optimized_functions.get_line_number_of_offset(testcase, -5)

    helper.assert_int_value_equals(ret, 0, "Returned value is wrong.")

    utils.msg("[+] SUCCESS: All %d performed speed optimized function-tests worked as expected!" % helper.get_number_performed_tests())
    utils.msg("[i] " + "-" * 100)
