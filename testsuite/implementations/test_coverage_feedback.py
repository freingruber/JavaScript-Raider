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


# This script contains two categories of tests
# 1) Functional tests:
#       These tests ensure that everything works as expected and that the coverage
#       feedback really works (e.g. new coverage is just returned in the first execution
#       and later not again. And that stuff like resetting the coverage feedback works).
#
# 2) Coverage feedback quality tests:
#       These tests can be used to measure "how good" the used coverage feedback is.
#       The tests contain different JavaScript code which should return different coverage feedback
#       in the opinion of the author. The code then measures which testcases really result in different (new)
#       coverage feedback.
#       This can be used to test different coverage feedback strategies to improve the current one
#       and make them comparable.
#       For example, let's say that the current coverage feedback just results in 60% passed tests,
#       then a different coverage method can be searched which results in a better coverage.
#       (and, if possible, with a similar execution speed). Let's say one can be found which is assumed
#       to work better, but is a lot slower. If this new method then results in let's say 62% passed tests,
#       it's maybe better to skip it and use the original, faster feedback method.
#       But if it results in 95% passed tests, it could make sense to use the new coverage method.
#       The tests are currently not comprehensive, but that's ok. I just need it as a rough heuristic.
#       It's maybe a good idea to later add a lot more tests to it (maybe also JIT tests or combined function calls).
#       This testsuite can also be used to compare the coverage feedback from different engines (e.g.: v8 vs. SpiderMonkey vs. JSC).


# Note:
# Tests should typically be independent from each other (E.g. the order of the tests should not matter).
# Since the code here tests the coverage feedback and coverage is just returned in the first occurrence,
# the tests are not independent (the correct order of the execution of them is important).
# I could change this by resetting in between the coverage map, but then the testsuite would run a lot longer.
# In this case, I preferred a fast testsuite execution time over independent tests.

import config as cfg
import utils
import testsuite.testsuite_helpers as helper


# Some of these tests fail. They test how good the coverage feedback is.
# For example, I know that I execute different JavaScript code which should
# create different coverage feedback => I measure if this is really the case.
# The goal is to find a
def start_coverage_feedback_quality_tests():
    utils.msg("[i] Going to measure coverage feedback quality (some of these tests can fail)...")
    helper.reset_stats()

    helper.restart_exec_engine()  # Start the tests with a restarted engine

    # Reload the "empty coverage map" to ensure that we start with a fresh coverage map
    # Which should be able to find new coverage
    cfg.exec_engine.load_global_coverage_map_from_file(cfg.coverage_map_testsuite)


    result = helper.execute_program("var x = Date; print(x)")
    helper.expect_new_coverage(result)


    result = helper.execute_program("var x = [1,2,3,4]")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = [1,2,3,4]")
    helper.assert_no_new_coverage(result)           # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    result = helper.execute_program("var x = [1.0,,,5.0]")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = [1.0,,,5.0]")
    helper.assert_no_new_coverage(result)           # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    # Now add an object to the array, this should generate new coverage
    result = helper.execute_program("var x = [1.0,,,{}]")
    helper.expect_new_coverage(result)

    # Increment instruction is new:
    result = helper.execute_program("var i = 0; ++i")
    helper.expect_new_coverage(result)
    result = helper.execute_program("var i = 0; ++i")
    helper.assert_no_new_coverage(result)  # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    # Post increment:
    result = helper.execute_program("var i = 0; i++")
    helper.expect_new_coverage(result)
    result = helper.execute_program("var i = 0; i++")
    helper.assert_no_new_coverage(result)  # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    # For Loop is new, which should be detected:
    result = helper.execute_program("for(var i = 0; i < 10000; ++i) {} \n" * 2)
    helper.expect_new_coverage(result)

    # Printing the Math object is new:
    result = helper.execute_program("print(Math)")
    helper.expect_new_coverage(result)

    for i in range(0, 5):
        result = helper.execute_program("print(Math)")
        helper.assert_no_new_coverage(result)  # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    # Check if Accessing Math.PI leads to new coverage
    result = helper.execute_program("print(Math.PI)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.max(0,20,13,75);")
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.min(0,20,13,75);")
    helper.expect_new_coverage(result)

    result = helper.execute_program("20-5")
    helper.expect_new_coverage(result)

    result = helper.execute_program("4*20")
    helper.expect_new_coverage(result)

    result = helper.execute_program("5<1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("5<=1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("1>=1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("4>1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Number(4711).toExponential();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("!true")
    helper.expect_new_coverage(result)

    result = helper.execute_program("!false")
    helper.expect_new_coverage(result)

    result = helper.execute_program("true && true")
    helper.expect_new_coverage(result)

    result = helper.execute_program("true || false")
    helper.expect_new_coverage(result)

    result = helper.execute_program("~5")
    helper.expect_new_coverage(result)

    result = helper.execute_program("5%3")
    helper.expect_new_coverage(result)

    result = helper.execute_program("5**5")
    helper.expect_new_coverage(result)

    result = helper.execute_program("1<<20")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = 1; x += 4;")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = 5; x -= 2;")
    helper.expect_new_coverage(result)

    result = helper.execute_program("1048576>>16")
    helper.expect_new_coverage(result)

    result = helper.execute_program("18n")
    helper.expect_new_coverage(result)

    result = helper.execute_program('BigInt("20")')
    helper.expect_new_coverage(result)
    result = helper.execute_program('BigInt("20")')
    helper.assert_no_new_coverage(result)  # Hard requirement: Executing the same code twice should never return new coverage a 2nd time!

    result = helper.execute_program("try { throw 42; } catch { }")
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.sign(20)")  # function should return 1
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.sign(-30)")  # function should return -1
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.sign(-0)")  # function should return -0
    helper.expect_new_coverage(result)

    result = helper.execute_program("Math.sign(NaN)")  # function should return NaN
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Array(20)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = [];x[20] = 1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = [10];x[20] = 1")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var x = [];x[20] = 'test'")
    helper.expect_new_coverage(result)

    # Try the same again and check if they no new coverage is detected
    result = helper.execute_program("new Array(20)")
    helper.assert_no_new_coverage(result)
    result = helper.execute_program("var x = [];x[20] = 1")
    helper.assert_no_new_coverage(result)
    result = helper.execute_program("var x = [10];x[20] = 1")
    helper.assert_no_new_coverage(result)
    result = helper.execute_program("var x = [];x[20] = 'test'")
    helper.assert_no_new_coverage(result)

    # Now try it with different "data", e.g. index 19 instead of 20.
    # I EXPECT (not assert) that this should not lead to new coverage
    result = helper.execute_program("var x = [];x[19] = 1")
    helper.expect_no_new_coverage(result)
    result = helper.execute_program("var x = [10];x[19] = 1")
    helper.expect_no_new_coverage(result)
    result = helper.execute_program("var x = [];x[19] = 'test'")
    helper.expect_no_new_coverage(result)


    # Now some string functions
    result = helper.execute_program("var str = 'Hello World!'; var res = str.toLowerCase()")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var str = 'Hello World!'; var res = str.toUpperCase()")
    helper.expect_new_coverage(result)

    # Try it again with the *same* symbols but in a different order
    # I expect that this should change nothing and I should not find new coverage
    result = helper.execute_program("var str = 'olherlddw'; var res = str.toLowerCase()")
    helper.expect_no_new_coverage(result)
    result = helper.execute_program("var str = 'olherlddw'; var res = str.toUpperCase()")
    helper.expect_no_new_coverage(result)


    result = helper.execute_program("var str = 'Hey, welcome to the fuzzer.'; var n = str.indexOf('welcome')")
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "Find some 0days with fuzzilli.";var res = str.replace("fuzzilli", "JS Raider")')    # :)
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "Hello fuzzer"; var res = str.slice(0, 5)')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "Have you already found a 0day today?"; var res = str.split(" ")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "The rain in SPAIN stays mainly in the plain"; var res = str.match(/ain/g)')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "Hello fuzzer";var res = str.charAt(0)')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var str = "       Hello fuzzer!        ";print(str.trim())')
    helper.expect_new_coverage(result)


    # Some Math functions
    result = helper.execute_program("var y = Math.sqrt(16)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.exp(1)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.cosh(3)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.random()")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.ceil(1.4)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.round(1.4)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.round(1.99)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var y = Math.round(1.98)")
    helper.expect_no_new_coverage(result)

    result = helper.execute_program("JSON")
    helper.expect_new_coverage(result)

    result = helper.execute_program('var myObj = { "name":"John", "age":31, "city":"New York" }')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var myObj = { "name":"John", "age":31, "city":"New York" };var myJSON = JSON.stringify(myObj)')
    helper.expect_new_coverage(result)


    result = helper.execute_program("""var obj = JSON.parse('{"firstName":"John", "lastName":"Doe"}')""")
    helper.expect_new_coverage(result)

    result = helper.execute_program('escape("XYZ?!")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('parseInt("10")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('parseInt("010")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('parseInt("0x10")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('parseInt("10.33")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('parseInt("He was 40")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('isNaN(123)')
    helper.expect_new_coverage(result)

    result = helper.execute_program("isNaN('Hello')")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var n = Date.now()")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date().getMonth();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date().getDay();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date().getFullYear();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date().getTime();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date().getHours();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("new Date('01 01 2015');")
    helper.expect_new_coverage(result)

    # some array operations
    result = helper.execute_program('var hege = ["Cecilie", "Lone"];var stale = ["Emil", "Tobias", "Linus"];var children = hege.concat(stale);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"];var fk = fruits.keys();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"];var energy = fruits.join(" and ");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"]; var a = fruits.lastIndexOf("Apple");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var numbers = [175, 50, 25]; function myFunc(total, num) { return total - num; }; numbers.reduceRight(myFunc);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"]; fruits.shift();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Apple", "Orange", "Mango"]; fruits.shift();')
    helper.expect_no_new_coverage(result)   # order of 2 elements changed, it should not lead to new coverage

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"]; fruits.splice(2, 0, "Lemon", "Kiwi");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["apple", "orange", "cherry"];function myFunction(item, index) '
                                    '{print(index + ":" + item);} ; fruits.forEach(myFunction);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"]; fruits.pop();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.push("Cat");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.sort();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.reverse();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.sort();')
    helper.expect_no_new_coverage(result)
    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.reverse();')
    helper.expect_no_new_coverage(result)
    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Mango"]; fruits.shift();')
    helper.expect_no_new_coverage(result)

    result = helper.execute_program('var fruits = ["Banana", "Orange", "Apple", "Kiwi"]; fruits.filter(word => word.length > 4);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.map(x => x*2);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.indexOf(3);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.copyWithin(0, 1, 3);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.toString();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.join(",");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1,2,3,4,3]; x.valueOf();')
    helper.expect_new_coverage(result)

    # Some other stuff
    result = helper.execute_program('1 instanceof Array')
    helper.expect_new_coverage(result)

    result = helper.execute_program('class Vector extends Array {}')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = {xyz: 123}; x.xyz;')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = {xyz: 123}; delete x.xyz;')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = {xyz: 123}; typeof(x);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('if(true) { var x = 1};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('if(false) {} else { var x = 1};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('if(false) {} else if(true) { var x = 1} else {};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = 5 > 3 ? true : false;')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = 5; while(x >0) {--x;};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = 5; while(x >0) {--x; if(x==1) {break;}};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = 5; while(x >0) {--x; if(x==1) {continue;}};')
    helper.expect_new_coverage(result)

    result = helper.execute_program('function xyz() {return 1;};xyz();')
    helper.expect_new_coverage(result)

    result = helper.execute_program("function xyz() {\n'use strict';\nreturn 1;};xyz();")
    helper.expect_new_coverage(result)

    result = helper.execute_program("function xyz() { console.log(arguments.length);};xyz();")
    helper.expect_new_coverage(result)

    result = helper.execute_program('let xyz = () => console.log("foo");xyz();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let xyz = /abcde/;')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let xyz = /abcde/.test("abcdefghijkla");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Map(); x.set("foo", 3);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Map(); x.set("foo", 3);x.get("foo");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Map(); x.set("foo", 3);x.delete("foo"); x.get("foo");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Map(); x.set("foo", 3);x.clear(); x.get("foo");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Set(); x.add("foo"); x.add("foo");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = new Set(); x.add("foo"); x.add("foo");x.entries();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = [1,2,3,4,5]; let iterator = x.values(); iterator.next(); iterator.next();')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = [1,2,3,4,5]; for(let y in x) {console.log(y);}')
    helper.expect_new_coverage(result)

    result = helper.execute_program('function *generator() { yield 1; yield 2;}; let x = generator(); console.log(x.next().value); console.log(x.next().value);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('new Proxy({}, {set: function() {console.log(1);}}).xyz = "foobar";')
    helper.expect_new_coverage(result)

    result = helper.execute_program('new Proxy({}, {get: function() {console.log(1);}}).xyz;')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = 123; console.log(`Output ${x}`);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('String.raw`foo${2+3}bar`')
    helper.expect_new_coverage(result)

    result = helper.execute_program('Symbol("foobar");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = Symbol.for("xyz");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('let x = Symbol.for("xyz"); Symbol.keyFor(x);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('Object.is("foo", 5);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"5".repeat(30);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('Object.getOwnPropertySymbols({});')
    helper.expect_new_coverage(result)

    result = helper.execute_program('String.fromCodePoint(7631);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foo".codePointAt(1);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foobar".startsWith("bar",3);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foobar1".endsWith("r1");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foobar1".includes("xyz");')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"xxxx".normalize()')
    helper.expect_new_coverage(result)

    helper.execute_program("'réservé';")    # Make one execution to ensure that the next execution doesn't trigger new coverage because of the string
    result = helper.execute_program("'réservé'.localeCompare('RESERVE');")
    helper.expect_new_coverage(result)

    result = helper.execute_program("'réservé'.localeCompare('RESERVE','en', { sensitivity: 'base' });")
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foo".padEnd(25, ".")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"foo".padStart(5, "0")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"Test foobar 123 foobarxyz".replaceAll("foobar", "")')
    helper.expect_new_coverage(result)

    result = helper.execute_program('"Test foobar 123 foobarxyz".substring(4,8)')
    helper.expect_new_coverage(result)


    # Again some array operations:
    result = helper.execute_program('[1, 30, 39, 29, 10, 13].every((currentValue) => currentValue < 10)')
    helper.expect_new_coverage(result)

    result = helper.execute_program('var x = [1, 2, 3, 4]; x.fill(0, 2, 4);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('[5, 12, 8, 130, 44].find(element => element > 10)')
    helper.expect_new_coverage(result)

    result = helper.execute_program('[5, 12, 8, 130, 44].findIndex((element) => element > 13);')
    helper.expect_new_coverage(result)

    result = helper.execute_program('[0, 1, 2, [3, 4]].flat()')
    helper.expect_new_coverage(result)

    result = helper.execute_program('[1, 2, 3, 4].flatMap(x => [x, x * 2])')
    helper.expect_new_coverage(result)

    result = helper.execute_program("Array.from('foo')")
    helper.expect_new_coverage(result)

    result = helper.execute_program("Array.isArray([1, 2, 3]);")
    helper.expect_new_coverage(result)

    result = helper.execute_program("[1, 2, 3].unshift(4, 5)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("const buffer = new SharedArrayBuffer(16); const uint8 = new Uint8Array(buffer); uint8[0] = 7;")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.add(uint8, 0, 2);")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.load(uint8, 0);")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.and(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.compareExchange(uint8, 0, 5, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.exchange(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.or(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.store(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.sub(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("var buffer = new SharedArrayBuffer(16); var uint8 = new Uint8Array(buffer); uint8[0] = 7; Atomics.xor(uint8, 0, 2)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("Atomics.isLockFree(3)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("BigInt.asIntN(64, 2n)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("BigInt.asUintN(64, 4n)")
    helper.expect_new_coverage(result)

    result = helper.execute_program("encodeURI('https://mozilla.org/?x=шеллы')")
    helper.expect_new_coverage(result)

    result = helper.execute_program("decodeURI('https://mozilla.org/?x=%D1%88%D0%B5%D0%BB%D0%BB%D1%8B')")
    helper.expect_new_coverage(result)

    result = helper.execute_program("eval('2 + 2')")
    helper.expect_new_coverage(result)

    result = helper.execute_program("escape('äöü');")
    helper.expect_new_coverage(result)

    number_tests_correct = helper.get_expectations_correct()
    number_tests_wrong = helper.get_expectations_wrong()
    number_tests_total = number_tests_correct + number_tests_wrong
    success_rate = (float(number_tests_correct) / number_tests_total) * 100.0

    if number_tests_correct == number_tests_total:
        utils.msg("[+] Coverage quality feedback result: All %d performed tests were passed! Your coverage feedback looks good!" % number_tests_total)
    else:
        utils.msg("[!] Coverage quality feedback result: %d of %d tests were successful (%.2f %%)" % (number_tests_correct, number_tests_total, success_rate))


# All of these tests must work 100% to ensure the functionality is implemented correctly
def start_functional_tests():
    utils.msg("[i] Going to start functional tests (all tests must pass)...")
    helper.reset_stats()

    helper.restart_exec_engine()  # Start the tests with a restarted engine

    # Reload the "empty coverage map" to ensure that we start with a fresh coverage map
    # Which should be able to find new coverage
    cfg.exec_engine.load_global_coverage_map_from_file(cfg.coverage_map_testsuite)

    # Let's now also create an in-memory snapshot to later restore the "empty" coverage map:
    cfg.exec_engine.backup_global_coverage_map()

    # New Code => New Coverage should be found
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_new_coverage(result)

    # Code was executed already, so there should be no new coverage
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_no_new_coverage(result)

    # Same again, just a 2nd time to get sure
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_no_new_coverage(result)

    # Let's now restore the coverage map via the in-memory "snapshot"
    cfg.exec_engine.restore_global_coverage_map()

    # And now it should again find the new coverage
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_new_coverage(result)

    # And the 2nd time it should not find new coverage again (because it was already previously found)
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_no_new_coverage(result)

    # Try it one more time:
    cfg.exec_engine.restore_global_coverage_map()

    # And now it should again find the new coverage
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_new_coverage(result)


    # Now backup a state where the testcase was already seen
    cfg.exec_engine.backup_global_coverage_map()

    # obviously, it should again not find the new coverage
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_no_new_coverage(result)

    # Now try to restore the snapshot, in which the coverage was already seen
    cfg.exec_engine.restore_global_coverage_map()

    # Since a backup was created after the code was already seen, it should now don't detect new coverage
    result = helper.execute_program("var x = 1; print(x+x)")
    helper.assert_no_new_coverage(result)

    utils.msg("[+] SUCCESS: All %d performed functional tests worked as expected!" % helper.get_number_performed_tests())


def test_coverage_feedback():
    if cfg.fuzzer_arguments.disable_coverage is True:
        utils.msg("[!] Coverage tests can't be performed because coverage feedback is disabled! Skipping these tests...")
        return

    utils.msg("\n")
    utils.msg("[i] " + "-" * 100)
    utils.msg("[i] Going to start coverage feedback tests ...")
    utils.msg("[i] " + "-" * 100)
    start_functional_tests()
    utils.msg("[i] " + "-" * 100)
    start_coverage_feedback_quality_tests()
    utils.msg("[i] " + "-" * 100)
