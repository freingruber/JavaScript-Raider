import config as cfg
import utils
import native_code.executor as executor



number_performed_tests = 0
expectations_correct = 0
expectations_wrong = 0


def reset_stats():
    global number_performed_tests, expectations_correct, expectations_wrong
    number_performed_tests = 0
    expectations_correct = 0
    expectations_wrong = 0


def get_number_performed_tests():
    global number_performed_tests
    return number_performed_tests


def get_expectations_correct():
    global expectations_correct
    return expectations_correct


def get_expectations_wrong():
    global expectations_wrong
    return expectations_wrong


def assert_success(result):
    global number_performed_tests
    number_performed_tests += 1
    if result.status != executor.Execution_Status.SUCCESS:
        utils.msg("[-] ERROR: Returned status was not SUCCESS")
        raise Exception()


def assert_crash(result):
    global number_performed_tests
    number_performed_tests += 1
    if result.status != executor.Execution_Status.CRASH:
        utils.msg("[-] ERROR: Returned status was not CRASH")
        raise Exception()


def assert_exception(result):
    global number_performed_tests
    number_performed_tests += 1
    if result.status != executor.Execution_Status.EXCEPTION_THROWN and result.status != executor.Execution_Status.EXCEPTION_CRASH:
        utils.msg("[-] ERROR: Returned status was not EXCEPTION")
        raise Exception()


def assert_timeout(result):
    global number_performed_tests
    number_performed_tests += 1
    if result.status != executor.Execution_Status.TIMEOUT:
        utils.msg("[-] ERROR: Returned status was not TIMEOUT")
        raise Exception()


def assert_output_equals(result, expected_output):
    global number_performed_tests
    number_performed_tests += 1
    if result.output.strip() != expected_output.strip():
        utils.msg("[-] ERROR: Returned output (%s) was not correct (%s)" % (result.output.strip(), expected_output))
        raise Exception()


def execute_program(code_to_execute):
    cfg.exec_engine.restart_engine()
    result = cfg.exec_engine.execute_safe(code_to_execute)
    return result


def restart_exec_engine():
    cfg.exec_engine.restart_engine()


def execute_program_from_restarted_engine(code_to_execute):
    restart_exec_engine()
    return execute_program(code_to_execute)


def assert_int_value_equals(value_real, value_expected, error_msg):
    global number_performed_tests
    number_performed_tests += 1
    if value_real == value_expected:

        return  # Test PASSED
    utils.msg("[-] ERROR: %s (expected: %d ,real: %d)" % (error_msg, value_expected, value_real))
    # In this case I throw an exception to stop execution because speed optimized functions must always be correct
    raise Exception()    # Raising an exception shows the stacktrace which contains the line number where a check failed


def assert_string_value_equals(string_real, string_expected, error_msg):
    global number_performed_tests
    number_performed_tests += 1
    if string_real == string_expected:
        return  # Test PASSED
    print("[-] ERROR: %s (expected: %s ,real: %s)" % (error_msg, string_expected, string_real))
    # In this case I throw an exception to stop execution because speed optimized functions must always be correct
    raise Exception()    # Raising an exception shows the stacktrace which contains the line number where a check failed



def assert_no_new_coverage(result):
    global number_performed_tests
    number_performed_tests += 1

    if result.status != executor.Execution_Status.SUCCESS:
        utils.msg("[-] ERROR: Returned status was not SUCCESS") # but the result must always be SUCCESS
        raise Exception()

    if result.num_new_edges == 0:
        return  # test PASSED
    print("[-] ERROR: Found new coverage (%d) but expected that there is no new coverage!" % result.num_new_edges)
    # In this case I throw an exception to stop execution because speed optimized functions must always be correct
    raise Exception()  # Raising an exception shows the stacktrace which contains the line number where a check failed


def assert_new_coverage(result):
    global number_performed_tests
    number_performed_tests += 1

    if result.status != executor.Execution_Status.SUCCESS:
        utils.msg("[-] ERROR: Returned status was not SUCCESS") # but the result must always be SUCCESS
        raise Exception()

    if result.num_new_edges != 0:
        return  # test PASSED
    print("[-] ERROR: Found no new coverage but there should be one!")
    # In this case I throw an exception to stop execution because speed optimized functions must always be correct
    raise Exception()  # Raising an exception shows the stacktrace which contains the line number where a check failed


# The expect functions don't throw an exception like the assert_* functions
# Instead, they just count how often the expected result was true
def expect_no_new_coverage(result):
    global expectations_correct, expectations_wrong, number_performed_tests
    number_performed_tests += 1

    if result.status != executor.Execution_Status.SUCCESS:
        utils.msg("[-] ERROR: Returned status was not SUCCESS") # but the result must always be SUCCESS
        raise Exception()

    if result.num_new_edges == 0:
        expectations_correct += 1
    else:
        expectations_wrong += 1


# The expect functions don't throw an exception like the assert_* functions
# Instead, they just count how often the expected result was true
def expect_new_coverage(result):
    global expectations_correct, expectations_wrong, number_performed_tests
    number_performed_tests += 1

    if result.status != executor.Execution_Status.SUCCESS:
        utils.msg("[-] ERROR: Returned status was not SUCCESS") # but the result must always be SUCCESS
        raise Exception()

    if result.num_new_edges != 0:
        expectations_correct += 1
    else:
        expectations_wrong += 1
