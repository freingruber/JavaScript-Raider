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

# Hint: also check the script in the testsuite which contains more comprehensive tests

import speed_optimized_functions



def perror(msg):
    print("[-] ERROR: %s" % msg)
    raise Exception()    # Raising an exception shows the stacktrace which contains the line number where a check failed
    # sys.exit(-1)


def main():
    # I re-implemented some python functions in C code to boost performance
    # This function tests the correctness of some of these implementations

    # Just some quick tests to check if the performance implementations work correctly

    # Get the next "{" starting symbol
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar{ xxx };", "{")
    if ret != 6:
        perror("Test1: Returned index was not 6: %d" % ret)


    # Since there is no "{" symbol, it should return -1
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar xxx };", "{")
    if ret != -1:
        perror("Test2: Returned index was not -1: %d" % ret)


    # Query the next "}" symbol, but it ignores "inner blocks". Since the "}" from the code is
    # from the block "{xxx }", it will be ignored and -1 should be returned
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("foobar{xxx };", "}")
    if ret != -1:
        perror("Test3: Returned index was not -1: %d" % ret)


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
    if ret != 42:
        perror("Test4: Returned index was not 42: %d" % ret)
    symbol = code[ret]
    if symbol != '}':
        perror("Test4: Symbol is not }: %s" % symbol)


    # Since the "{" symbol is within a string, it should return -1
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };'", '{')
    if ret != -1:
        perror("Test5: Returned index was not -1: %d" % ret)

    # Same as above, but now I add a "{" after the string "{"
    ret = speed_optimized_functions.get_index_of_next_symbol_not_within_string("var x = 'foobar{xxx };'; if { bla }", '{')
    if ret != 28:
        perror("Test6: Returned index was not 28: %d" % ret)


    # TODO: Add some more tests for other symbols, corner cases and so on..

    print("[+] SUCCESS: Everything seems to work")


if __name__ == "__main__":
    main()


