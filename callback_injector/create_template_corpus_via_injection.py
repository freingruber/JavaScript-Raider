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

# TODO: This script is not refactored yet and not functional at the moment.
# A lot of function names and so on were also not updated, so the script will not work at the moment
# It's also important to mention that you currently should also not use the script because
# I didn't find a single vulnerability with this callback idea. The current code generates way
# too many template files which then has a negative impact on fuzzing.
# The code must first be refactored and then a method to detect "duplicates" must be added to reduce
# the number of generated template files. Then new JavaScript callback methods can be added and
# then it maybe starts to be an effective technique.

# This mode can be started by passing the "--create_template_corpus_via_injection" flag to the fuzzer.
#
# At the moment this is implemented as a "mode", but this will maybe change in the future.
# The script creates new template files by injecting callback functions into every testcase
# from the JavaScript corpus.
# This is done by calling create_template_corpus_via_injection() from this script



import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import os.path
import re
import hashlib
from native_code.executor import Execution_Status
import native_code.speed_optimized_functions as speed_optimized_functions
import config as cfg
import utils
import javascript.js_runtime_extraction_code as js_runtime_extraction_code
import javascript.js_helpers as js_helpers
import javascript.js as js

import testcase_helpers
import callback_injector.callback_injector_helpers as callback_injector_helpers

import testcase_state   # TODO the whole code passes function arguments which are also named "testcase_state" ...

result_code_of_last_execution = None
exec_engine = None

current_filename = None
output_template_corpus_dir = None
output_crash_dir = None


# I modify the number of variables in the current testcase state when I inject a new callback
# When injecting a callback using a different technique I want to start again with the variable IDs
# I therefore store the original number of variables in this global variable and after every execution
# i reset it in the state
backup_number_variables = None

# This variable just holds a reference to the testcase state and some functions modify the state
# e.g. increase the number of variables
# This variable is just used as a global reference to the state so that I don't need to pass
# the state object to every function
backup_testcase_state = None

# This is a copy of the current unmodified state. It's mainly used in the testcase state creation for a 
# new found template file.
backup_testcase_state_unmodified = None

backup_testcase_number_of_lines = 0

debug_stop = False

# The following variables will be loaded via a call to:
# load_globals()
class_methods = None
class_properties = None
class_not_accessible_properties = None
obj_methods = None
obj_properties = None
obj_not_accessible_properties = None


def create_template_corpus_via_injection(start_id=None, end_id=None):
    global exec_engine, current_filename, output_template_corpus_dir, output_crash_dir

    output_template_corpus_dir = cfg.fuzzer_arguments.corpus_template_files_dir
    output_crash_dir = cfg.output_dir_crashes
    exec_engine = cfg.exec_engine

    utils.msg("[i] Starting to create template corpus via injection...")

    utils.msg("[i] Output template corpus dir is at: %s" % output_template_corpus_dir)
    utils.msg("[i] Output crash dir is at: %s" % output_crash_dir)

    load_globals()

    if not os.path.exists(output_template_corpus_dir):
        os.makedirs(output_template_corpus_dir)

    if not os.path.exists(output_crash_dir):
        utils.perror("Error, output crash dir doesn't exist: %s" % output_crash_dir)

    problem_entries = temp_hack_remove_again()

    for entry in cfg.corpus_js_snippets.corpus_iterator():
        (content, state, filename) = entry

        if filename not in problem_entries:
            continue  # TODO remove again
        # testcase_id = int(filename[2:-3],10)
        # if testcase_id <= 11500 or testcase_id > 13500:
        #    continue

        # if filename != "tc3048.js": # tc1045.js
        #    continue    # debugging, remove again

        utils.msg("[i] Going to create templates for file: %s" % filename)
        # Set the global >current_filename< to the current file name because some sub functions
        # access this variable to know the output folder
        current_filename = filename

        output_directory = os.path.join(output_template_corpus_dir, current_filename)
        if os.path.exists(output_directory):
            continue  # already created file

        create_template_files_for_testcase(content, state)


def load_globals():
    global exec_engine, class_methods, class_properties, class_not_accessible_properties, obj_methods, obj_properties, obj_not_accessible_properties
    utils.msg("[i] Going to load globals...")
    (class_methods, class_properties,
        class_not_accessible_properties,
        obj_methods,
        obj_properties,
        obj_not_accessible_properties) = js_runtime_extraction_code.extract_data_of_all_globals(exec_engine)
    utils.msg("[+] Finished loading globals")

    # Debugging code
    # print("class_methods:")
    # print(class_methods["BigInt"])
    # print("class_properties:")
    # print(class_properties["BigInt"])
    # print("class_not_accessible_properties:")
    # print(class_not_accessible_properties["BigInt"])
    # print("obj_methods:")
    # print(obj_methods["BigInt"])
    # print("obj_properties:")
    # print(obj_properties["BigInt"])
    # print("obj_not_accessible_properties:")
    # print(obj_not_accessible_properties["BigInt"])
    # print("End of load_global(), stopping...")
    # sys.exit(-1)



def get_proxy_handler(proxy_handler_number, proxy_handler_number_to_return_via_construct, testcase_state, className, should_fix_function_getters=True):
    global class_methods, class_properties, class_not_accessible_properties, obj_methods, obj_properties

    code_to_print_identifier = get_js_print_identifier()

    current_variable_id = testcase_state.number_variables
    current_variable_id += 1
    args_variable_name = "var_%d_" % current_variable_id

    current_variable_id += 1
    arg_target_obj = "var_%d_" % current_variable_id
    
    current_variable_id += 1
    arg_two = "var_%d_" % current_variable_id

    current_variable_id += 1
    arg_three = "var_%d_" % current_variable_id

    current_variable_id += 1
    arg_four = "var_%d_" % current_variable_id

    current_variable_id += 1
    arg_old_obj = "var_%d_" % current_variable_id

    testcase_state.number_variables = current_variable_id

    if proxy_handler_number == proxy_handler_number_to_return_via_construct:
        code_to_create_construct_proxy = "new Proxy(newTarget, proxyhandler%d);" % proxy_handler_number
    else:
        code_to_create_construct_proxy = "get_proxy%d(newTarget);" % proxy_handler_number_to_return_via_construct

    proxy_get_additional_code = ""
    proxy_initial_functions = ""
    proxy_set_additional_code = ""

    if should_fix_function_getters and className in class_methods:
        func_number = 0
        all_methods = set()
        if className in class_methods:
            all_methods |= class_methods[className]
        if className in obj_methods:
            all_methods |= obj_methods[className]
        all_properties = set()
        if className in class_properties:
            all_properties |= class_properties[className]
        if className in class_not_accessible_properties:
            all_properties |= class_not_accessible_properties[className]
        if className in obj_properties:
            all_properties |= obj_properties[className]

        all_properties = all_properties - all_methods
        for method_name in all_methods:
            func_number += 1
            proxy_get_additional_code += """
            if(__arg_two__ == "__method_name__") {
                %s;
                return handler_proxy__proxy_number___function__func_number__;
            }""".replace("__arg_two__", arg_two).replace("__method_name__", method_name).replace("__func_number__", str(func_number)).replace("__proxy_number__", str(proxy_handler_number)).replace("%s", code_to_print_identifier)

            proxy_initial_functions += """
function handler_proxy__proxy_number___function__func_number__(...args) {
    %s;
    let __arg_variable_name__ = oldObj__proxy_number__["__method_name__"](...args);
    %s;
    return __arg_variable_name__;
}""".replace("__arg_variable_name__", args_variable_name).replace("__method_name__", method_name).replace("__func_number__", str(func_number)).replace("__proxy_number__", str(proxy_handler_number)).replace("%s", code_to_print_identifier)

            proxy_set_additional_code += """
            if(__arg_two__ == "__method_name__") {//handler_proxy
                %s;
            }""".replace("__arg_two__", arg_two).replace("__method_name__", method_name).replace("%s", code_to_print_identifier)


        for property_name in all_properties:
            # Important: Don't remove the "//handler_proxy" comment in the next code
            # If the code would not be execute it would be replaced with a _NOT_REACHED_ label
            # However, I want to remove it because otherwise the testcase would become very big
            # Typically I only remove full functions and not "if statements"
            # If I would remove an if-branch it could lead to a problem because then the "else" part
            # can be there without a previous "if" part.
            # However, I made an exception and still remove the "if" branch when inside the code the
            # string "handler_proxy" can be found. It's therefore important that this comment stays there
            # I later remove the comment before the testcase is stored in the corpus
            proxy_get_additional_code += """
            if(__arg_two__ == "__property_name__") {//handler_proxy
                %s;
            }""".replace("__arg_two__", arg_two).replace("__property_name__", property_name).replace("%s", code_to_print_identifier)

            proxy_set_additional_code += """
            if(__arg_two__ == "__property_name__") {//handler_proxy
                %s;
            }""".replace("__arg_two__", arg_two).replace("__property_name__", property_name).replace("%s", code_to_print_identifier)


    tmp = """var oldObj__proxy_number__ = undefined;__proxy_initial_functions__
function get_proxy__proxy_number__(__arg_old_obj__) {
    oldObj__proxy_number__ = __arg_old_obj__;
    let proxyhandler__proxy_number__ = {
        get: function(__arg_target_obj__,__arg_two__, __arg_three__) {
            %s;
            let __arg_variable_name__ = Reflect.get(__arg_target_obj__, __arg_two__, __arg_three__);
            %s;__proxy_get_additional_code__
            return __arg_variable_name__;
        },
        set: function(__arg_target_obj__, __arg_two__, __arg_three__, __arg_four__) {
            %s;__proxy_set_additional_code__
            let __arg_variable_name__ = Reflect.set(__arg_target_obj__, __arg_two__, __arg_three__, __arg_four__);
            %s;
            return __arg_variable_name__;
        },
        deleteProperty: function(__arg_target_obj__, __arg_two__) {
            %s;
            let __arg_variable_name__ = Reflect.deleteProperty(__arg_target_obj__, __arg_two__);
            %s;
            return __arg_variable_name__;
        },
        ownKeys: function (__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Reflect.ownKeys(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
        has: function (__arg_target_obj__, __arg_two__) {
            %s;
            let __arg_variable_name__ = __arg_two__ in __arg_target_obj__;
            %s;
            return __arg_variable_name__;
        },
        defineProperty: function (__arg_target_obj__, __arg_two__, __arg_three__) {
            %s;
            let __arg_variable_name__ = Reflect.defineProperty(__arg_target_obj__, __arg_two__, __arg_three__);
            %s;
            return __arg_variable_name__;
        },
        isExtensible: function (__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Reflect.isExtensible(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
        preventExtensions:  function (__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Reflect.preventExtensions(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
        apply: function(__arg_target_obj__, __arg_two__, __arg_three__) {
            %s;
            let __arg_variable_name__ = Reflect.apply(__arg_target_obj__, __arg_two__, __arg_three__);
            %s;
            return __arg_variable_name__;
        },
        construct: function(__arg_target_obj__, __arg_two__) {
            %s;
            let newTarget = new __arg_target_obj__(...__arg_two__);
            %s;
            let __arg_variable_name__ = __code_to_create_construct_proxy__
            %s;
            return __arg_variable_name__;
        },
        getOwnPropertyDescriptor: function(__arg_target_obj__, __arg_two__) {
            %s;
            let __arg_variable_name__ = Object.getOwnPropertyDescriptor(__arg_target_obj__, __arg_two__);
            %s;
            return __arg_variable_name__;
        },
        getPropertyDescriptor: function(__arg_target_obj__, __arg_two__) {
            %s;
            let __arg_variable_name__ = Object.getPropertyDescriptor(__arg_target_obj__, __arg_two__);
            %s;
            return __arg_variable_name__;
        },
        getPrototypeOf: function(__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Reflect.getPrototypeOf(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
        setPrototypeOf: function(__arg_target_obj__, __arg_two__) {
            %s;
            let __arg_variable_name__ = Reflect.setPrototypeOf(__arg_target_obj__, __arg_two__);
            %s;
            return __arg_variable_name__;
        },
        getOwnPropertyNames: function(__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Object.getOwnPropertyNames(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
        getPropertyNames: function(__arg_target_obj__) {
            %s;
            let __arg_variable_name__ = Object.getPropertyNames(__arg_target_obj__);
            %s;
            return __arg_variable_name__;
        },
    };
    return new Proxy(oldObj__proxy_number__, proxyhandler__proxy_number__);
}
""".replace("__proxy_number__", str(proxy_handler_number)).replace("__arg_variable_name__", args_variable_name).replace("__arg_target_obj__", arg_target_obj).replace("__arg_two__", arg_two).replace("__arg_three__", arg_three).replace("__arg_four__", arg_four).replace("%s", code_to_print_identifier).replace("__arg_old_obj__", arg_old_obj).replace("__code_to_create_construct_proxy__", code_to_create_construct_proxy).replace("__proxy_get_additional_code__", proxy_get_additional_code).replace("__proxy_initial_functions__", proxy_initial_functions).replace("__proxy_set_additional_code__", proxy_set_additional_code)

    return tmp


def replace_sub_parts(content, search_start, search_end, new_start, new_end):
    original_content = content
    dummy_str_start = "__REPLACE_START__ "      # important, they must end with a space so that the later check char_before.isalnum() returns false. otherwise stuff like [[]] would not work
    dummy_str_end = "__REPLACE_END__ "          # important, they must end with a space so that the later check char_before.isalnum() returns false. otherwise stuff like [[]] would not work
    # E.g.: [1,2,3] to: new Array(1,2,3)
    # search_start would be: [
    # search_end would be: ]
    # new_start would be: new Array(
    # new_end would be )

    new_start = new_start.replace(search_start, dummy_str_start).replace(search_end, dummy_str_end)
    new_end = new_end.replace(search_start, dummy_str_start).replace(search_end, dummy_str_end)

    while True:
        # print("START CONTENT:")
        # print(content)
        # print("SEARCH START:")
        # print(search_start)
        idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content, search_start)
        # print("idx: %d" % idx)
        # print("len: %d" % len(content))
        if idx == -1:
            break
        char_before = content[idx-1]
        content_before = content[:idx]      # without the "["
        content_rest = content[idx+len(search_start):]  # this is without the "["
        
        if char_before.isalnum() or char_before == "_" or char_before == "$" or char_before == "/":
            # Then this is not a new declaration like: let x = [1,2,3]
            # Instead it's an access like x[1]

            # the "/" check ensures that RegEx strings are detected. E.g.:
            # /z/[Symbol.search]('a') == -1;
            # In this case the "[" can't be changed to a new Array...
            content = content_before + dummy_str_start + content_rest
            # we replace the "[" with "__REPLACE__" so that it's not found again
            # in the end I change it back
            continue

        test = content_before.strip().lower()
        if test.endswith(")") or test.endswith("else") or test.endswith("catch") or test.endswith("finally"):
            content = content_before + dummy_str_start + content_rest
            continue

        test2 = content_rest.split("\n")[0].replace("==", "someThingDifferent")
        if "=" in test2:
            # This means it's on the left side of an assigned and "new .." is therefore not valid
            # For example consider this code:
            # 0, [arguments] = [];
            # After processing it would result in:
            # 0, new Array([arguments]) = new Array([]);
            # which is incorrect and leads to an exception
            # This check here ensures that the following code is generated:
            # 0, [arguments] = new Array([]);
            # print("TODO2 analyse this with more testcases")

            # TODO: This is sometimes wrong...
            # Consider this testcase:
            # "".match(/(?:(?=a)b){5}abcde/);
            # The first "" would not be replaced with "new String("")"
            # because there is a "=" in the right middle in the "(?=a)" code
            # And because of the "=" symbol it thinks it's an assignment...
            # I would need to add code to also parse strings/regex strings here....
            # This is currently not supported
            content = content_before + dummy_str_start + content_rest
            continue
        elif " in " in test2 or " of " in test2:
            # code like:
            # for ([arguments] in [[]]) ;
            # would become:
            # for (new Array([arguments]) in new Array([[])]) ;
            # This code here prevents this and ensures that only this code gets generated:
            # for ([arguments] in new Array([new Array([])])) ;

            # Same applies to:
            # for ([arguments] of [[]]) ;
            # print("TODO3 analyse this with more testcases")
            content = content_before + dummy_str_start + content_rest
            continue

        test3 = test.split("\n")[-1]
        if "function func_" in test3:
            # it's a function declaration and therefore "new.." is not possible
            # for example:
            # function func_1_([])
            # =>
            # function func_1_(new Array([])) 
            # which is invalid code. This code here prevent this modification
            # print("TODO2 ANALYZE IN DEPTH WITH MORE SAMPLES!!!!")
            content = content_before + dummy_str_start + content_rest
            continue

        # print("Content rest:")
        # print(content_rest)
        # print("-----------")
        # print("Search end: %s" % search_end)
        idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(content_rest, search_end)
        # print("idx2: %d" % idx2)
        if idx2 == -1:
            if search_end == search_start:
                break
            content = content_before + dummy_str_start + content_rest
            continue
        argument_to_array = content_rest[:idx2]     # without the "]"
        content_after = content_rest[idx2+len(search_end):]   # without the "]"
        content = content_before + new_start + argument_to_array + new_end + content_after

    new_content = content.replace(dummy_str_start, search_start).replace(dummy_str_end, search_end)

    result = execute_safe_wrapper(new_content)
    if result.status == Execution_Status.SUCCESS:
        return new_content
    else:
        # print("Incorrect!")
        # print("Before:")
        # print(original_content)
        # print("after:")
        # print(new_content)
        # print("---------")
        return original_content     # Return not modified content because it seems it introduced problems


def replace_str_with_other_str(content, str_to_replace, new_str):
    new_content = content.replace(str_to_replace, new_str)
    if new_content == content:
        # print("skip execution")
        return content  # nothing was modified and an execution is therefore not required

    result = execute_safe_wrapper(new_content)
    if result.status == Execution_Status.SUCCESS:
        return new_content
    else:
        # This is a small hack here
        utils.msg("[i] first failed")
        # This can happen, for example:
        # var cond = false; if (cond) {alert("test");}
        # Now if the modification happens this code would be generated:
        # var cond = new Boolean(false); if (cond) {alert("test");}
        # BUT: Now the test-string is alerted! Because the logic was modified because "new Boolean(false)" evaluates to true
        # To solve this problem the .valueOf() call can be used:
        # var cond = new Boolean(false); if (cond.valueOf()) {alert("test");}

        # Please note: I don't want to always inject the valueOf() call because typically valueOf() is automatically called
        # e.g. if later operations are performed on the Boolean value it would be called.
        # That means the callbacks would trigger later what is what I want to achieve in the fuzzer
        # Immediately calling valueOf() is just the backup plan...
        new_content = content.replace(str_to_replace, new_str + ".valueOf()")
        result = execute_safe_wrapper(new_content)
        if result.status == Execution_Status.SUCCESS:
            return new_content
        else:
            utils.msg("[i] Incorrect Replace!")
            utils.msg("[i] Before:")
            utils.msg("[i] " + content)
            utils.msg("[i] after:")
            utils.msg("[i] " + new_content)
            utils.msg("[i] ---------")
            return content     # Return not modified content because it seems it introduced problems



def check_if_correct_replacement_position(content_search, substr_to_replace):
    if substr_to_replace not in content_search:
        return False    # It means it was already previously replaced
    idx = content_search.index(substr_to_replace)
    if(idx == -1):
        utils.perror("Logic flow in check_if_correct_replacement_position()")
    char_before = content_search[idx-1]
    try:
        char_after = content_search[idx+len(substr_to_replace)]
    except:
        char_after = " "    # could happen if "substr_to_replace" is at the end of the testcase
    # print("Char before: %s" % char_before)
    # print("Char after: %s" % char_after)
    
    content_before = content_search[:idx]
    if content_before.endswith("BigInt(") or content_before.endswith("Number(") or content_before.endswith("RegExp("):
        return False    # don't create stuff like "new Number(new Number(1337))"

    if char_after.isalnum() or char_after == "_":
        return False
    if char_before.isalnum() or char_before == "_":
        return False
    return True


def replace_number_substring(content_search, content_search2, content_new, substr_to_replace, new_str):
    if substr_to_replace not in content_search:
        utils.perror("Logic flaw in replace_number_substring()")

    idx1 = content_search.index(substr_to_replace)
    if idx1 == -1:
        utils.perror("Logic2 flaw in replace_number_substring()")
    
    fake_new_str = "a" * len(new_str)   # this ensures that later iterations do not detect the number again
    
    # tmp_content_new = content_new.replace(substr_to_replace, new_str, 1)
    tmp_content_new = content_new[:idx1] + new_str + content_new[idx1+len(substr_to_replace):]
    # print("tmp_content_new:")
    # print(tmp_content_new)
    # print("------------------")
    result = execute_safe_wrapper(tmp_content_new)
    if result.status == Execution_Status.SUCCESS:
        #print("success")
        tmp_content_search = content_search[:idx1] + fake_new_str + content_search[idx1+len(substr_to_replace):]
        tmp_content_search2 = content_search2[:idx1] + fake_new_str + content_search2[idx1+len(substr_to_replace):]
        return tmp_content_search, tmp_content_search2, tmp_content_new
    else:
        # print("not success")
        # It was an incorrect replacement
        # So return the original content, however, mark the search string so that the substr is not found again in the same loop
        # e.g. the BigInt loop should not find it again. This is required because if for example "18n" occurs twice in a testcase
        # the second "18n" match would need to find the second "18n" and not the first. Therefore I replace the first "18n" with "aaa"
        # However, in the next loop it needs to be found again. For example:
        # 18-12
        # In the first loop which checks for negative numbers it could find "-12", but that is incorrect
        # Therefore the second loop (which checks for positive numbers) must find "12" again.
        # That's why I'm using two "content_search" variables here
        tmp_content_search = content_search[:idx1] + fake_new_str + content_search[idx1+len(substr_to_replace):]
        # note: "content_search2" is not modified here!
        return content_search, content_search2, content_new   # return the unmodified "content_new"


def replace_numbers(content):
    # Currently I don't handle numbers like: 123e5 or 123e-5;
    # I also don't handle octal numbers yet
    # However, I don't think they are really important

    # Test regex strings at: https://regexr.com/

    content_search = content
    content_search2 = content
    content_new = content

    # print("Negative BigInts:")
    matches = re.findall(r"[-]{1}[\d]+n", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new BigInt(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"

    # print("Positive BigInts:")
    matches = re.findall(r"[\d]+n", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new BigInt(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"

    # print("Negative hex numbers:")
    matches = re.findall(r"[-]{1}0[xX][0-9a-fA-F]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"


    # print("Positive hex numbers:")
    matches = re.findall(r"0[xX][0-9a-fA-F]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"


    # print("Negative binary numbers:")
    matches = re.findall(r"[-]{1}0[bB][0-1]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"


    # print("Positive binary numbers:")
    matches = re.findall(r"0[bB][0-1]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"


    # print("Negative numbers:")
    # Find all negative numbers
    matches = re.findall(r"[-]{1}[\d]*[.]{0,1}[\d]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"


    # print("Positive numbers:")
    matches = re.findall(r"[\d]*[.]{0,1}[\d]+", content)
    for matched_str in matches:
        # print(matched_str)
        if check_if_correct_replacement_position(content_search, matched_str):
            new_str = "new Number(%s)" % matched_str
            (content_search, content_search2, content_new) = replace_number_substring(content_search, content_search2, content_new, matched_str, new_str)
    content_search = content_search2    # this resets the variable. This ensures that incorrect entries in this loop can be found again in the next loop. E.g.: "18n-12n" where "-12n" was incorrectly found. Next loop can now find agian "12n"

    return content_new


def rewrite_testcase_to_use_new(content, testcase_state):
    global exec_engine

    # Important: I need to change it to "new Array([/**/]);"" and not to "new Array(/**/);"
    # Otherwise stuff like [1,2,,3] would not work
    # Same applies to objects because "new Object({next:123});" is valid but "new Object(next:123);" would not
    # Change arrays:
    content = replace_sub_parts(content, "[", "]", "new Array([", "])")
    
    # Do not modify objects: This is currently not working and very complex
    # For example, "{" is also the start block if if/while/try ... blocks
    # They can be filtered but the real problem is that the object syntax is different
    # for example: {property: 123} is valid but "new Object(property:123)" is not
    # It would therefore require a lot of engineering to change this and therefore I'm currently not doing it
    # DONT COMMENT IN: CURRENTLY NOT WORKING!
    # content = replace_sub_parts(content, "{", "}", "new Object({", "})")

    # Strings
    content = replace_sub_parts(content, '"', '"', "new String(\"", "\")")
    content = replace_sub_parts(content, "'", "'", "new String('", "')")
    content = replace_sub_parts(content, "`", "`", "new String(`", "`)")

    # It should be safe to do the following replacements because words like "true" should
    # not occur somewhere else. E.g. not in function names or variable names because
    # all functions and variables were renamed! It can only occur in strings
    # class properties or within the name of default functions
    # Currently I ignore these cases because the code already checks if an exception occurs, so it
    # should be safe to do these modifications

    content = replace_str_with_other_str(content, "true", "new Boolean(true)")
    content = replace_str_with_other_str(content, "false", "new Boolean(false)")

    numbers_to_replace = ["Number.EPSILON",
                          "Number.MAX_VALUE",
                          "Number.MIN_VALUE",
                          "Math.E",
                          "Math.E",
                          "Math.LN10",
                          "Math.LOG2E",
                          "Number.POSITIVE_INFINITY",
                          "Number.NEGATIVE_INFINITY",
                          "NaN",
                          "Infinity",
                          "Number.MAX_SAFE_INTEGER",
                          "Number.MIN_SAFE_INTEGER",
                          "Math.PI"]
    for number_to_replace in numbers_to_replace:
        new_str = "new Number(%s)" % number_to_replace
        content = replace_str_with_other_str(content, number_to_replace, new_str)
    # content = replace_str_with_other_str(content, "NaN", "new Number(NaN)")

    content = replace_numbers(content)

    # Now grep for RegExp strings:
    # RegExp:
    # var re = /hi/g;
    # =>
    # var re = new RegExp("hi", "g");
    content_search = content
    matches = re.findall(r"\/.*?\/[gimy]{0,1}", content)
    for matched_str in matches:
        if check_if_correct_replacement_position(content_search, matched_str):
            tmp_str = matched_str[1:]   # remove first "/"
            if tmp_str[-1] == "/":
                tmp_str = tmp_str[:-1]  # remove the last "/"
                new_str = "new RegExp(\"%s\")" % tmp_str
            else:
                second_arg = tmp_str[-1]
                tmp_str = tmp_str[:-2]  # removes something like /i or /g
                new_str = "new RegExp(\"%s\", \"%s\")" % (tmp_str, second_arg)
            
            
            idx = content_search.index(matched_str)
            tmp_content_new = content[:idx] + new_str + content[idx+len(matched_str):]

            new_str_search = "a" * len(new_str)
            tmp_content_search = content_search[:idx] + new_str_search + content_search[idx+len(matched_str):]
            content_search = tmp_content_search

            result = execute_safe_wrapper(tmp_content_new)
            if result.status == Execution_Status.SUCCESS:
                content = tmp_content_new   # just set it when replacement was successful


    content = "\n" + content    # this ensures that the following logic also works when the testcase starts with "new ..."
    while "\nnew " in content:
        idx = content.index("\nnew ") + 1
        code_before = content[:idx]

        code_after = content[idx:]
        if "." not in code_after:
            break   # fixing the new with "new\t" and doing a "continue" is useless because there would also be no "." for the next iteration
        idx2 = code_after.index(".")
        code_which_creates_object = code_after[:idx2]

        current_variable_id = testcase_state.number_variables
        current_variable_id += 1
        next_variable_name = "var_%d_" % current_variable_id
        testcase_state.number_variables = current_variable_id

        code_at_end = code_after[idx2:]
        content_tmp = code_before + "var "+next_variable_name+" = " + code_which_creates_object + ";"+next_variable_name + code_at_end
        result = execute_safe_wrapper(content_tmp)
        if result.status == Execution_Status.SUCCESS:
            content = content_tmp
        else:
            content = content.replace("\nnew ", "\nnew\t", 1)   # dont modify but ensure that it's not found again in next iteration
    if content[0] == "\n":
        content = content[1:]   # remove the added newline again

    # print("New content:")
    # print(content)
    return content  # Return the modified content





def get_subclass_code(className, testcase_state, redefineSymbols, exception_safe, is_native_type):
    code_to_print_identifier = get_js_print_identifier()

    new_class_name = "cl_%d_" % (testcase_state.number_classes+1)
    current_variable_id = testcase_state.number_variables

    current_variable_id += 1
    args_variable_name = "var_%d_" % current_variable_id

    if exception_safe:
        exception_code_start = "\n            try{"
        exception_code_end = """\n            }
            finally { 
                """+code_to_print_identifier+""";
                return null;
            }"""
    else:
        exception_code_start = ""
        exception_code_end = ""

    prefix_code = "class "+new_class_name+" extends "+className+" {\n"

    # Add the constructor
    if is_native_type:
        # for example BigInt needs a different constructor
        prefix_code += """    constructor(...__arg_variable_name__) {
        let self = Object(__class_name__(...__arg_variable_name__));
        Object.setPrototypeOf(self, __new_class_name__.prototype);
        %s;
        return self;
    }
""".replace("%s", code_to_print_identifier).replace("__arg_variable_name__", args_variable_name).replace("__new_class_name__", new_class_name).replace("__class_name__", className)
    else:
        prefix_code += """    constructor(...__arg_variable_name__) {
        super(...__arg_variable_name__);
        %s;
    }
""".replace("%s", code_to_print_identifier).replace("__arg_variable_name__", args_variable_name)


    # Contains already implemented functions/properties or properties which are not allowed to redefine
    already_implemented = ["constructor", "prototype"]

    # First add object methods
    if className in obj_methods:
        for func_name in obj_methods[className]:
            if func_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    __func_name__(...__arg_variable_name__) {
            %s;__exception_code_start__
            let __variable_name__ = super.__func_name__(...__arg_variable_name__);
            %s;
            return __variable_name__;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__func_name__", func_name).replace("__variable_name__", next_variable_name).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end).replace("__arg_variable_name__", args_variable_name)
        already_implemented += obj_methods[className]

    # Now add setter/getter for properties
    if className in obj_properties:
        for prop_name in obj_properties[className]:
            if prop_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    get ["__property_name__"]() {
            %s;__exception_code_start__
            let __variable_name__ = super["__property_name__"]; 
            %s;
            return __variable_name__;__exception_code_end__
    }
    set ["__property_name__"](value) {
            %s;__exception_code_start__
            super["__property_name__"] = value; 
            %s;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__property_name__", prop_name).replace("__variable_name__", next_variable_name).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end)
        already_implemented += obj_properties[className]


    # Now for not accessible properties (they can still be set but not read!)
    # But i think i can still overwrite the getter, it's just not called because the property is never read
    if className in obj_not_accessible_properties:
        for prop_name in obj_not_accessible_properties[className]:
            if prop_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    get ["__property_name__"]() {
            %s;__exception_code_start__
            let __variable_name__ = super["__property_name__"]; 
            %s;
            return __variable_name__;__exception_code_end__
    }
    set ["__property_name__"](value) {
            %s;__exception_code_start__
            super["__property_name__"] = value; 
            %s;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__property_name__", prop_name).replace("__variable_name__", next_variable_name).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end)
        already_implemented += obj_not_accessible_properties[className]

    # Now the static methods
    if className in class_methods:
        for func_name in class_methods[className]:
            if func_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    static __func_name__(...__arg_variable_name__) {
            %s;__exception_code_start__
            let __variable_name__ = __class_name__.__func_name__(...__arg_variable_name__);
            %s;
            return __variable_name__;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__func_name__", func_name).replace("__variable_name__", next_variable_name).replace("__class_name__", className).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end).replace("__arg_variable_name__", args_variable_name)
        already_implemented += class_methods[className]

    # Now the static properties
    if className in class_properties:
        for prop_name in class_properties[className]:
            if prop_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    static get ["__property_name__"]() {
            %s;__exception_code_start__
            let __variable_name__ = __class_name__["__property_name__"]; 
            %s;
            return __variable_name__;__exception_code_end__
    }
    static set ["__property_name__"](value) {
            %s;__exception_code_start__
            __class_name__["__property_name__"] = value; 
            %s;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__property_name__", prop_name).replace("__variable_name__", next_variable_name).replace("__class_name__", className).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end)
        already_implemented += class_properties[className]

    # Now static not accessible properties
    if className in class_not_accessible_properties:
        for prop_name in class_not_accessible_properties[className]:
            if prop_name in already_implemented:
                continue
            current_variable_id += 1
            next_variable_name = "var_%d_" % current_variable_id
            prefix_code += """    static get ["__property_name__"]() {
            %s;__exception_code_start__
            let __variable_name__ = __class_name__["__property_name__"]; 
            %s;
            return __variable_name__;__exception_code_end__
    }
    static set ["__property_name__"](value) {
            %s;__exception_code_start__
            __class_name__["__property_name__"] = value; 
            %s;__exception_code_end__
    }
""".replace("%s", code_to_print_identifier).replace("__property_name__", prop_name).replace("__variable_name__", next_variable_name).replace("__class_name__", className).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end)
        already_implemented += class_not_accessible_properties[className]


    if redefineSymbols:
        current_variable_id += 1
        next_variable_name = "var_%d_" % current_variable_id
        prefix_code += """    static get [Symbol.species]() {
            %s;
            return __class_name__;
    }
    *[Symbol.iterator]() {
            %s;
            let it = this.__proto__.__proto__[Symbol.iterator].call(this);
            let result = it.next();
            %s;
            while (!result.done) {
                let __variable_name__ = result.value;
                %s;
                yield __variable_name__;
                result = it.next();
                %s;
            }
            %s;
    }
    [Symbol.toPrimitive](__arg_variable_name__) { 
        %s;\n            try{
            if(this.__proto__.__proto__[Symbol.toPrimitive] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.toPrimitive].call(__arg_variable_name__);
                %s;
                return __variable_name__;
            }\n            }
            finally { 
                %s;
                if(__arg_variable_name__ == "number") {
                    %s;
                    return this["valueOf"]();
                }
                else if (__arg_variable_name__ == "string" || __arg_variable_name__ == "default") {
                    %s;
                    return this["toString"]();
                }
                else {
                    %s;
                    return null;
                }
            }
    }
    [Symbol.hasInstance](...__arg_variable_name__) { 
        %s;__exception_code_start__
            if(this.__proto__.__proto__[Symbol.hasInstance] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.hasInstance].call(...__arg_variable_name__);
                %s;
                return __variable_name__;
            }__exception_code_end__
    }
	static [Symbol.hasInstance](...__arg_variable_name__) {
        %s;__exception_code_start__
            if(super.__proto__[Symbol.hasInstance] != undefined) {
                let __variable_name__ =  super.__proto__[Symbol.hasInstance](...__arg_variable_name__);
                %s;
                return __variable_name__;
            }__exception_code_end__
    }
    [Symbol.replace](...__arg_variable_name__) {
		%s;__exception_code_start__
            if(this.__proto__.__proto__[Symbol.replace] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.replace].call(...__arg_variable_name__);
                %s;
                return __variable_name__;
            }__exception_code_end__
	}
	[Symbol.search](...__arg_variable_name__) {
		%s;__exception_code_start__
            if(this.__proto__.__proto__[Symbol.search] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.search].call(...__arg_variable_name__);
                %s;
                return __variable_name__;
            }__exception_code_end__
	}
    [Symbol.split](...__arg_variable_name__) {
		%s;__exception_code_start__
            if(this.__proto__.__proto__[Symbol.split] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.split].call(...__arg_variable_name__);
                %s;
                return __variable_name__;
            }__exception_code_end__
	}
    get [Symbol.toStringTag]() {
        %s;__exception_code_start__
            if(this.__proto__.__proto__[Symbol.toStringTag] != undefined) {
                let __variable_name__ = this.__proto__.__proto__[Symbol.toStringTag];
                %s;
                return __variable_name__;
            }__exception_code_end__
	}
    *[Symbol.matchAll](...__arg_variable_name__) {
			%s;
            let it = this.__proto__.__proto__[Symbol.matchAll].call(this, ...__arg_variable_name__);
            let result = it.next();
            %s;
            while (!result.done) {
                let __variable_name__ = result.value;
                %s;
                yield __variable_name__;
                result = it.next();
                %s;
            }
            %s;
	}
    async* [Symbol.asyncIterator](...__arg_variable_name__) {
		%s;
            let it = this.__proto__.__proto__[Symbol.asyncIterator].call(this, ...__arg_variable_name__);
            let result = it.next();
            %s;
            while (!result.done) {
                let __variable_name__ = result.value;
                %s;
                yield __variable_name__;
                result = it.next();
                %s;
            }
            %s;
	}
""".replace("%s", code_to_print_identifier).replace("__class_name__", className).replace("__variable_name__", next_variable_name).replace("__exception_code_start__", exception_code_start).replace("__exception_code_end__", exception_code_end).replace("__arg_variable_name__", args_variable_name)
    

    prefix_code += "}\n"    # end the class
    new_allocate_code = "new " + new_class_name

    testcase_state.number_variables = current_variable_id
    return prefix_code, new_allocate_code


def extract_offsets(testcase_content, base_offset=0):
    offsets_to_patch = []
    offsets_to_proxy = []

    # First iterate through the file and check 
    current_idx = 0
    last_idx = len(testcase_content) - 1
    previous_char = None
    while current_idx <= last_idx:
        current_char = testcase_content[current_idx]
        # print("Current idx: %d and char: %s" % (current_idx, current_char))
        current_content_start = testcase_content[current_idx:]

        if current_content_start.startswith("true"):
            idx_end = current_idx + len("true") - 1
            previous_content = "true"
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))
            current_idx = idx_end + 1
            previous_char = 'e'
        elif current_content_start.startswith("false"):
            idx_end = current_idx + len("false") - 1
            previous_content = "false"
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))
            current_idx = idx_end + 1
            previous_char = 'e'
        elif current_content_start.startswith("null"):
            idx_end = current_idx + len("null") - 1
            previous_content = "null"
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))
            current_idx = idx_end + 1
            previous_char = 'l'
        elif current_content_start.startswith("undefined"):
            idx_end = current_idx + len("undefined") - 1
            previous_content = "undefined"
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))
            current_idx = idx_end + 1
            previous_char = 'd'
        elif current_content_start.startswith("new "):
            rest = testcase_content[current_idx:]
            # print("Rest:")
            # print(rest)
            # print("--------------")
            idx_coma = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ',')
            idx_semicolon = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ';')
            idx_tmp1 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ']')
            idx_tmp2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, ')')

            idx_1 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, '(')

            idx_next = 99999999
            prev_char = ""
            if idx_coma < idx_next and idx_coma != -1:
                idx_next = idx_coma
                prev_char = ","
            if idx_semicolon < idx_next and idx_semicolon != -1:
                idx_next = idx_semicolon
                prev_char = ";"
            if idx_tmp1 < idx_next and idx_tmp1 != -1:
                idx_next = idx_tmp1
                prev_char = "]"
            if idx_tmp2 < idx_next and idx_tmp2 != -1:
                idx_next = idx_tmp2    
                prev_char = ")"

            if idx_1 == -1 and idx_next == -1:
                current_idx += len("new")
                previous_char = " "
                continue
            if idx_next < idx_1 and idx_next != -1:
                # code like: "new RegExp;"
                end_idx = current_idx + idx_next - 1
                previous_content = testcase_content[current_idx:end_idx+1]
                offsets_to_proxy.append((current_idx+base_offset, end_idx+base_offset, previous_content))

                current_idx = end_idx + 1
                previous_char = prev_char
            else:
                rest2 = rest[idx_1+1:]
                # print("Rest2:")
                # print(rest2)
                # print("--------------")
                idx_2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest2, ')')
                if idx_2 == -1:
                    current_idx += len("new")
                    previous_char = " "
                    continue
                end_idx = current_idx + idx_1 + idx_2 + 1
                # print("Start: 0x%x" % current_idx)
                # print("End: 0x%x" % end_idx)
                previous_content = testcase_content[current_idx:end_idx+1]
                offsets_to_proxy.append((current_idx+base_offset, end_idx+base_offset, previous_content))
                # note: stuff which ares with "new " is added to offset_to_proxy because these variables must be proxied!

                current_idx = end_idx + 1
                previous_char = "("

        elif current_char.isnumeric() and (previous_char is None or previous_char.isalpha() is False) and previous_char != "_":
            # It's the start of a number!
            number_of_n_occurrence = 0
            number_of_dot_occurrence = 0
            number_of_e_occurrence = 0
            idx_start = current_idx

            tmp_idx = current_idx+1
            is_wrong = False
            tmp_char = "a"
            while True:
                if tmp_idx > last_idx:
                    break
                tmp_char = testcase_content[tmp_idx]
                if tmp_char.isnumeric() is False and tmp_char != "n" and tmp_char != "." and tmp_char != "e" and tmp_char != "E":
                    break
                # If we reach here it could be a string
                if tmp_char == "n":
                    number_of_n_occurrence += 1
                    if number_of_n_occurrence > 1:
                        # typically the "n" should just appear once at the end, so if it appears more often it's not a big int
                        is_wrong = True
                        break
                elif tmp_char == ".":
                    number_of_dot_occurrence += 1
                    if number_of_dot_occurrence > 1:
                        is_wrong = True
                        break
                elif tmp_char == "e" or tmp_char == "E":    # I currently don't support something like "1e-100" only stuff like "1e100"
                    number_of_e_occurrence += 1
                    if number_of_e_occurrence > 1:
                        is_wrong = True
                        break
                tmp_idx += 1

            if tmp_char.isalpha() or is_wrong:
                # it means it's not a number because it's a strange string, so just continue with next char
                current_idx += 1
                previous_char = current_char
                continue

            idx_end = tmp_idx - 1

            if previous_char == "-":
                # add the case where the minus belongs to the number
                previous_content = testcase_content[idx_start-1:idx_end+1]
                offsets_to_patch.append((idx_start-1+base_offset, idx_end+base_offset, previous_content))

                # add the normal case (in case the minus symbol was the minus operation...)
                previous_content = testcase_content[idx_start:idx_end+1]
                offsets_to_patch.append((idx_start+base_offset, idx_end+base_offset, previous_content))
            elif previous_char == ".":
                # float number which starts with a "."
                previous_content = testcase_content[idx_start-1:idx_end+1]
                offsets_to_patch.append((idx_start-1+base_offset, idx_end+base_offset, previous_content))
            else:
                # normal case
                previous_content = testcase_content[idx_start:idx_end+1]
                offsets_to_patch.append((idx_start+base_offset, idx_end+base_offset, previous_content))

            current_idx = idx_end + 1
            previous_char = testcase_content[current_idx-1]

           
        elif current_char == '"':
            rest = testcase_content[current_idx+1:]
            idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, '"')
            if idx_end == -1:
                current_idx += 1
                previous_char = current_char
                continue
            idx_end += current_idx + 1
            previous_content = testcase_content[current_idx:idx_end+1]
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))

            current_idx = idx_end + 1
            previous_char = '"'
        elif current_char == "'":
            rest = testcase_content[current_idx+1:]
            idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "'")
            if idx_end == -1:
                current_idx += 1
                previous_char = current_char
                continue
            idx_end += current_idx + 1
            previous_content = testcase_content[current_idx:idx_end+1]
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))

            current_idx = idx_end + 1
            previous_char = "'"
        elif current_char == '`':
            rest = testcase_content[current_idx+1:]
            idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "`")
            if idx_end == -1:
                current_idx += 1
                previous_char = current_char
                continue
            idx_end += current_idx + 1
            previous_content = testcase_content[current_idx:idx_end+1]
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))

            current_idx = idx_end + 1
            previous_char = "`"

        elif current_char == '[':
            rest = testcase_content[current_idx+1:]
            idx_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "]")
            if idx_end == -1:
                current_idx += 1
                previous_char = current_char
                continue
            idx_end += current_idx + 1
            previous_content = testcase_content[current_idx:idx_end+1]
            offsets_to_patch.append((current_idx+base_offset, idx_end+base_offset, previous_content))

            current_idx = idx_end + 1
            previous_char = "]"

        elif current_char == ".":
            # Can be something like Number.EPSILON
            # Or something like -Number.POSITIVE_INFINITY
            # Or something like customClass.customProperty

            # Find start of the token
            tmp_idx = current_idx

            while True:
                tmp_idx -= 1
                if tmp_idx < 0:
                    break
                tmp_char = testcase_content[tmp_idx]
                if tmp_char.isalnum() or tmp_char == "-" or tmp_char == "_":
                    continue
                else:
                    break
            # Now >tmp_idx+1< points to the start of the token
            start_of_token = tmp_idx + 1

            # Now find the end of the token
            tmp_idx = current_idx
            tmp_char = ""
            while True:
                tmp_idx += 1
                if tmp_idx >= len(testcase_content):
                    break
                tmp_char = testcase_content[tmp_idx]
                if tmp_char.isalnum() or tmp_char == "_":
                    continue
                else:
                    break

            if tmp_char == "(":     # it's a function call and therefore not a token which can be replaced
                # so just skip this one and continue with the next index
                current_idx += 1
                previous_char = "."
            else:
                # Now >tmp_idx+1< points to the start of the token
                end_of_token = tmp_idx - 1

                
                previous_content = testcase_content[start_of_token:end_of_token+1]
                offsets_to_patch.append((start_of_token+base_offset, end_of_token+base_offset, previous_content))

                current_idx = end_of_token + 1
                previous_char = testcase_content[current_idx-1]        

        else:
            current_idx += 1
            previous_char = current_char

    return offsets_to_patch, offsets_to_proxy


def rewrite_testcase_to_use_object(new_prefix_code, old_code_before, old_code_after, testcase_state):
    current_variable_id = testcase_state.number_variables
    current_variable_id += 1
    new_variable_name = "var_%d_" % current_variable_id
    variable_alloc_code = "var %s = " % new_variable_name
    testcase_state.number_variables = current_variable_id

    code_to_test = variable_alloc_code + new_prefix_code + ";\n" + old_code_before + new_variable_name + old_code_after
    return code_to_test




def get_all_allowed_injection_locations(testcase_content):
    default_high_value = 99999
    
    allowed_locations = []
    
    # TODO another allowed location is "var var_1_ = *HERE*"

    # Get all "[" and "]" locations:
    for entry in [("[", "]"), ("(", ")")]:
        current_content = testcase_content
        current_offset = 0
        (start_symbol, end_symbol) = entry
        while True:
            offset_start = speed_optimized_functions.get_index_of_next_symbol_not_within_string(current_content, start_symbol, default_high_value)
            if offset_start == default_high_value:
                break   # no more "[" symbols in the content
            try:
                rest = current_content[offset_start+1:]
            except:
                break
            offset_end = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, end_symbol, default_high_value)
            if offset_end == default_high_value:
                break   # no end "]" symbol in the content
            allowed_locations.append((current_offset + offset_start, current_offset + offset_start + offset_end + 1))
            try:
                current_content = rest[offset_end+1:]
            except:
                break
            current_offset = current_offset + offset_start + 1 + offset_end + 1
    return allowed_locations



def is_offset_within_allowed_locations(offset_to_check, allowed_locations_to_patch, testcase_content):
    # FIRST CASE:
    # Basically, I just want to inject at locations like:
    # Math.pow(1,1)
    # => Then I would want to inject by replacing a "1" because the value is passed to a native function
    # and that means the real value is queried somewhere inside a native function which can contain a coding flaw
    # On the other hand, I don't want to inject in a location like:
    # var var_1_ = 1+1;
    # If I would replace a "1" with an object which has a getter, then it would not make sense because the getter would
    # be invoked by the "+" operation and not within a native function...
    # Therefore I'm just injecting inside "(" and ")" blocks and inside of "[" and "]" blocks
    # Edit: Is this true? "+" is basically also just a native function, but it likely doesn't contain such bugs and occurs
    # way more frequently
    #
    # SECOND CASE:
    # Moreover, if code like this exists:
    # var var_1_ = 1;
    # ...
    # Math.pow(var_1_, 5)
    # => Then I also want to change the "1" because the "1" is just accessed inside Math.pow, e.g. the following code demonstrates this:

    # var var_2_ = {
    #    [Symbol.toPrimitive](var_3_) {
    #                    if(var_3_ == "number") {
    #                            console.log("INJECTED CALLBACK");
    #                            return 1;
    #                    }
    #            },
    # }
    # console.log("Start");
    # var var_1_ = var_2_;
    # console.log("Before Math.pow()");
    # Math.pow(var_1_,5);
    # console.log("After Math.pow()");    

    # First case:
    for entry in allowed_locations_to_patch:
        (start_offset, end_offset) = entry
        if start_offset <= offset_to_check <= end_offset:
            return True

    # Second case:
    lines = testcase_content.split("\n")
    line_number = testcase_helpers.content_offset_to_line_number(lines, offset_to_check)
    target_line = lines[line_number]

    # I'm checking for "_=" in case of code like "var var_1_= *****"
    if (" =" in target_line or "_=" in target_line) and "==" not in target_line:
        return True

    return False


def deterministically_include_callbacks(testcase_content, testcase_state, only_modify_new):
    global debug_stop

    allowed_locations_to_patch = get_all_allowed_injection_locations(testcase_content)
    # print("allowed_locations_to_patch:")
    # print(allowed_locations_to_patch)
    # sys.exit(-1)

    (offsets_to_patch, offsets_to_proxy) = extract_offsets(testcase_content)

    required_extract_offsets = offsets_to_patch
    while True:
        tmp = []
        for offset_to_patch in required_extract_offsets:
            (start_offset, end_offset, previous_content) = offset_to_patch
            if previous_content.isdigit():
                continue    # skip values such as 10000 because then I would identify 0000 as a sub part (which is incorrect)
            if "." in previous_content and not (" " in previous_content or "," in previous_content or "(" in previous_content or "[" in previous_content or "{" in previous_content):
                continue
            (offsets_to_patch_SUBPART, offsets_to_proxy_SUBPART) = extract_offsets(previous_content[1:], start_offset+1)
            tmp += offsets_to_patch_SUBPART
            tmp += offsets_to_proxy_SUBPART
            offsets_to_patch += offsets_to_patch_SUBPART
            offsets_to_proxy += offsets_to_proxy_SUBPART
        
        required_extract_offsets = tmp
        if len(required_extract_offsets) == 0:
            break


    # Some debugging code
    # print("Offset_to_patch:")
    # for offset_to_patch in offsets_to_patch:
    #     (start_offset, end_offset, previous_content) = offset_to_patch
    #     print(previous_content)
    # sys.exit(-1)

    total = len(offsets_to_patch) + len(offsets_to_proxy)
    if total > 250:
        # If there are too many callback locations I would create too many template files from one corpus file
        # Then other template files would not be executed so often
        # Therefore I skip these huge testcases
        return 0


    # This stores all used global class names like "Array", ...
    classes_in_use = set()
    
    if only_modify_new is False:
        # print("offset_to_patch:")
        for offset_to_patch in offsets_to_patch:
            (start_offset, end_offset, previous_content) = offset_to_patch
            
            if is_offset_within_allowed_locations(start_offset, allowed_locations_to_patch, testcase_content) is False:
                continue    # skip this offset because it would not make sense to inject there

            # print("Start: 0x%x" % start_offset)
            # print("End: 0x%x" % end_offset)
            # print("Content: %s\n" % previous_content)
            # print("-----------")
            if (end_offset - start_offset + 1) != len(previous_content):
                utils.perror("Incorrect entry, logic flaw?")

            code_before = testcase_content[:start_offset]
            code_after = testcase_content[end_offset+1:]

            code_to_test = rewrite_testcase_to_use_object(embed_first_callback_code(previous_content, testcase_state, False), code_before, code_after, testcase_state)
            triggered_exception = execute(code_to_test)
            if triggered_exception:
                # print("Trying with exception prevention:")
                code_to_test = rewrite_testcase_to_use_object(embed_first_callback_code(previous_content, testcase_state, True), code_before, code_after, testcase_state)
                execute(code_to_test)
            
            code_to_test = rewrite_testcase_to_use_object(embed_second_callback_code(previous_content, testcase_state, False), code_before, code_after, testcase_state)
            triggered_exception = execute(code_to_test)
            # triggered_exception = execute(code_before + embed_second_callback_code(previous_content, testcase_state, False) + code_after)
            if triggered_exception:
                # print("Trying with exception prevention:")
                # execute(code_before + embed_second_callback_code(previous_content, testcase_state, True) + code_after)
                code_to_test = rewrite_testcase_to_use_object(embed_second_callback_code(previous_content, testcase_state, True), code_before, code_after, testcase_state)
                execute(code_to_test)

    # print("\n\noffsets_to_proxy:")
    for offset_to_patch in offsets_to_proxy:
        (start_offset, end_offset, previous_content) = offset_to_patch

        if is_offset_within_allowed_locations(start_offset, allowed_locations_to_patch, testcase_content) is False:
            # skip this offset because it would not make sense to inject there
            # TODO: I'm not 100% sure if this logic also works with proxies, however
            # I have a lot of templates from proxying code from here
            # so it makes sense to reduce the number of proxy-templates and this definitely reduces the number
            continue    

        # print("Start: 0x%x" % start_offset)
        # print("End: 0x%x" % end_offset)
        # print("Content: %s\n" % previous_content)
        # print("------------")
        if (end_offset - start_offset + 1) != len(previous_content):
            utils.msg("[i] Incorrect entry, logic flaw?")
            continue
    
        if "(" in previous_content:
            idx = previous_content.index("(")
            arguments = previous_content[idx:]
            className = previous_content[len("new "):idx].strip()
        else:
            arguments = ""
            className = previous_content[len("new "):].strip()

        if className == "" or className.startswith("{"):
            continue
        if "[" in className or "]" in className or "(" in className or ")" in className:
            continue
        if className.startswith("new "):
            # These are strange testcases which contain code like: "new new String" which lead to exceptions which are catched
            className = className[len("new "):]

        if " " in className:
            continue


        classes_in_use.add(className)

        code_before = testcase_content[:start_offset]
        code_after = testcase_content[end_offset+1:]

        # =================== Proxying code ===================

        new_middle_code = "get_proxy1(%s)" % previous_content
        proxy_handler_code = get_proxy_handler(1, 1, testcase_state, className)
        # print("ATTEMPTING PROXY:")
        # print(proxy_handler_code + code_before + new_middle_code + code_after)
        execute(proxy_handler_code + code_before + new_middle_code + code_after)
        if result_code_of_last_execution is not None and "construct: function" in result_code_of_last_execution:
            # it means the "construct" function was called which means I can also return another proxy handler in the construct call
            prefix_code = get_proxy_handler(1, 2, testcase_state, className)
            prefix_code += get_proxy_handler(2, 2, testcase_state, className)
            # prefix_code += "%s = new Proxy(%s, proxyhandler1);\n" % (classname, classname)
            execute(prefix_code + code_before + new_middle_code + code_after)


        # =================== Sub Classing Code ===================
        if className.startswith("cl_") or className.startswith("var_") or className.startswith("func_") or className.lower() == "proxy" or className.lower() == "function" or className.lower() == "generator":
            # e.g.: a proxy object can't be subclassed
            # in v8 you get:
            # Class extends value does not have valid prototype property undefined
            continue        # skip these cases because they would lead to an exception because the class is just later defined

        is_native_type = False
        if className == "BigInt":
            is_native_type = True
        
        # One execution without redefined symbols
        # This can be useful e.g. when array.map() is called, the constructor will be called twice
        # If the symbols will be redefined, the constructor of the original array will be called and the custom constructor
        # won't be called. That's why I execute both combinations here
        (prefix_code, new_allocate_code) = get_subclass_code(className, testcase_state, redefineSymbols=False, exception_safe=False, is_native_type=is_native_type)
        exception_occurred = execute(prefix_code + code_before + new_allocate_code + arguments + code_after)
        # Ignore the output , I just want one entry with exception handling which is added below (keep corpus small)
        if exception_occurred:
            # print("Todo, first code throws exception?")
            # print(prefix_code + code_before + new_allocate_code + arguments + code_after)
            # Re-execute as exception safe code!
            (prefix_code, new_allocate_code) = get_subclass_code(className, testcase_state, redefineSymbols=False, exception_safe=True, is_native_type=is_native_type)
            exception_occurred = execute(prefix_code + code_before + new_allocate_code + arguments + code_after)
            # sys.exit(-1)

        # Now also one execution where the className is rewritten to the name class
        # For example, If I rewrite  "new RegExp" to "new cl_1_"
        # Then it's possible that data is stored in the static property of RegExp
        # FOr example: RegExp.lastMatch is set when operations are performed
        # Therefore code like RegExp.lastMatch must also be rewritten to cl_1_.lastMatch
        # That is what I'm doing here
        # Note that this could lead to problems. e.g. if I have two "new RegExp" objects, I just change the first one
        # then I rewrite to cl_1_.lastMatch but the lastMatch would be set in the 2nd object, a problem would occur
        # currently I just ignore this
        old_class_str_to_replace = className + "."
        new_class_str_to_replace = new_allocate_code[len("new "):] + "."
        tmp_code_before = code_before.replace(old_class_str_to_replace, new_class_str_to_replace)
        tmp_arguments = arguments.replace(old_class_str_to_replace, new_class_str_to_replace)
        tmp_code_after = code_after.replace(old_class_str_to_replace, new_class_str_to_replace)
        exception_occurred = execute(prefix_code + tmp_code_before + new_allocate_code + tmp_arguments + tmp_code_after)
        # Ignore exception here


        
        # One execution with redefined symbols (This can lead to different code paths and therefore I try it 2 times)
        # one without and one with redefined symbols
        (prefix_code, new_allocate_code) = get_subclass_code(className, testcase_state, redefineSymbols=True, exception_safe=False, is_native_type=is_native_type)
        exception_occurred = execute(prefix_code + code_before + new_allocate_code + arguments + code_after)
        if exception_occurred:
            (prefix_code, new_allocate_code) = get_subclass_code(className, testcase_state, redefineSymbols=True, exception_safe=True, is_native_type=is_native_type)
            exception_occurred = execute(prefix_code + code_before + new_allocate_code + arguments + code_after)
            if exception_occurred:
                pass
                # print("Todo, still exception?")
                # print(prefix_code + code_before + new_allocate_code + arguments + code_after)
                # sys.exit(-1)
        # print("Class Name: %s" % className)
        # print("arguments: %s" % arguments)

        # Also do one more execution with rewritten static class name
        exception_occurred = execute(prefix_code + tmp_code_before + new_allocate_code + tmp_arguments + tmp_code_after)
        # Ignore exception here

    # Proxy global classes
    # e.g. add code like: 
    # Array = new Proxy(Array, proxyhandler1)
    for classname in classes_in_use:
        if classname.startswith("cl_"):
            continue    # self defined classes can later be defined, since I add my code at the start it would not work. so it's currently not supported
        prefix_code = get_proxy_handler(1, 1, testcase_state, classname, should_fix_function_getters=False)
        prefix_code += "%s = get_proxy1(%s);\n" % (classname, classname)
        execute(prefix_code + testcase_content)
        if result_code_of_last_execution is not None and "construct: function" in result_code_of_last_execution:
            # it means the "construct" function was called which means I can also return another proxy handler in the construct call
            prefix_code = get_proxy_handler(1, 2, testcase_state, classname, should_fix_function_getters=False)
            prefix_code += get_proxy_handler(2, 2, testcase_state, classname, should_fix_function_getters=False)
            prefix_code += "%s = get_proxy1(%s);\n" % (classname, classname)
            execute(prefix_code + testcase_content)
            continue

        prefix_code = get_proxy_handler(1, 1, testcase_state, classname, should_fix_function_getters=True)
        prefix_code += "%s = get_proxy1(%s);\n" % (classname, classname)
        execute(prefix_code + testcase_content)
        if result_code_of_last_execution is not None and "construct: function" in result_code_of_last_execution:
            # it means the "construct" function was called which means I can also return another proxy handler in the construct call
            prefix_code = get_proxy_handler(1, 2, testcase_state, classname, should_fix_function_getters=True)
            prefix_code += get_proxy_handler(2, 2, testcase_state, classname, should_fix_function_getters=True)
            prefix_code += "%s = get_proxy1(%s);\n" % (classname, classname)
            execute(prefix_code + testcase_content)

    return total


def embed_second_callback_code(previous_content, testcase_state, protected_object):
    callback_code = get_js_objs_with_callback_functions()[2]

    if protected_object:
        callback_code = "new Object(" + callback_code + ") "

    callback_code = callback_code.replace("tmpFuzzer : 1337,", "").replace("return 1;", "return " + previous_content + ";").replace("return \"\";", "return " + previous_content + ";").replace("yield 1;", "yield " + previous_content + ";").replace("yield 2;", "yield " + previous_content + ";").replace("yield 3;", "yield " + previous_content + ";")
    return increase_variable_numbers_in_callback_code(callback_code, testcase_state)


def embed_first_callback_code(previous_content, testcase_state, protected_object):
    callback_code = get_js_objs_with_callback_functions()[0]
    if protected_object:
        callback_code = "new Object(" + callback_code + ") "
    callback_code = callback_code.replace("tmpFuzzer : 1337,", "").replace("return 42;", "return " + previous_content + ";").replace("return \"\";", "return " + previous_content + ";")
    return increase_variable_numbers_in_callback_code(callback_code, testcase_state)


def increase_variable_numbers_in_callback_code(callback_code, testcase_state):
    current_last_used_variable_id = testcase_state.number_variables
    for current_variable_number_to_fix in range(1, 100):
        token_name = "var_%d_" % current_variable_number_to_fix
        if token_name in callback_code:
            next_variable_id = current_last_used_variable_id + 1
            if current_variable_number_to_fix != next_variable_id:
                # That means it must be renamed
                token_name_new = "var_HACK_%d_" % next_variable_id
                # print("Going to rename %s token_name to %s" % (token_name, token_name_new))
                callback_code = callback_code.replace(token_name, token_name_new)
            current_last_used_variable_id = next_variable_id
    testcase_state.number_variables = current_last_used_variable_id     # set the new last used variable ID in the state
    callback_code = callback_code.replace("var_HACK_", "var_")
    return callback_code
    

def try_add_error_prepare_stacktrace(content, testcase_state):
    unused_variable_idx1 = testcase_state.number_variables + 1
    unused_variable_idx2 = testcase_state.number_variables + 2
    testcase_state.number_variables = testcase_state.number_variables + 2
    variable_decl = "var_%d_,var_%d_" % (unused_variable_idx1, unused_variable_idx2)

    code_to_print_identifier = get_js_print_identifier()

    prefix = """Error.prepareStackTrace = function(VARIABLE_DECL) {
   %s;
}
""".replace("%s", code_to_print_identifier).replace("VARIABLE_DECL", variable_decl)
   

    code1 = prefix + content
    execute(code1)

    # The Error.prepareStackTrace function typically does not trigger automatically
    # The e.stack property must be accessed to trigger it
    # The following loop tries to add such a code
    # Note: because of my variable name standardization the variable is not called e
    # So it's not possible to grep for catch(e). The code will be something like:
    # catch (var_1_)
    # Also note: The code does not always trigger. E.g: just accessing "e.stack" is not enough
    # The thrown error must be an instance of "Error". For example:
    # try { throw "42" }
    # Would not result in the execution. But code like:
    # try { notExistingFunction(); }
    # Would execute it
    for sub_pattern in ["catch\(", "catch \(", "catch\t\(", "catch\n\("]:
        for idx in [m.start() for m in re.finditer(sub_pattern, code1)]:
            rest = code1[idx:]
            idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "(")
            if idx2 == -1:
                continue
            rest2 = rest[idx2+1:]
            idx3 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest2, ")")
            if idx3 == 0 or idx3 == -1:
                continue    # 0 would mean there is no argument in the ( and )
            
            variable_name = rest2[:idx3]
            if "," in variable_name:
                variable_name = variable_name.split(",")[0]     # just take first variable name
            rest3 = rest2[idx3+1:]
            idx4 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest3, "{")
            if idx4 == -1:
                continue

            start_of_curly_bracket_in_testcase = idx+idx2+idx3+idx4 + 1 + 1  # +1 because of the +1 in rest2 and +1 in rest3
            # print("start_of_curly_bracket_in_testcase: 0x%x" % start_of_curly_bracket_in_testcase)
            code_before = code1[:start_of_curly_bracket_in_testcase+1]
            code_after = code1[start_of_curly_bracket_in_testcase+1:]
            code2 = code_before + "\n" + variable_name + ".stack;" + code_after
            execute(code2)


# This assumes that { and } is not used in the function where cfg.v8_print_id_not_printed is
# This is the case for all callbacks which I create myself and should therefore always work
def remove_not_printed_code_locations(code):
    original_code = code
    number_of_iterations = 0
    stop_length = 5*len(original_code)
    not_printed_str = "'%s'" % cfg.v8_print_id_not_printed
    while True:
        number_of_iterations += 1
        if number_of_iterations > 10000:
            return original_code    # some strange testcase which has a wrong syntax
        if len(code) > stop_length:
            return original_code        # it means it's an endless loop and the testcase becomes bigger and bigger. happens when the testcase is bogus
        if not_printed_str not in code:
            break
        idx = code.index(cfg.v8_print_id_not_printed)
        # print("Code:")
        # print(code)

        # Find the start of the function where PRINTED is called
        idx_start = idx-1
        depth = 0 
        while True:
            # print(idx_start)
            if idx_start < 0:
                # Logic flaw, the test case is strange. Just return the unmodified code
                return original_code
                # print("Logic flaw1, stopping")
                # sys.exit(-1)
            if code[idx_start] == "{" and depth == 0:
                break
            if code[idx_start] == "{":
                depth -= 1
            elif code[idx_start] == "}":
                depth += 1
            idx_start -= 1
        # while code[idx_start] != "{":
        #    idx_start -= 1
        while code[idx_start] != "\n":
            idx_start -= 1
        
        # Now idx_start points to the code where the function was defined

        idx_end = idx_start
        # Now find the end of the function
        # while code[idx_end] != "}":
        #    idx_end += 1
        depth = -1      # we start with -1 because I'm starting at the newline which means I will also process the opening { first which will change depth to 0
        while True:
            if idx_end >= len(code):
                return original_code
                # print("Logic flaw2, stopping")
                # This can especially occur when I create wrong templates
                # e.g.: code like:
                # } else {
                # ..._NOT_PRINTED_....
                # }
                # 
                # => The problem is that the first "}" would lead to incorrect results
                # I need to create templates like:
                # }\nelse {
                #
                # The newline is important, otherwise the depth would be incorrect in this loop

                # print(code)
                # print("IDX_END: 0x%x" % idx_end);
                # print("idx_start: 0x%x" % idx_start)
                # print("idx: 0x%x" % idx)
                # sys.exit(-1)
            if code[idx_end] == "}" and depth == 0:
                break
            if code[idx_end] == "}":
                depth -= 1
            elif code[idx_end] == "{":
                depth += 1
            idx_end += 1

        while code[idx_end] != "\n":
            idx_end += 1
        # idx_end += 1        # skip the \n at the end

        part_to_be_removed = code[idx_start:idx_end]

        """
        print("Original code:")
        print(code)
        print("-------------")
        
        print("part_to_be_removed:")
        print(part_to_be_removed)
        print("-------------")

        print("Before:")
        print(code[:idx_start])
        print("-------------")

        print("After:")
        print(code[idx_end:] )
        print("-------------")
        """

        part_to_be_removed_stripped = part_to_be_removed.strip().lower()
        cant_remove = False
        if part_to_be_removed_stripped.startswith("if") or part_to_be_removed_stripped.startswith("do") or part_to_be_removed_stripped.startswith("while") or part_to_be_removed_stripped.startswith("catch") or part_to_be_removed_stripped.startswith("try"):
            if "handler_proxy" not in part_to_be_removed_stripped:
                cant_remove = True
        if cfg.v8_temp_print_id in part_to_be_removed or cant_remove == True:
            # print("TODO Strange case, this should never occur")
            # print(code)
            # sys.exit(-1)
            # In this case the function can't be removed, but I can replace all the 
            part_to_be_removed = part_to_be_removed.replace("'%s'" % cfg.v8_print_id_not_printed, "'%s'" % cfg.v8_print_id_not_reachable)
            tmp = code[:idx_start] + part_to_be_removed + code[idx_end:]
        else:
            tmp = code[:idx_start] + code[idx_end:]     # now remove the function which is never called
        code = tmp
        
    return code



def fix_back_code_before_execution(code):
    # BigInt hack:
    # This is a stupid small hack which I use to subclass BigInt
    # the problem is that "new BigInt" is not valid code, but I need the "new" in front of it
    # so that I detect it in my code as class which I should sub class
    # So I'm just pretending "new BigInt" is valid and just before I execute it, I fix it back
    code = code.replace("new BigInt(", "BigInt(")

    # I'm also using a similar technique for "new "
    code = code.replace("new\t", "new ")
    return code
    


def execute_safe_wrapper(code_to_execute):
    global exec_engine
    code_to_execute = fix_back_code_before_execution(code_to_execute)
    result = exec_engine.execute_safe(code_to_execute)
    return result



def remove_multiple_output_lines(code):
    tmp = ""
    prefix = ""
    protection_id = 0
    fuzzcomamnd_str = "%s('%s'," % (cfg.v8_fuzzcommand, cfg.v8_print_command)
    for line in code.split("\n"):
        if fuzzcomamnd_str in line:
            protection_id += 1
            prefix += "var protection_%d_ = true;\n" % protection_id
            
            tmp += "if(protection_%d_ == true) { " % protection_id
            tmp += line
            tmp += "protection_%d_ = false;}\n" % protection_id
        else:
            tmp += line + "\n"

    return prefix + tmp


def execute(code_to_execute, store_result=True):
    global backup_number_variables, backup_testcase_state
    global result_code_of_last_execution, exec_engine, output_crash_dir
    global debug_stop

    # print("Executing:")
    # print(code_to_execute)
    # print("-----------------\n")
    # return

    result_code_of_last_execution = None    # Reset the result and just set it if it was successful

    # TODO: What is this variable? can't remember what I implemented here
    enable_multioutput_removal = False

   
    (code_to_execute, max_print_id) = callback_injector_helpers.update_IDs(code_to_execute)
    
    # print("CODE TO ATTEMPT:")
    # print(code_to_execute)

    result = execute_safe_wrapper(code_to_execute)

    # Fix the number of used variables for the next iteration by setting it back to the original value
    backup_testcase_state.number_variables = backup_number_variables   
    if debug_stop:
        print("Executed:")
        print(code_to_execute)
        print("Result:")
        print(result)
        sys.exit(-1)
    # print(result)
    
    if result.status == Execution_Status.TIMEOUT:
        # Try it with just one print => multiple prints in a long loop can take a very long time!
        # print("Trying with patched")
        temp_execution = remove_multiple_output_lines(code_to_execute)
        # print("---------")
        # print(temp_execution)
        # print("---------")
        result = execute_safe_wrapper(temp_execution)
        if result.status == Execution_Status.TIMEOUT:
            # print("STILL TIMEOUT!")
            return False    # still timeout, so just return
        enable_multioutput_removal = True
        # print("WORKED!")

    if result.status == Execution_Status.SUCCESS:
        # print("SUCCESS")
        if len(result.output) > 0 and max_print_id != 0:
            # That means it printed at a location and output was really seen
            # which means the code was executed which means a new location to add fuzzing code
            # was found
            code_to_execute = callback_injector_helpers.fix_IDs(code_to_execute, result.output, max_print_id)
            print_id_str = "'%s'" % cfg.v8_temp_print_id
            if print_id_str in code_to_execute:
                updated_code = remove_not_printed_code_locations(code_to_execute)

                code_to_test = updated_code
                if enable_multioutput_removal:
                    code_to_test = remove_multiple_output_lines(updated_code)

                result = execute_safe_wrapper(code_to_test)
                if result.status != Execution_Status.SUCCESS or len(result.output) == 0:
                    # Note: I don't compare here the output because It could happen that the output is different
                    # print("WRONG CODE REMOVAL! TODO CHECK THIS CASE")
                    # print("code_to_execute:")
                    # print(code_to_execute)
                    # print("After remove:")
                    # print(updated_code)
                    # sys.exit(-1)
                    updated_code = code_to_execute  # just use the previous result because the update failed
                # Now execute it again and check if the removal was correct!
                updated_code = fix_back_code_before_execution(updated_code)
                updated_code = updated_code.replace("//handler_proxy", "")  # remove the comment again
                # print("SAVING CODE:")
                # print(updated_code)
                result_code_of_last_execution = updated_code
                if store_result:
                    # STORE THE FOUND TEMPLATE IN THE TEMPLATE CORPUS:
                    store_new_template_file_in_corpus(updated_code)
                return False  # no exception
    elif result.status == Execution_Status.EXCEPTION_THROWN:
        # print("EXCEPTION!")
        # print(code_to_execute)
        # print("--------")
        # sys.exit(-1)
        return True     # Exception
    elif result.status == Execution_Status.TIMEOUT:
        return False    # nothing to do
    elif result.status == Execution_Status.CRASH:
        # msg(0, "ATTENTION: Found a crash with the Code >%s<" % code_to_execute)    # This should not happen during corpus creation!
        utils.msg("[+] CRASH!")
        utils.msg("[+] " + code_to_execute)
        
        m = hashlib.md5()
        m.update(code_to_execute.encode("utf-8"))
        result_hash = str(m.hexdigest())

        crash_file_fullpath = os.path.join(output_crash_dir, result_hash + ".js")
        with open(crash_file_fullpath, "w") as fobj_out:
            fobj_out.write(code_to_execute)
    else:
        utils.perror("Unkown status")

    return False    # no exception


# This function checks if all variables are contiguous (e.g. there is not var_1_ and var_3_ but no var_2_)
# Important: it just starts with the new IDs because I don't want to rename variables
# in the original testcase because I use the state of the original testcase
# If I would rename some variables there, the state would no longer match.
# Therefore I just start with the new variable IDs
def ensure_all_new_variables_are_contiguous(code):
    global backup_number_variables
    
    new_variables_start_with_id = backup_number_variables + 1

    max_number_of_variables = 1000
    variable_in_use = [False]*max_number_of_variables
    next_token_id = new_variables_start_with_id

    # Check which tokens are in-use
    for idx in range(new_variables_start_with_id, new_variables_start_with_id + max_number_of_variables):
        token_name = "var_%d_" % idx
        if token_name in code:
            new_token_name = "var_%d_" % next_token_id
            next_token_id += 1
            if new_token_name == token_name:
                pass    # nothing to do
            else:
                # they are different, e.g. token_name has a higher token ID, so change it
                code = code.replace(token_name, new_token_name)
    return code   


def store_new_template_file_in_corpus(code_with_callback):
    global current_filename, output_template_corpus_dir

    # remove empty lines
    tmp = []
    lines = code_with_callback.split("\n")
    for line in lines:
        if line.strip() == "":
            continue
        tmp.append(line)
    code_with_callback = "\n".join(tmp)

    code_with_callback = ensure_all_new_variables_are_contiguous(code_with_callback)
    
    output_directory = os.path.join(output_template_corpus_dir, current_filename)
    if not os.path.exists(output_directory):
        os.makedirs(output_directory)

    m = hashlib.md5()
    m.update(code_with_callback.encode("utf-8"))
    result_hash = str(m.hexdigest())

    try:
        state = create_state_for_new_template_file(code_with_callback)
    except:
        # TODO: This can occur, I think this occurs when the original value which gets moved into the callback
        # is multi-line and not a single line
        # However, currently I don't have time to fix this corner case
        # Edit: The testcase which triggers this is "tc12894.js" and it's a multi-line
        # original value, however, the value is an array and in the array a string is stored and the string is a fuzzed
        # very long string with a lot of special characters. So maybe my line counting algorithm fails there because
        # of the unicode/special characters in the string
        return
    output_file_fullpath = os.path.join(output_directory, result_hash + ".js")
    with open(output_file_fullpath, "w") as fobj_out:
        fobj_out.write(code_with_callback)

    output_state_file_fullpath = output_file_fullpath + ".pickle"
    
    testcase_state.save_state(state, output_state_file_fullpath)
    
    # print("New code:")
    # print(code_with_callback)
    # print("State:")
    # print(state)
    # sys.exit(-1)


def create_state_for_new_template_file(new_code):
    global backup_testcase_state_unmodified, backup_testcase_number_of_lines
    global exec_engine

    # Restart the engine to ensure a stable engine
    exec_engine.restart_engine() 

    fuzzcommand_str = "%s('%s'" % (cfg.v8_fuzzcommand, cfg.v8_print_command)
    fuzzcommand_str_commented = "//" + fuzzcommand_str
    # Remove the output so that state creation works correctly
    new_code = new_code.replace(fuzzcommand_str, fuzzcommand_str_commented)


    new_state = backup_testcase_state_unmodified.deep_copy()

    lines = new_code.split("\n")
    number_of_lines = len(lines)
    number_of_new_lines = number_of_lines - backup_testcase_number_of_lines


    # Fill the fields correctly:
    # TODO: Shouldn't I use here the js_helpers.get_number_variables_all() versions instead???
    new_state.number_functions = js_helpers.get_number_functions(new_code)
    new_state.number_variables = js_helpers.get_number_variables(new_code)
    new_state.number_classes = js_helpers.get_number_classes(new_code)


    # I'm using here a loop because I don't have a function yet to insert multiple lines in one function call..
    # TODO: Adapt the state_insert_line() function
    for i in range(number_of_new_lines):
        new_state = state_insert_line(0, "", "", new_state)

    # Small hack...
    # Currently state_insert_line() marks the new added line as a line where code can be injected
    # I don't want this because the callback code is not code where lines can be injected...
    # Basically I should rewrite state_insert_line(), but for now just remove the lines again...
    for i in range(number_of_new_lines-1):  # -1 because after last line code can be inserted
        line_number = i + 1     # +1 because at line 0 code can be inserted
        if line_number in new_state.lines_where_code_can_be_inserted:
            new_state.remove_all_entries_for_line_number(line_number)


    # Identify lines with callback code:
    code_lines_with_callback = []
    current_line_number = 0
    for line in lines:
        if fuzzcommand_str in line:
            code_lines_with_callback.append(current_line_number)
        current_line_number += 1

    if len(code_lines_with_callback) == 0:
        utils.perror("Internal error, trying to create state for a template file which doesn't contain callbacks: %s" % new_code)
        

    for line_number in code_lines_with_callback:
        if line_number in new_state.lines_where_code_can_be_inserted:
            # utils.perror("Internal coding flaw, should never occur. Inside create_state_for_new_template_file()")
            continue
        
        new_state.lines_where_code_can_be_inserted.append(line_number)
        new_state = adapt_state_file_in_line_number(new_code, new_state, line_number)
        

    new_state.recalculate_unused_variables()

    new_state.sort_all_entries()
    
    new_state.testcase_filename = "template"
    new_state.testcase_size = len(new_code)
    new_state.testcase_number_of_lines = number_of_lines    # must be set at the bottom because the above functions modify the number of lines in the state

    return new_state



def temp_hack_remove_again():
    tmp = set()
    with open("/home/r_freingruber/PROBLEM_DISABLED_FILES.txt", "r") as fobj:
        for line in fobj.read().split("\n"):
            line = line.strip()
            if line == "":
                continue
            testcase_name = line.split()[3]
            tmp.add(testcase_name)
    
    with open("/home/r_freingruber/PROBLEM_TEMPLATES.txt", "r") as fobj:
        for line in fobj.read().split("\n"):
            line = line.strip()
            if line == "":
                continue
            testcase_name = line.split()[2]
            tmp.add(testcase_name)
    

    print("Loaded %s entries" % len(tmp))
    for entry in tmp:
        print("\t%s" % entry)
    return tmp


def create_template_files_for_testcase(testcase_content, testcase_state):
    global backup_number_variables, backup_testcase_state, backup_testcase_state_unmodified, backup_testcase_number_of_lines
    length = len(testcase_content)
    if length > 2000:
        # Just do this if the testcase is small
        # There are some huge testcases and they would create a huge amount of templates
        # I don't want to fill the template corpus with just these entries...
        # Moreover: It would create a lot of templates and therefore the creation of state files for all these templates
        # would take very long
        return

    if testcase_state.runtime_length_in_ms > 400:
        # Skip template creations for slow testcases. This are ~450 files out of 16 000 files which
        # execute slower than 400 ms
        return


    # The different injection methods add new variables, I reset the number of used variables after every execution
    # so that the next injection technique starts again by the next free variable ID
    backup_number_variables = testcase_state.number_variables
    backup_testcase_state = testcase_state
    backup_testcase_state_unmodified = testcase_state.deep_copy()
    backup_testcase_number_of_lines = len(testcase_content.split("\n"))
    
    try_add_error_prepare_stacktrace(testcase_content, testcase_state)
    
    # Now inject callbacks using different methods.
    deterministically_include_callbacks(testcase_content, testcase_state, only_modify_new=False)


    # Now try to rewrite the testcase
    # => e.g. if there is code like "= 123" then replace it with "= new Number(123)"
    # => because then I can inject callbacks by e.g. sub classing "new Number"

    # but I don't want to sub class the "new XYZ" code again which I already previously sub-classed
    # in the above call
    # I therefore use here a small hack
    # I change the "new " (at the end a space) code to "new\t"
    # It behaves the same, but then my grep for "new " doesn't catch these locations again
    rewritten_content = testcase_content.replace("new ", "new\t")
    rewritten_content = rewrite_testcase_to_use_new(rewritten_content, testcase_state)

    # A quick check to see if the content was really modified. If not, the executions can be skipped (because nothing changed)
    test_tmp = rewritten_content.replace("new\t", "new ")
    if test_tmp != testcase_content:
        # Only perform execution if content is different
        # Note: passing the state here is not 100% correct, but I'm just accessing later the number or variables , so it should be OK
        # I'm also now setting "only_modify_new = True" to ensure that only code via "new" gets handled
        # and the other callback techniques are not executed again
        deterministically_include_callbacks(rewritten_content, testcase_state, only_modify_new=True)
