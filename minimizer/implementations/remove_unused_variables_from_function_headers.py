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



# This function removes unused arguments from function headers.
# Example:
# function func_1_(var_1_, var_2_, var_3_) {
#   const var_4_ = [Infinity,Object];
#   const var_5_ = var_4_.toLocaleString();
# }
# func_1_();
# => In this case var_1_, var_2_ and var_3_ are not used and can therefore be removed

import minimizer.minimizer_helpers as minimizer_helpers
import testcase_helpers


def remove_unused_variables_from_function_headers(content, required_coverage):
    variable_names_to_remove = []
    # Get unused variable names:
    for i in range(8000):
        variable_name = "var_%d_" % i
        if content.count(variable_name) == 1:
            # exactly one occurrence which means it can be such a case

            codeline = testcase_helpers.get_first_codeline_which_contains_token(content, variable_name)
            if "function " in codeline or "function\t" in codeline:
                variable_names_to_remove.append(variable_name)

    if len(variable_names_to_remove) == 0:
        return content  # nothing to do

    # First try to remove all variables at once
    content_adapted = content
    for variable_name in variable_names_to_remove:
        # important, we can't just remove the variable name, it's also maybe necessary to remove spaces or "," and again spaces
        content_adapted = minimizer_helpers.remove_variable_from_function_header(content_adapted, variable_name)

    if minimizer_helpers.does_code_still_trigger_coverage(content_adapted, required_coverage):
        content = content_adapted   # removing was successful
        return content

    if len(variable_names_to_remove) == 1:
        return content

    # Fallback: Try to remove one variable at a time
    for variable_name in variable_names_to_remove:
        # important, we can't just remove the variable name, it's also maybe necessary to remove spaces or "," and again spaces
        new_content = minimizer_helpers.remove_variable_from_function_header(content, variable_name)
        if minimizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
            content = new_content   # removing was successful

    return content
