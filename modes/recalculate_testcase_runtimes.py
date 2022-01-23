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



# This mode can be started by passing the "--recalculate_testcase_runtimes_mode" flag to the fuzzer.
#
# Every testcase stores in it's state the runtime of the testcase. If a corpus was created
# on a system different to the fuzzing system, the runtime will be wrong.
# E.g.: I calculated the corpus (and especially the states) on my local system
# and then switch to fuzzing to GCE instances. On my system a testcase can have a runtime of 50ms
# whereas on GCE it can have a runtime of 217 ms. The runtime values which are used to calculate
# upper boundaries for runtimes during fuzzing iterations can therefore be wrong.
# This mode will execute every testcase and store the correct runtime in the state.
# Execute it when you decide to use a new system.
#
# Side note: The max runtime is currently not really hardly enforced during fuzzing.
# Slightly different runtimes therefore don't really hard that much (at least at the moment).


import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
import testcase_state
import utils
import config as cfg


def recalculate_testcase_runtimes():
    corpus_filepath = cfg.output_dir_current_corpus

    counter = 0
    exception_testcases = []
    for filename in os.listdir(corpus_filepath):
        if filename.endswith(".js") is False:
            continue

        filepath = os.path.join(corpus_filepath, filename)
        if os.path.isfile(filepath) is False:
            continue
        
        with open(filepath, "r") as fobj:
            content = fobj.read()

        state_filepath = filepath + ".pickle"
        state = testcase_state.load_state(state_filepath)

        counter += 1
        utils.msg("[i] Going to recalculate runtime of testcase (counter: %d): %s" % (counter, filename))
        original_runtime_length = state.runtime_length_in_ms
        runtimes = []
        number_exceptions = 0
        for i in range(0, 5):       # Perform 5 executions
            result = cfg.exec_engine.execute_once(content)
            if "SUCCESS" not in result.get_status_str():
                number_exceptions += 1
            runtimes.append(result.exec_time)
        if number_exceptions > 1:
            exception_testcases.append(filename)
            continue

        runtimes.sort()
        runtimes.pop(0)     # remove fastest execution
        runtimes.pop()      # remove slowest execution
        average_runtime = float(sum(runtimes)) / len(runtimes)
        utils.msg("[i] New runtime %.2f (old runtime %.2f): %s" % (average_runtime, original_runtime_length, filename))
        
        state.runtime_length_in_ms = average_runtime
        testcase_state.save_state(state, state_filepath)

    for filename in exception_testcases:
        utils.msg("[-] Exception testcase: %s" % filename)
