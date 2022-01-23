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


def rename_classes(content, required_coverage):
    class_names_to_rename = set()

    for class_decl in ["class ", ]:
        tmp = content.replace("\t", " ").replace("\n", " ").split(class_decl)
        if class_decl not in tmp[0]:
            tmp.pop(0)  # remove first which doesn't start with class
        for part in tmp:
            if "{" not in part:
                continue
            idx_1 = part.index("{")
            class_name = part[:idx_1].strip()
            if " extends" in class_name:
                class_name = class_name.split()[0]
            if class_name != "" and js_helpers.contains_only_valid_token_characters(class_name):
                if class_name.startswith("cl_") is False:
                    class_names_to_rename.add(class_name)

    class_names_to_rename = list(class_names_to_rename)
    # Start renaming with the longest variable name.
    # This helps to prevent cases where a variable name is the substring of another variable name
    class_names_to_rename.sort(reverse=True, key=len)

    last_used_class_id = 0
    for idx in range(200):
        token_name = "cl_%d_" % idx
        if token_name in content:
            last_used_class_id = idx

    class_id = last_used_class_id + 1
    for class_name in class_names_to_rename:

        utils.msg("[i] Attempt to rename class: %s" % class_name)
        renamed_successful = False

        new_content = js_renaming.rename_class_name_safe(content, class_name, class_id)
        if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
            renamed_successful = True

        if renamed_successful is False:
            if class_name != "_":
                # Here is a fallback to old code which renamed tokens (which is likely buggy but maybe works in some corner cases?)
                new_content = js_renaming.rename_class_name_old(content, class_name, class_id)
                if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                    renamed_successful = True

        if renamed_successful is False:
            if class_name != "_":
                # Last fallback is just to try replacing every token....
                new_content = content.replace(class_name, "cl_%d_" % class_id)
                if new_content != content and standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                    renamed_successful = True

        if renamed_successful:
            utils.msg("[+] Successfully renamed class: %s to cl_%d_" % (class_name, class_id))
            content = new_content
            class_id += 1
        else:
            utils.msg("[-] Renaming class failed: %s" % class_name)

    return content
