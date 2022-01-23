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



# Example:
# function func_1_() {
#     const var_4_ = [Infinity,Object];
#     const var_5_ = var_4_.toLocaleString();
# }
# func_1_();

# =>

# const var_4_ = [Infinity,Object];
# const var_5_ = var_4_.toLocaleString();

import minimizer.minimizer_helpers as minimizer_helpers
import native_code.speed_optimized_functions as speed_optimized_functions


def remove_not_required_function_contexts(content, required_coverage):


    function_names_to_remove = []
    # Get unused variable names:
    for i in range(100):
        function_name = "func_%d_" % i
        if content.count(function_name) == 2:   # one for the definition, one for the invocation
            function_names_to_remove.append(function_name)

    for function_name in function_names_to_remove:
        function_invocation_code = function_name + "();"    # I'm always assuming empty invocations here
        if function_invocation_code in content:
            # Try to remove it.
            start_of_function_declaration = content.find("function %s" % function_name)
            rest = content[start_of_function_declaration:]
            idx = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest, "{")
            rest2 = rest[idx + 1:]
            idx2 = speed_optimized_functions.get_index_of_next_symbol_not_within_string(rest2, "}")
            function_body = rest2[:idx2]

            function_body2 = ""
            for line in function_body.split("\n"):
                line = line.strip()
                if line == "":
                    continue
                function_body2 += line + "\n"

            full_end_idx_of_function_body = start_of_function_declaration + idx + 1 + idx2 + 1
            if full_end_idx_of_function_body < len(content):
                if content[full_end_idx_of_function_body] == "\n":
                    full_end_idx_of_function_body += 1  # also remove the newline after the function body

            full_function = content[start_of_function_declaration:full_end_idx_of_function_body]
            new_content = content.replace(full_function, "")    # remove the function
            new_content = new_content.replace(function_invocation_code, function_body2.strip())  # add the function body at the previous location
            if minimizer_helpers.does_code_still_trigger_coverage(new_content, required_coverage):
                content = new_content   # removing was successful
    return content
