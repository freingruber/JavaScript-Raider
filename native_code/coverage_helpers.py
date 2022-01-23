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


# This script contains some helper functions to extract coverage information.

import config as cfg


def extract_coverage_from_coverage_map_file(filepath):
    result = []
    with open(filepath, "rb") as fobj:
        coverage_map_content = fobj.read()
        idx = 0
        for x in coverage_map_content:
            if x == 0xff:
                idx += 8
                continue
            b1 = x & 0b00000001
            b2 = x & 0b00000010
            b3 = x & 0b00000100
            b4 = x & 0b00001000
            b5 = x & 0b00010000
            b6 = x & 0b00100000
            b7 = x & 0b01000000
            b8 = x & 0b10000000

            if b1 == 0:
                result.append(idx)
            idx += 1
            if b2 == 0:
                result.append(idx)
            idx += 1
            if b3 == 0:
                result.append(idx)
            idx += 1
            if b4 == 0:
                result.append(idx)
            idx += 1
            if b5 == 0:
                result.append(idx)
            idx += 1
            if b6 == 0:
                result.append(idx)
            idx += 1
            if b7 == 0:
                result.append(idx)
            idx += 1
            if b8 == 0:
                result.append(idx)
            idx += 1
    return result


def remove_already_known_coverage(new_coverage, already_known_coverage):
    return list(set(new_coverage) - set(already_known_coverage))


def extract_coverage_of_testcase(testcase_content, original_coverage_filepath):
    cfg.exec_engine.load_global_coverage_map_from_file(original_coverage_filepath)

    for i in range(0, 3):  # 3 executions to ensure that the coverage really gets triggered
        cfg.exec_engine.execute_once(testcase_content)

    # Old code had execute_safe() calls... this can hang very long when there is a new coverage map used
    # because the indeterministic coverage will lead to several executions;
    # and since I'm restoring everytime the coverage map, this can take very long (maybe?)
    # result = cfg.exec_engine.execute_safe(testcase_content)
    # result = cfg.exec_engine.execute_safe(testcase_content)

    cfg.exec_engine.save_global_coverage_map_in_file(cfg.coverage_map_minimizer_filename)
    ret = extract_coverage_from_coverage_map_file(cfg.coverage_map_minimizer_filename)
    return ret
