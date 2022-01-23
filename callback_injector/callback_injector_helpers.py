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


# Helper functions for the callback injector

import config as cfg


def update_IDs(code):
    print_id = 0
    while cfg.v8_temp_print_id in code:
        print_id += 1
        code = code.replace(cfg.v8_temp_print_id, cfg.v8_print_id_prefix + str(print_id) + cfg.v8_print_id_postfix, 1)
    return code, print_id


def remove_IDs(code, max_print_id):
    for i in range(1, max_print_id+1):
        # Mark it as not printed so that the fuzzer knows that he must not fuzz the code at that location
        code = code.replace(cfg.v8_print_id_prefix + str(i) + cfg.v8_print_id_postfix, cfg.v8_print_id_not_printed)
    return code


def fix_IDs(code, output, max_print_id):
    already_fixed_IDs = set()
    len_prefix = len(cfg.v8_print_id_prefix)
    len_negative_postfix = len(cfg.v8_print_id_postfix) * -1
    for printed_ID in output.split("\n"):
        printed_ID = printed_ID.strip()
        if printed_ID == "":
            continue
        if printed_ID.startswith(cfg.v8_print_id_prefix) is False:
            continue
        code = code.replace(printed_ID, cfg.v8_temp_print_id)        # Mark the print for the later iterations as executed
        printed_ID_value = int(printed_ID[len_prefix:len_negative_postfix], 10)
        already_fixed_IDs.add(printed_ID_value)

    for i in range(1, max_print_id+1):
        if i in already_fixed_IDs:
            continue
        # Mark it as not printed so that the fuzzer knows that he must not fuzz the code at that location
        code = code.replace(cfg.v8_print_id_prefix + str(i) + cfg.v8_print_id_postfix, cfg.v8_print_id_not_printed)
    return code
