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


def rename_variables(content, required_coverage):
    variable_names_to_rename = js_helpers.get_all_variable_names_in_testcase(content)

    # the above method (get_all_variable_names_in_testcase()) was my old code which missed a lot of cases
    # The following function is my new code which should catch all variable names!
    # Just to get sure I merge both lists (which most likely contains some wrong cases from the first function
    # but it doesn't matter, the runtime is just a little bit longer...)
    variable_names_to_rename2 = js_helpers.get_variable_name_candidates(content)
    for variable_name in variable_names_to_rename2:
        if variable_name not in variable_names_to_rename:
            variable_names_to_rename.append(variable_name)

    if len(variable_names_to_rename) == 0:
        return content      # Nothing to rename

    # Start renaming with the longest variable name.
    # This helps to prevent cases where a variable name is the substring of another variable name
    variable_names_to_rename.sort(reverse=True, key=len)

    # Get starting ID for the new variables
    last_used_variable_id = 0
    for idx in range(8000):
        token_name = "var_%d_" % idx
        if token_name in content:
            last_used_variable_id = idx

    # Now iterate through all variables and replace them
    variable_id = last_used_variable_id+1
    for variable_name in variable_names_to_rename:
        utils.msg("[i] Attempting to rename variable: %s" % variable_name)

        renamed_successful = False

        for i in range(0, 2):    # try 2 times to rename a variable => it's really important that the fuzzer knows the variable token names!
            new_content = js_renaming.rename_variable_name_safe(content, variable_name, variable_id)
            # print("attempt1_variable")
            if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                renamed_successful = True
                break

        if renamed_successful is False:
            if variable_name != "_":
                for i in range(0, 2):
                    # Here is a fallback to old code which renamed tokens (which is likely buggy but maybe works in some corner cases?)
                    new_content = js_renaming.rename_variable_name_old(content, variable_name, variable_id)
                    # print("attempt2_variable")
                    if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                        renamed_successful = True
                        break

        if renamed_successful is False:
            if variable_name != "_":
                # Last fallback is just to try replacing every token....
                new_content = content.replace(variable_name, "var_%d_" % variable_id)
                # print("attempt3_variable")
                if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                    renamed_successful = True

        if renamed_successful:
            utils.msg("[+] Successfully renamed variable: %s to var_%d_" % (variable_name, variable_id))
            content = new_content
            variable_id += 1
        else:
            utils.msg("[-] Renaming variable failed: %s" % variable_name)
    return content
