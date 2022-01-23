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



import standardizer.standardizer_helpers as standardizer_helpers


def remove_shebang(content, required_coverage):
    if content.startswith("#!/") is False:
        return content
    new_content = content.split("\n", 1)[1]    # remove the first line
    if standardizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
        return new_content
    return content
