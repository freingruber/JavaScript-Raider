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



import utils
import standardizer.standardizer_helpers as standardizer_helpers
import javascript.js_renaming as js_renaming
import javascript.js_helpers as js_helpers


def rename_functions(content, required_coverage):
    function_names_to_rename = set()

    for function_decl in ["function ", "function* "]:
        tmp = content.replace("\t", " ").replace("\n", " ").split(function_decl)
        if function_decl not in tmp[0]:
            tmp.pop(0)  # remove first which doesn't start with function
        for part in tmp:
            if "(" not in part:
                continue
            idx_1 = part.index("(")
            function_name = part[:idx_1].strip()
            if function_name != "" and js_helpers.contains_only_valid_token_characters(function_name):
                if function_name.startswith("func_") is False:
                    function_names_to_rename.add(function_name)

    function_names_to_rename = list(function_names_to_rename)
    # Start renaming with the longest variable name.
    # This helps to prevent cases where a variable name is the substring of another variable name
    function_names_to_rename.sort(reverse=True, key=len)

    last_used_function_id = 0
    for idx in range(200):
        token_name = "func_%d_" % idx
        if token_name in content:
            last_used_function_id = idx

    func_id = last_used_function_id + 1
    for function_name in function_names_to_rename:
        utils.msg("[i] Attempt to rename function: %s" % function_name)
        renamed_successful = False
        # print("attempt1:")
        new_content = js_renaming.rename_function_name_safe(content, function_name, func_id)
        if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
            renamed_successful = True

        if renamed_successful is False:
            if function_name != "_":
                # Here is a fallback to old code which renamed tokens (which is likely buggy but maybe works in some corner cases?)
                new_content = js_renaming.rename_function_name_old(content, function_name, func_id)
                # print("attempt2:")
                if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                    renamed_successful = True

        if renamed_successful is False:
            if function_name != "_":
                # Last fallback is just to try replacing every token....
                new_content = content.replace(function_name, "func_%d_" % func_id)
                # print("attempt3:")
                if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                    renamed_successful = True

        if renamed_successful:
            utils.msg("[+] Successfully renamed function: %s to func_%d_" % (function_name, func_id))
            content = new_content
            func_id += 1
        else:
            utils.msg("[-] Renaming function failed: %s" % function_name)

    return content
