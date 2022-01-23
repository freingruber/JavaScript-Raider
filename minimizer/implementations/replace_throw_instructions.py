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



# Code like:
# throw "" + var_1_;
# will be rewritten to:
# try { throw "" + var_1_; } catch (e) {}
# Important:
# I don't just remove the throwing code because the way it accesses the variable is maybe required for the coverage
# and then the minimization would not occur.
# By wrapping it inside the try catch block, I ensure that it won't throw an exception
# This is very important for testcases which contain code like:
# if(condition) {
#   throw error
# }
# and condition is typically false but it's simple during fuzzing to wrap condition to true
# That would result in a lot of exceptions during fuzzing and therefore I rewrite the testcase to always catch the exception


import minimizer.minimizer_helpers as minimizer_helpers


def replace_throw_instructions(content, required_coverage):

    new_content = ""
    code_changed = False
    for line in content.split("\n"):
        if "throw " in line:
            code_changed = True
            new_content += "try { %s } catch (e) {}\n" % line     # wrap the line in a try-catch block
        else:
            new_content += line + "\n"

    if code_changed is False:
        return content      # Nothing was changed, so return the unmodified code

    new_content = new_content.rstrip("\n")

    if minimizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
        return new_content   # modification was successful
    return content  # not successful, so return the original code
