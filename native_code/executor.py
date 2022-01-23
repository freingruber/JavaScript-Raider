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



# The Executor class is used as an abstraction layer to interact with JavaScript engines
# A script can be passed to a function and the result indicates if:
# *) new coverage was found
# *) a crash occurred
# *) the testcase timeout
# *) or if it was a normal execution
# Restarting the v8 engine, ensuring stable results and so on are abstracted away using this class
# The caller must not care about these details, he just passes JavaScript code and receives a reliable result
#
# Note: It's very important that one execution does not leak memory. Since the fuzzer
# performs millions/billions of executions, just a small memory leak quickly leads to out-of-memory processes
# Same applies to files: if a file is opened (or file descriptor for communication),
# it must properly be closed or we run out of file descriptors

# Hint:
# If you want to use this library without the fuzzer, you just need to ensure
# to remove the "config.py" and "utils.py" dependencies. Just replace
# all "utils.msg" calls with "print" calls and "utils.perror" with a "print" and "sys.exit(-1)"
# For the "config.py" dependencies just replace the configurations with the actual values
# (e.g.: the path to the d8 binary).

import sys
import os
current_dir = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.abspath(os.path.join(current_dir, '..'))
if current_dir not in sys.path: sys.path.append(current_dir)

# Ensure we can import from base folder stuff like config/utils
if base_dir not in sys.path: sys.path.append(base_dir)



import libJSEngine  # C implementation for the executor; execute ./compile.sh to create it
import config as cfg
import enum
import datetime
import time
import utils
import os.path


def RIFSIGNALED(status):
    return (status & 0xff) != 0


def RIFEXITED(status):
    return RIFSIGNALED(status) is False and RIFTIMEDOUT(status) is False


def RIFTIMEDOUT(status):
    return (status & 0xff0000) != 0


def RTERMSIG(status):
    return status & 0xff


def REXITSTATUS(status):
    return (status >> 8) & 0xff


class Execution_Status(enum.Enum):
    SUCCESS = 0
    CRASH = 1
    EXCEPTION_THROWN = 2
    TIMEOUT = 3
    EXCEPTION_CRASH = 4
    INTERNAL_ERROR = 6
    UNKOWN = 5


class Execution_Result:
    def __init__(self, result):
        # Code if stdout output is compiled/enabled in the fuzzer:
        # self.output: This is the fuzzer output via named pipe reflection, e.g. via FUZZILLI_PRINT()
        # (status, self.exec_time, self.output, self.engine_stdout, self.engine_stderr, self.engine_was_restarted) = result

        (status, self.exec_time, self.output, self.engine_stderr, self.engine_was_restarted) = result

        # "engine_stderr":
        # This field is just filled when a crash occurred!

        # Common status values are:
        # 0x00: Success
        # 0x100: Exception
        # 0x04: Crash
        # 0x10000: Timeout
        if status == 0xff00:
            self.status = Execution_Status.INTERNAL_ERROR
        elif status == 0x4548:
            # This code was originally interpreted by fuzzilli as a crash, but I think it should be an exception
            # I assume that this code means that a Worker was started (2nd process)
            # In most cases I can ignore this status because it should not occur anymore because the fuzzer
            # doesn't create code which starts workers
            self.status = Execution_Status.EXCEPTION_CRASH
        else:
            if RIFEXITED(status) != 0:
                code = REXITSTATUS(status)
                if code == 0:
                    self.status = Execution_Status.SUCCESS
                else:
                    self.status = Execution_Status.EXCEPTION_THROWN
            elif RIFSIGNALED(status) != 0:
                self.status = Execution_Status.CRASH
                # crash_code = RTERMSIG(status)
                # print("crash_code: 0x%x" % crash_code)
            elif RIFTIMEDOUT(status) != 0:
                self.status = Execution_Status.TIMEOUT
            else:
                utils.msg("[-] Unkown status - should not occur:")
                utils.msg("[-] status: 0x%x" % status)
                self.status = Execution_Status.UNKOWN

        self.exec_time_usec = self.exec_time
        self.exec_time /= 1000  # convert to "ms" (milliseconds)

        # This score specifies how reliable a result is
        # A higher value means a more unreliable result (=> in-deterministic behavior)
        # This means if the code sample is executed multiple times it triggers new edges
        # which were not triggered the first times
        self.unreliable_score = 0  # correct value is later set

        # The number of edges are later separately initialized
        # Note: num_new_edges and num_edges are just set if the result is SUCCESS
        # Note: num_edges just gets set if there was a new edge
        self.num_new_edges = 0
        self.num_edges = 0

        self.total_executions_performed_via_execute_safe = 0  # execute_safe() is a function and this counts # of execs

    def set_coverage(self, coverage_result):
        (self.num_new_edges, self.num_edges) = coverage_result

    def get_status_str(self):
        if self.status == Execution_Status.SUCCESS:
            return "[+] SUCCESS"
        elif self.status == Execution_Status.CRASH:
            return "[!] CRASH"
        elif self.status == Execution_Status.EXCEPTION_THROWN:
            return "[-] EXCEPTION-THROWN"
        elif self.status == Execution_Status.TIMEOUT:
            return "[-] TIMEOUT"
        elif self.status == Execution_Status.UNKOWN:
            return "[?] UNKOWN"
        elif self.status == Execution_Status.INTERNAL_ERROR:
            return "[!] INTERNAL ERROR"
        elif self.status == Execution_Status.EXCEPTION_CRASH:
            return "[!] EXCEPTION CRASH"
        else:
            return "[?] COMPLETE UNKOWN"  # should never occur

    def __repr__(self):
        tmp = "Status: \t\t%s\n" % self.get_status_str()
        tmp += "Execution time: \t%d ms\n" % self.exec_time
        tmp += "Execution time specific: \t%d us\n" % self.exec_time_usec
        tmp += "Fuzz-output: (stripped): \t>%s<\n" % self.output.strip()

        # I removed v8 engine stdout because I typically don't need it (It would just slow down fuzzing)
        # tmp += "Engine stdout output (stripped): \t>%s<\n" % self.engine_stdout.strip()
        tmp += "Engine stderr output (stripped): \t>%s<\n" % self.engine_stderr.strip()
        tmp += "Unreliable score: \t%d\n" % self.unreliable_score
        tmp += "New edges: \t\t%d\n" % self.num_new_edges
        if self.num_edges > 0:
            tmp += "Total edges: \t\t%d\n" % self.num_edges
        tmp += "Execs in execute_safe(): \t%d\n" % self.total_executions_performed_via_execute_safe
        if self.engine_was_restarted:
            tmp += "[!] Engine was restarted\n"
        return tmp


class Executor:

    def __init__(self, timeout_per_execution_in_ms=cfg.v8_timeout_per_execution_in_ms_min, enable_coverage=True,
                 custom_path_d8=None):
        self.coverage_enabled = enable_coverage
        self.restart_after_executions = cfg.v8_restart_engine_after_executions
        self.executions_since_last_restart = 0
        self.timeout_per_execution_in_ms = timeout_per_execution_in_ms

        self.script_starttime = datetime.datetime.now()

        # Note that querying the >total_number_executions< and dividing it by the time elapsed
        # does not yield the real fuzzer speed (number of executions per second) in the first minutes
        # The reason is that the code makes "dummy iterations" in the beginning
        # See the adjust_coverage_with_dummy_executions() function
        # Since the dummy executions are very fast the real fuzzer speed will slightly be over-estimated
        # during the first minutes
        # If you don't have a good input corpus and find a lot of new coverage, the speed will also
        # be incorrect (because a lot of in-deterministic behavior will be found which results in
        # several hundred of executions to remove the in-deterministic behavior from the coverage map).
        self.total_number_executions = 0
        self.total_number_engine_starts = 0

        # This variable sums up all returned execution times of all testcases (=> used to calculate fuzzer overhead)
        # counted in seconds
        self.total_testcases_execution_time = 0.0

        self.engine_is_running = False  # stores the current state of the JavaScript engine

        # I store all executed testcases since the last restart in this list
        # When a crash occurs and the crash testcase is not independent (e.g.: execution alone
        # doesn't lead to a crash), then the crash testcase is maybe connected to previously executed code
        # This occurred several times at the beginning (e.g.: a testcase modified a global state which is
        # currently not reverted by v8 during in-memory executions)
        # I therefore also store for every crash all previously executed testcases.
        self.executed_testcases_since_last_engine_restart = []

        # >total_number_executions< can be higher than >total_number_testcases_executed<
        # because a call to execute_safe may lead to several executions (to get a reliable result)
        self.total_number_testcases_executed = 0

        self.total_number_very_unreliable_results = 0

        if custom_path_d8 is None:
            if self.coverage_enabled:
                path_d8 = cfg.v8_path_with_coverage
            else:
                path_d8 = cfg.v8_path_without_coverage
        else:
            path_d8 = custom_path_d8

        utils.msg("[i] Starting d8 from path: %s" % path_d8)
        libJSEngine.initialize(path_d8, cfg.v8_shm_id)
        self.__start_engine()
        self.number_triggered_edges = 0  # Counts how many edges were triggered yet
        self.execute("")  # empty execution
        # => this is required so that the engine runs one time to return some requires values (e.g. size of coverage map)

        # Now that the engine was executed and all requires values can be read, initialization can be finished
        self.total_number_possible_edges = libJSEngine.finish_initialization()

    def __del__(self):
        libJSEngine.shutdown()

    def __kill_possible_running_process(self):
        libJSEngine.kill_child()
        self.engine_is_running = False

    def __start_engine(self):
        # utils.msg("[!] Restarting engine!")
        libJSEngine.spawn_child()
        self.executions_since_last_restart = 0
        self.engine_is_running = True
        self.total_number_engine_starts += 1
        self.executed_testcases_since_last_engine_restart.clear()

    def save_global_coverage_map_in_file(self, filepath):
        libJSEngine.save_global_coverage_map_in_file(filepath)

    def load_global_coverage_map_from_file(self, filepath):
        if not os.path.exists(filepath):
            # It's important to check this here
            # otherwise libJSEngine would just seg fault
            print("Error, filepath %s does not exist! Stopping!" % filepath)
            sys.exit(-1)
        self.number_triggered_edges = libJSEngine.load_global_coverage_map_from_file(filepath)

    # This creates an in-memory backup ("snapshot") of the coverage map
    # This snapshot can be restored via >restore_global_coverage_map()<
    # Note:
    # It's also possible create a backup by saving the coverage map to a file
    # via a call to >save_global_coverage_map_in_file()< and then loading it via
    # >load_global_coverage_map_from_file()<. But an in-memory snapshot is a lot faster.
    def backup_global_coverage_map(self):
        libJSEngine.backup_global_coverage_map()

    def restore_global_coverage_map(self):
        # This resets the coverage map to the state stored
        # during the last backup_global_coverage_map() invocation
        # (e.g.: after the dummy executions; depending on the fuzzer mode)
        # This is useful when previous coverage results should be
        # dropped so that the same coverage can be found again
        # For example, during testcase or corpus minimization
        libJSEngine.restore_global_coverage_map()

    # A manual engine restart should typically not be triggered.
    # I mainly use this to test code samples after a restart or without a restart
    # (to ensure that the restart doesn't affect the result)
    # Another use case is the verification if a crash can alone be triggered
    # (e.g. restart the engine and then just execute the crashing testcase
    # without the previously executed testcases which may modified a global state in the JS engine)
    def restart_engine(self):
        self.__kill_possible_running_process()
        self.__start_engine()

    def stop_engine(self):
        self.__kill_possible_running_process()

    def enable_coverage(self):
        self.__kill_possible_running_process()
        self.coverage_enabled = True

    def disable_coverage(self):
        self.__kill_possible_running_process()
        self.coverage_enabled = False

    # Internal implementation to perform an exception
    # Should not be called by the end user
    def internal_perform_execution(self, script_code, timeout_to_use=None):
        start_time = datetime.datetime.now()
        if self.executions_since_last_restart >= self.restart_after_executions and self.engine_is_running is True:
            self.__kill_possible_running_process()
        if self.engine_is_running is False:
            self.__start_engine()

        if timeout_to_use is None:
            timeout_to_use = self.timeout_per_execution_in_ms   # no timeout passed, so use the default one

        self.executed_testcases_since_last_engine_restart.append(script_code)

        ret = libJSEngine.execute_script(script_code, int(timeout_to_use))
        exec_result = Execution_Result(ret)

        if exec_result.status == Execution_Status.INTERNAL_ERROR:
            # Restart engine and try it again
            utils.msg("[-] ATTENTION: Execution resulted in Execution_Status.INTERNAL_ERROR; restarting engine...")
            self.__kill_possible_running_process()
            self.__start_engine()
            self.executed_testcases_since_last_engine_restart.append(script_code)
            ret = libJSEngine.execute_script(script_code, int(timeout_to_use))
            exec_result = Execution_Result(ret)

        if exec_result.status == Execution_Status.TIMEOUT or exec_result.status == Execution_Status.CRASH or exec_result.status == Execution_Status.EXCEPTION_CRASH:
            # Mark the engine as not running
            # it will be restarted at the beginning of the next execution invocation
            self.engine_is_running = False
        if exec_result.engine_was_restarted:
            utils.msg("[-] CARE: The engine had to be restarted unintentionally. This should not happen")
            time.sleep(2)
            self.executions_since_last_restart = 0  # Reset the counter
            self.total_number_engine_starts += 1
        self.executions_since_last_restart += 1
        self.total_number_executions += 1

        # returned seconds is a floating point value and also contains the microseconds
        self.total_testcases_execution_time += (datetime.datetime.now() - start_time).total_seconds()
        return exec_result

    # The execute() function ensures that new behavior is correct and reliable
    # The execute() function therefore executes a testcase maybe multiple times
    # Instead, the execute_once() function really just performs one execution.
    # This is mainly used internally (e.g.: to make dummy executions to initialize the engine coverage)
    def execute_once(self, script_code, is_query=False, custom_timeout=None):
        if is_query is True:
            # This is some internal execution to get some runtime information
            # It should not update the coverage map and it should has a sufficient long runtime to not trigger a timeout
            # Examples of usage: During state creation when variable data types or properties are extracted
            # Or code which extracts names, properties and functions of globals from the JavaScript engine

            # Give internal queries 20 times longer execution time (they should really never timeout)
            exec_result = self.internal_perform_execution(script_code, timeout_to_use=self.timeout_per_execution_in_ms * 20)
            return exec_result
        else:
            # Normal execution (e.g.: dummy executions)
            exec_result = self.internal_perform_execution(script_code, timeout_to_use=custom_timeout)
            if exec_result.status == Execution_Status.SUCCESS and self.coverage_enabled:
                exec_result.set_coverage(libJSEngine.evaluate_coverage())
                self.number_triggered_edges += exec_result.num_new_edges
            self.total_number_testcases_executed += 1
            return exec_result

    # Typically, new coverage gets updated in the coverage map so that subsequent executions do not find the same code again
    # However, when doing operations such as testcase minimization it's important that the same coverage can
    # be triggered multiple times
    def execute_without_coverage_update(self, script_code):
        exec_result = self.internal_perform_execution(script_code)
        number_new_edges = 0
        if exec_result.status == Execution_Status.SUCCESS and self.coverage_enabled:
            number_new_edges = libJSEngine.evaluate_coverage_step1_check_for_new_coverage()
        return exec_result, number_new_edges

    # You should not call this directly.
    # Call instead:
    # execute_once()
    # execute_safe()
    # The typical flow of execution is either:
    # execute_safe() -> execute() -> internal_perform_execution()
    # or
    # execute_once() -> execute() -> internal_perform_execution()
    #
    # The internal_perform_execution() call performs the execution
    # The current function ( execute() ) implements the coverage query / update
    # Originally I always queries and updated the global coverage, however, this
    # must be skipped for some operations (e.g.: testcase minimization) and therefore
    # I added this function to handle this
    # The execute_safe() function executes this function maybe multiple times
    # until results are reliable (and every newly detected coverage is updated in the global coverage map)
    def execute(self, script_code, custom_timeout=None, is_second_attempt=False):
        if custom_timeout is None:
            custom_timeout = self.timeout_per_execution_in_ms

        exec_result = self.internal_perform_execution(script_code, timeout_to_use=custom_timeout)
        if exec_result.status == Execution_Status.UNKOWN:
            utils.msg("[-] TODO: Received unkown return status in execute()")
            # sys.exit(-1)

        if exec_result.status == Execution_Status.SUCCESS and self.coverage_enabled:
            # I had a problem that sometimes results were not reliable because sometimes some in-deterministic new coverage was triggered
            # I don't want that the code puts such random samples into the corpus because it will fill the corpus with
            # useless entries which will reduce the fuzzer efficiency in long-term.
            # Since code samples with new coverage are not frequently detected,
            # it should not hurt to make for every new code coverage sample an additional execution (this will not occur too often).
            # => I just count samples which result twice in new coverage! This removes (or at least dramatically reduces) these in-deterministic results

            # It's therefore important that the first evaluation of the coverage does not update the overall coverage map
            # However, the second run must update the coverage map with the coverage from the first & second run!
            # If it was a false positive (=> first run showed new coverage because of in-deterministic behavior),
            # then in-deterministic behavior will not be detected again because I aso update the first coverage
            # exec_result.set_coverage(libJSEngine.evaluate_coverage())
            #
            # Otherwise I would maybe very often trigger the in-deterministic coverage

            number_new_edges = libJSEngine.evaluate_coverage_step1_check_for_new_coverage()
            if number_new_edges != 0:
                self.restart_engine()  # Restarting the engine helps to reduce false positives.
                # And again, finding new coverage is a rare event => This is not often performed

                # Give a higher timeout because the testcase could maybe be at the boundary of the timeout
                # e.g. if a timeout is 100ms and the first executed was 95ms, then it could happen that the 2nd invocation
                # takes for example 105 ms. In this case I don't want to run into a timeout and therefore I increase the
                # timeout for the 2nd execution
                second_exec_result = self.internal_perform_execution(script_code, timeout_to_use=custom_timeout * 1.5)
                if second_exec_result.status != Execution_Status.SUCCESS:
                    # should not occur, but who knows?
                    # EDIT: => as it turns out this can occur... (e.g.: timeout)
                    # Note: after updating v8 to a newer version (december 2020) this occurs more frequently..
                    # Now I added the "is_second_attempt" code which seems to solve the problem
                    if is_second_attempt:
                        # Then just return the 2nd result, e.g. timeout
                        # keep the message because I want to see how often this occurs
                        utils.msg("[-] INCORRECT SECOND EXECUTION RESULT: %s" % second_exec_result.get_status_str())
                        return second_exec_result
                    else:
                        # It's the first attempt, so maybe start a second attempt...
                        return self.execute(script_code, custom_timeout, is_second_attempt=True)
                else:
                    # Second result was also a success, so we can query the coverage again and update the coverage map
                    exec_result.set_coverage(libJSEngine.evaluate_coverage_step2_finish_query_coverage())

                if exec_result.num_new_edges != 0:
                    # Use the first result and not the 2nd one
                    # otherwise we may miss in-deterministic edges from first execution
                    self.number_triggered_edges += exec_result.num_new_edges
        return exec_result

    def get_testcases_since_last_engine_restart(self):
        # If a crash occurred, I also save the last executed testcases
        return self.executed_testcases_since_last_engine_restart

    def reset_total_testcases_execution_time(self):
        self.total_testcases_execution_time = 0.0

    def get_total_testcases_execution_time(self):
        return self.total_testcases_execution_time

    # The execute() function executes a given input once
    # However, it can happen that calling the same code multiple times triggers different edge coverage
    # in every execution (because of in-deterministic behavior)
    # This would add incorrect code samples to the corpus
    # It therefore makes sense to execute code which triggers new behavior multiple times until
    # the code does not trigger new behavior. This is what this function does
    # The suffix is "_safe" because the coverage map is considered "safe" and "stable" afterwards
    # Please note: Execution of testcases multiple times when new coverage is found is a very rare event
    # (at least if you already have a good corpus ;) ). It should therefore not hurt the performance
    def execute_safe(self, script_code, custom_timeout=None):
        self.total_number_testcases_executed += 1

        first_result = self.execute(script_code, custom_timeout=custom_timeout)
        first_result.total_executions_performed_via_execute_safe = 1
        # if there was a crash, an exception thrown or a timeout, the new_edges field won't be set
        # and therefore the code immediately returns
        if first_result.num_new_edges == 0:
            return first_result

        # If this point is reached, new coverage was triggered

        iterations_without_new_coverage = 0
        total_iterations = 0
        required_iterations_without_new_coverage = 3  # 3 iterations without new coverage should be enough to handle in-deterministic behavior

        # 135 is a lot, however, it's very important that stable samples are used so
        # that the corpus is really good
        maximum_iterations = 135

        first_result.unreliable_score = 0  # start with a good score
        while True:
            total_iterations += 1
            result = self.execute_once(script_code, custom_timeout=custom_timeout)
            first_result.total_executions_performed_via_execute_safe += 1
            if result.num_new_edges == 0:
                iterations_without_new_coverage += 1
            else:
                iterations_without_new_coverage = 0  # reset because new coverage was found; so start search again
            if iterations_without_new_coverage == required_iterations_without_new_coverage:
                return first_result  # The first result is returned because it's the minimum-set of all results for new edges

            # If it triggers very often new coverage (a lot of in-deterministic behavior), it can make sense to
            # increase the number of "iterations required without new coverage"
            if total_iterations >= maximum_iterations:
                # Very unstable testcase!
                first_result.unreliable_score = 10  # increase the score
                self.total_number_very_unreliable_results += 1
                # this ensures that the fuzzer doesn't get stuck in the endless loop with such samples and just returns
                return first_result
            elif total_iterations >= 50:
                required_iterations_without_new_coverage = 25
                first_result.unreliable_score = 5  # increase the score
            elif total_iterations >= 25:
                required_iterations_without_new_coverage = 15
                first_result.unreliable_score = 4  # increase the score
            elif total_iterations >= 15:
                required_iterations_without_new_coverage = 10
                first_result.unreliable_score = 3  # increase the score
            elif total_iterations >= 10:
                required_iterations_without_new_coverage = 7
                first_result.unreliable_score = 2  # increase the score
            elif total_iterations >= 5:
                required_iterations_without_new_coverage = 5
                first_result.unreliable_score = 1  # increase the score

    # This should be executed once before execution() (or other variations) are called.
    # It starts to adjust the coverage so that reliable results are returned
    # in execution() calls.
    def adjust_coverage_with_dummy_executions(self):
        # on my local system 35 executions of empty code are enough,
        # on AWS 55 were required;
        # After updating v8 to a version from 2022, 55 were still not enough
        # So I changed it to 150 just to get sure...
        number_loop_iterations = 150

        # Initially, the coverage feedback varies because of in-deterministic behavior
        # To encounter this, the engine is started several times so that the coverage map gets updated
        # with all these different in-deterministic behaviors
        # This is important because otherwise the engine would detect new behavior for a testcase
        # which maybe doesn't trigger new behavior (and just some in-deterministic behavior)
        utils.msg("[i] Starting adjustment of coverage feedback...")
        for i in range(0, number_loop_iterations):  # some iterations which update the coverage map;
            self.execute_once("")  # this intentionally doesn't call execute_safe()

        new_coverage = 0
        for i in range(0, 5):
            new_coverage += self.execute_once("").num_new_edges  # this intentionally doesn't call execute_safe()
        if new_coverage != 0:
            # There is in-deterministic behavior still after X executions!
            # If this is triggered, you can try to change "utils.perror" to "utils.msg".
            # The fuzzer should still work fine in such a case
            # Or you can try to increase >number_loop_iterations<
            utils.perror("[-] Internal error, results are not deterministic! Stopping... (this can especially occur after updating v8 and v8 had some internal changes...)")

        # Now store the current coverage map state for a possible later restore operation
        # (e.g. for minimization operations)
        self.backup_global_coverage_map()

        utils.msg("[+] Finished adjustment of coverage feedback!")

    def get_number_engine_restarts(self):
        return self.total_number_engine_starts

    def get_total_number_executions(self):
        return self.total_number_executions

    # Not used anymore, I'm dumping stats in the status_update function in JS_Fuzzer.py
    def print_statistics(self):
        print("Total number of testcases: %d" % self.total_number_testcases_executed)
        print(
            "Total number of executions: %d" % self.total_number_executions)  # number of executions is bigger than testcases because testcases can be executed multiple times

        print("Engine was restarted: %d times" % self.total_number_engine_starts)

        script_endtime = datetime.datetime.now()
        script_timediff = script_endtime - self.script_starttime
        print("Execution time was %d seconds" % script_timediff.seconds)
        execution_speed = float(self.total_number_executions) / float(script_timediff.seconds)
        print("Execution speed: %.2f exec/sec" % execution_speed)

        testcases_speed = float(self.total_number_testcases_executed) / float(script_timediff.seconds)
        print("Testcases speed: %.2f tc/sec" % testcases_speed)

        if self.coverage_enabled:
            print("Total number very unreliable results: %d" % self.total_number_very_unreliable_results)
            print("Total number possible edges: %d" % self.total_number_possible_edges)
            print("Triggered edges: %d" % self.number_triggered_edges)
            current_coverage = (float(self.number_triggered_edges) / float(self.total_number_possible_edges) * 100)
            print("Current coverage: %.4f %%" % current_coverage)

    def get_number_triggered_edges(self):
        return self.number_triggered_edges, self.total_number_possible_edges
