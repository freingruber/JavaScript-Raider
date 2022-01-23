// Copyright 2022 @ReneFreingruber
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// https://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// The code in this file is strongly based on the modules from fuzzilli (from the year 2020)
//     *) https://github.com/googleprojectzero/fuzzilli/tree/master/Sources/libreprl
//     *) https://github.com/googleprojectzero/fuzzilli/tree/master/Sources/libcoverage
// This code was shipped under the Apache 2.0 License with the following Copyright information:
// Copyright 2020 Google LLC

// The following modifications were done on the code:
//      *) The code was ported to a Python module (with new required functions to support the Python <-> C code integration)
//      *) The two modules were merged into a single file
//      *) Some modifications were done (e.g.: Split the update of the coverage map; Removal of unicode symbols in the output, ...)
//      *) Comments were modified
//      *) The performance functions are new and independent to fuzzilli's LibRERL and LibCoverage
//              internal_get_line_number_of_offset()
//              internal_get_index_of_next_symbol_not_within_string()



#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif

#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <poll.h>
#include <signal.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <stdarg.h>
#include <Python.h>

#include <stdbool.h>

#include <locale.h>
#include <wchar.h>


// A unidirectional communication channel for larger amounts of data, up to a maximum size (REPRL_MAX_DATA_SIZE).
// Implemented as a (RAM-backed) file for which the file descriptor is shared with the child process and which is mapped into our address space.
struct data_channel {
    // File descriptor of the underlying file. Directly shared with the child process.
    int fd;
    // Memory mapping of the file, always of size REPRL_MAX_DATA_SIZE.
    char* mapping;
};

struct reprl_context {
    // Whether reprl_initialize has been successfully performed on this context.
    int initialized;
    
    // Read file descriptor of the control pipe. Only valid if a child process is running (i.e. pid is nonzero).
    int ctrl_in;
    // Write file descriptor of the control pipe. Only valid if a child process is running (i.e. pid is nonzero).
    int ctrl_out;
    
    // Data channel REPRL -> Child
    struct data_channel* data_in;
    // Data channel Child -> REPRL
    struct data_channel* data_out;
    
    // Optional data channel for the child's stdout and stderr.
    struct data_channel* stdout;
    struct data_channel* stderr;
    
    // PID of the child process. Will be zero if no child process is currently running.
    int pid;
    
    // Arguments and environment for the child process.
    char** argv;
    char** envp;
    
    // A malloc'd string containing a description of the last error that occurred.
    char* last_error;
};


// ######################## START REPRL DEFINES ########################

/// Maximum size for data transferred through REPRL. In particular, this is the maximum size of scripts that can be executed.
/// Currently, this is 16MB. Executing a 16MB script file is very likely to take longer than the typical timeout, so the limit on script size shouldn't be a problem in practice.
#define REPRL_MAX_DATA_SIZE (16 << 20)

/// Allocates a new REPRL context.
/// @return an uninitialized REPRL context
struct reprl_context* reprl_create_context();

/// Initializes a REPRL context.
/// @param ctx An uninitialized context
/// @param argv The argv vector for the child processes
/// @param envp The envp vector for the child processes
/// @param capture_stdout Whether this REPRL context should capture the child's stdout
/// @param capture_stderr Whether this REPRL context should capture the child's stderr
/// @return zero in case of no errors, otherwise a negative value
int reprl_initialize_context(struct reprl_context* ctx, char** argv, char** envp, int capture_stdout, int capture_stderr);

/// Destroys a REPRL context, freeing all resources held by it.
/// @param ctx The context to destroy
void reprl_destroy_context(struct reprl_context* ctx);

/// Executes the provided script in the target process, wait for its completion, and return the result.
/// If necessary, or if fresh_instance is true, this will automatically spawn a new instance of the target process.
///
/// @param ctx The REPRL context
/// @param script The script to execute
/// @param script_length The size of the script in bytes
/// @param timeout The maximum allowed execution time in microseconds
/// @param execution_time A pointer to which, if execution succeeds, the execution time in microseconds is written to
/// @param fresh_instance if true, forces the creation of a new instance of the target
/// @return A REPRL exit status (see below) or a negative number in case of an error
int reprl_execute(struct reprl_context* ctx, const char* script, uint64_t script_length, uint64_t timeout, uint64_t* execution_time, int fresh_instance);

/// Returns true if the execution terminated due to a signal.
int RIFSIGNALED(int status);

/// Returns true if the execution finished normally.
int RIFEXITED(int status);

/// Returns true if the execution terminated due to a timeout.
int RIFTIMEDOUT(int status);

/// Returns the terminating signal in case RIFSIGNALED is true.
int RTERMSIG(int status);

/// Returns the exit status in case RIFEXITED is true.
int REXITSTATUS(int status);

/// Returns the stdout data of the last successful execution if the context is capturing stdout, otherwise an empty string.
/// The output is limited to REPRL_MAX_FAST_IO_SIZE (currently 16MB).
/// @param ctx The REPRL context
/// @return A string pointer which is owned by the REPRL context and thus should not be freed by the caller
char* reprl_fetch_stdout(struct reprl_context* ctx);

/// Returns the stderr data of the last successful execution if the context is capturing stderr, otherwise an empty string.
/// The output is limited to REPRL_MAX_FAST_IO_SIZE (currently 16MB).
/// @param ctx The REPRL context
/// @return A string pointer which is owned by the REPRL context and thus should not be freed by the caller
char* reprl_fetch_stderr(struct reprl_context* ctx);

/// Returns the fuzzout data of the last successful execution.
/// The output is limited to REPRL_MAX_FAST_IO_SIZE (currently 16MB).
/// @param ctx The REPRL context
/// @return A string pointer which is owned by the REPRL context and thus should not be freed by the caller
char* reprl_fetch_fuzzout(struct reprl_context* ctx);

/// Returns a string describing the last error that occurred in the given context.
/// @param ctx The REPRL context
/// @return A string pointer which is owned by the REPRL context and thus should not be freed by the caller
char* reprl_get_last_error(struct reprl_context* ctx);

static int reprl_spawn_child(struct reprl_context* ctx);
static void reprl_terminate_child(struct reprl_context* ctx);
void remove_possible_unicode_characters(unsigned char *tmp);
static int internal_get_index_of_next_symbol_not_within_string(const char *content, char symbol);
static int internal_get_line_number_of_offset(const char *content, int offset);

// ######################## END REPRL DEFINES ########################

char **prog_argv = NULL;
char **environment = NULL;
int environment_length = 0;
extern char **environ;

struct reprl_context* current_reprl_context = NULL;

#define CHECK_SUCCESS(cond) if((cond) < 0) { perror(#cond); abort(); }
#define CHECK(cond) if(!(cond)) { fprintf(stderr, "(" #cond ") failed!"); abort(); }
#define unlikely(cond) __builtin_expect(!!(cond), 0)

static char *dup_str(const char *str);
int coverage_initialize(int shm_id);
uint32_t coverage_finish_initialization();
void coverage_shutdown();
void coverage_clear_bitmap();
static void coverage_internal_evaluate(uint8_t* virgin_bits, uint8_t* current_coverage_map, int *num_new_edges, int *num_edges);

static int coverage_evaluate_step1_check_for_new_coverage();
static void coverage_evaluate_step2_finish_query_coverage(int *num_new_edges, int *num_edges);

void coverage_save_virgin_bits_in_file(const char *filepath);
int coverage_load_virgin_bits_from_file(const char *filepath);

void coverage_backup_virgin_bits();
void coverage_restore_virgin_bits();

//int coverage_compare_equal(unsigned int* edges, uint64_t num_edges);
//int coverage_evaluate_crash();

static int get_number_edges(uint64_t* start, uint64_t* end);
static int get_number_edges_virgin(uint64_t* start, uint64_t* end);


#define SHM_SIZE 0x100000			// the size must be big enough for the target JS engine (v8)
#define MAX_EDGES ((SHM_SIZE - 4) * 8)


// Structure of the shared memory region.
struct shmem_data {
    uint32_t num_edges;
    uint8_t edges[];
};

struct cov_context {
    int id;	 // Id of this coverage context.
    uint8_t* virgin_bits;	// Bitmap of edges that have been discovered so far.
	uint8_t* virgin_bits_backup;	// I sometimes revert 
	
    //uint8_t* crash_bits;	// Bitmap of edges that have been discovered in crashing samples so far.
	uint8_t* coverage_map_backup;	// This is used to backup the result coverage map of one execution (if new coverage is found)
    //uint64_t num_edges;		// Total number of edges in the target program.
    uint64_t bitmap_size;	// Number of used bytes in the shmem->edges bitmap, roughly num_edges / 8.
    //uint64_t found_edges;	// Total number of edges that have been discovered so far.
    struct shmem_data* shmem;	// Pointer into the shared memory region.
};


struct cov_context context = {};



// ================ Start Python wrapped module ================
static PyObject *initialize(PyObject *self, PyObject *args);
static PyObject *finish_initialization(PyObject *self, PyObject *args);
static PyObject *spawn_child(PyObject *self, PyObject *args);
static PyObject *execute_script(PyObject *self, PyObject *args);
static PyObject *kill_child(PyObject *self, PyObject *args);
static PyObject *shutdown(PyObject *self, PyObject *args);
static PyObject *evaluate_coverage(PyObject *self, PyObject *args);
static PyObject *evaluate_coverage_step1_check_for_new_coverage(PyObject *self, PyObject *args);
static PyObject *evaluate_coverage_step2_finish_query_coverage(PyObject *self, PyObject *args);
static PyObject *save_global_coverage_map_in_file(PyObject *self, PyObject *args);
static PyObject *load_global_coverage_map_from_file(PyObject *self, PyObject *args);
static PyObject *backup_global_coverage_map(PyObject *self, PyObject *args);
static PyObject *restore_global_coverage_map(PyObject *self, PyObject *args);
static PyObject *get_index_of_next_symbol_not_within_string(PyObject *self, PyObject *args);
static PyObject *get_line_number_of_offset(PyObject *self, PyObject *args);



static PyMethodDef ExposedMethods[] = { 
	{"initialize",  initialize, METH_VARARGS},
	{"finish_initialization",  finish_initialization, METH_VARARGS},
	{"spawn_child",  spawn_child, METH_VARARGS}, 
	{"execute_script",  execute_script, METH_VARARGS},
	{"kill_child", kill_child, METH_VARARGS},
	{"shutdown", shutdown, METH_VARARGS},
	{"evaluate_coverage", evaluate_coverage, METH_VARARGS},
	{"save_global_coverage_map_in_file", save_global_coverage_map_in_file, METH_VARARGS},
	{"load_global_coverage_map_from_file", load_global_coverage_map_from_file, METH_VARARGS},
	{"backup_global_coverage_map", backup_global_coverage_map, METH_VARARGS},
	{"restore_global_coverage_map", restore_global_coverage_map, METH_VARARGS},
	{"evaluate_coverage_step1_check_for_new_coverage", evaluate_coverage_step1_check_for_new_coverage, METH_VARARGS},
	{"evaluate_coverage_step2_finish_query_coverage", evaluate_coverage_step2_finish_query_coverage, METH_VARARGS},
    {"get_index_of_next_symbol_not_within_string", get_index_of_next_symbol_not_within_string, METH_VARARGS},
	{"get_line_number_of_offset", get_line_number_of_offset, METH_VARARGS},
	{NULL, NULL}  /* Sentinel */
};



static struct PyModuleDef Definitions = {
	PyModuleDef_HEAD_INIT,
	"libJSEngine", /* name of module */
	NULL, /* module documentation, may be NULL */
	-1,   /* size of per-interpreter state of the module, or -1 if the module keeps state in global variables. */
	ExposedMethods
};

PyMODINIT_FUNC PyInit_libJSEngine(void) {
	return PyModule_Create(&Definitions);
}


static PyObject *initialize(PyObject *self, PyObject *args) {
	const char *d8_path;
	int shm_id;
	int ret;
	if (!PyArg_ParseTuple(args, "si", &d8_path, &shm_id)) { return NULL; }

    // The following call is important for the unicode-performance functions
    // It is required so that the mbrlen() function returns the correct length
    setlocale(LC_ALL, "");

	if(prog_argv != NULL) {
		free(prog_argv[0]);		// d8 path
		free(prog_argv);
	}

	// TODO: Don't hardcode the arguments like this. Pass them from Python
	prog_argv = malloc(9 * sizeof(char *));
	prog_argv[0] = dup_str(d8_path);
	prog_argv[1] = "--debug-code";
	prog_argv[2] = "--expose-gc";
	prog_argv[3] = "--single-threaded";
	prog_argv[4] = "--predictable";
	prog_argv[5] = "--allow-natives-syntax";
	prog_argv[6] = "--interrupt-budget=1024";
	prog_argv[7] = "--fuzzing";
	prog_argv[8] = NULL;

	// Now copy the environment
	char **env = environ;
	int listSZ;
	for (listSZ = 0; env[listSZ] != NULL; listSZ++) { }
	//printf("DEBUG: Number of environment variables = %d\n", listSZ);
	listSZ += 2;	// One more environment variable for the shared memory; One for null termination

	if(environment_length != 0 && environment != NULL) {
		// Free previous allocations
		for (int i = 0; i < (listSZ-1); i++) {
			free(environment[i]);
		}
		free(environment);
	}

	environment_length = listSZ;
	environment = malloc(listSZ * sizeof(char *));
	if (environment == NULL) {
		fprintf(stderr, "[libJSEngine] Memory allocation failed!\n");
 		exit(-1);
	}
	for (int i = 0; i < (listSZ-2); i++) {
		if ((environment[i] = dup_str(env[i])) == NULL) {
			fprintf(stderr, "[libJSEngine] Memory allocation failed!\n");
			exit(-1);
		}
	}
	char shm_key[1024];
	snprintf(shm_key, 1024, "SHM_ID=shm_id_%d_%d", getpid(), shm_id);
	environment[listSZ-2] = dup_str(shm_key);
	environment[listSZ-1] = NULL;

	current_reprl_context = reprl_create_context();
	ret = reprl_initialize_context(current_reprl_context, prog_argv, environment, 0, 1);	// capture: stdout=false; stderr=true
	if(ret == -1) {
		fprintf(stderr, "[libJSEngine] reprl_initialize_context() failed!\n");
		exit(-1);
	}
	coverage_initialize(shm_id);		// Initialize the coverage map
	return Py_BuildValue("i", 0);
}


static PyObject *finish_initialization(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	uint32_t num_edges = coverage_finish_initialization();
	return Py_BuildValue("I", num_edges);
}


static PyObject *kill_child(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	reprl_terminate_child(current_reprl_context);
	return Py_BuildValue("i", 0);
}


static PyObject *spawn_child(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }

	int ret = 0;
	ret = reprl_spawn_child(current_reprl_context);
	if(ret == -1) {
		fprintf(stderr, "[libJSEngine] Problem spawning child, trying it again after 5 seconds: %s\n", strerror(errno));
		sleep(5);
		ret = reprl_spawn_child(current_reprl_context);
		if(ret == -1) {
			fprintf(stderr, "[libJSEngine] ERROR - still failing to spawn a child: %s\n", strerror(errno));
			exit(-1);
		}
	}
	return Py_BuildValue("i", 0);
}


static PyObject *get_index_of_next_symbol_not_within_string(PyObject *self, PyObject *args) {
    char arg_symbol = 0;
    int arg_symbol_int = 0;
    const char *arg_content;
    int ret_value = -1;
    if (!PyArg_ParseTuple(args, "si", &arg_content, &arg_symbol_int)) { return NULL; }
    arg_symbol = (char)arg_symbol_int;
    // printf("Content:%s\n", arg_content);
    // printf("Symbol: %c\n", arg_symbol);
    ret_value = internal_get_index_of_next_symbol_not_within_string(arg_content, arg_symbol);
    return Py_BuildValue("i", ret_value);
}


static PyObject *get_line_number_of_offset(PyObject *self, PyObject *args) {
    const char *arg_content;
    int arg_offset = 0;
    int line_number = -1;
    if (!PyArg_ParseTuple(args, "si", &arg_content, &arg_offset)) { return NULL; }
    line_number = internal_get_line_number_of_offset(arg_content, arg_offset);
    return Py_BuildValue("i", line_number);
}


static PyObject *execute_script(PyObject *self, PyObject *args) {
	const char *arg_script_string;
	unsigned int arg_script_length;
	int arg_timeout;
	//struct reprl_result result = {};
	//memset(&result, 0x00, sizeof(struct reprl_result));
	int return_value = 0;
	int engine_was_restarted = 0;
	uint64_t real_execution_time = 0;

	if (!PyArg_ParseTuple(args, "si", &arg_script_string, &arg_timeout)) { return NULL; }

    //printf("in c code, script: %s\n", arg_script_string);

    // Calculate the script length
    // Note: That was a funny bug!
    // One would assume that just calculating the string length in python using using len(script_code) works
    // and this worked in 99,99 % of cases
    // (My previous code passed the length from python to the C code)
    // However, if the string contains unicode characters, it doesn't.
    // python calculates a length of 1 for 1 unicode character. However, python communicates with the C-module
    // which itself copies the BYTES to the d8 engine. And a unicode character consumes more than 1 byte
    // My first attempt was to calculate the number of bytes in Python, however, this also doesn't work
    // E.g.: unicode characters which consume 2 bytes in Python suddenly consume more bytes in C code
    // I think this is because of the Python distutils which maybe changes the bytes..
    // Conclusion: calculate the string length in C code and not in Python code..
    arg_script_length = strlen(arg_script_string);

    //printf("Arg script string: %s\n", arg_script_string);
    //printf("String length: %d\n", arg_script_length);
    //char tester[1000];
    //memset(tester, 0x00, 999);
    //memcpy(tester, arg_script_string, arg_script_length);
    //printf("Tester: %s\n", tester);

	arg_timeout = arg_timeout * 1000;// the REPRL code expects the timeout in seconds but I pass it in ms; the code later divides it by 1000 so I first multiply by 1000
	return_value = reprl_execute(current_reprl_context, arg_script_string, (int64_t)(arg_script_length), (int64_t)(arg_timeout), &real_execution_time, 0);
	//return_value = reprl_execute_script(arg_timeout, arg_script_string, (int64_t)(arg_script_length), &result);
	if(return_value == -1) {
		// Try it one more time with argument "fresh_instance" set to 1
		real_execution_time = 0;
		return_value = reprl_execute(current_reprl_context, arg_script_string, (int64_t)(arg_script_length), (int64_t)(arg_timeout), &real_execution_time, 1);
		if(return_value == -1) {
		    /*
			fprintf(stderr, "[libJSEngine] The JS engine seems to be not responsive, going to SLEEP\n");
			while(1) {
				// This loop will never end, but it keeps the engine running (if it's still running)
				// This gives time to attach a debugger to debug the problem
				sleep(60);
			}
			*/
			fprintf(stderr, "[libJSEngine] I seems like fuzzing was stopped via ctrl+c. Stopping...\n");
			// TODO: Maybe I can return here some status code to tell the JS engine to invoke the signal_handler
			// The signal handler could then dump the last results.
			_exit(-1);
		}
		engine_was_restarted = 1;
	}

	char *fuzz_output = reprl_fetch_fuzzout(current_reprl_context);
	remove_possible_unicode_characters((unsigned char *)fuzz_output);

	char *stderr_output = NULL;
	if(return_value == 0x04) {
		// process crashed, so get stderr output to understand root cause of crash (For not re-produceable crashes)
		stderr_output = reprl_fetch_stderr(current_reprl_context);
        remove_possible_unicode_characters((unsigned char *)stderr_output);
	} else {
		stderr_output = "";
	}
    // With stdout:
    // const char *stdout_output = reprl_fetch_stdout(current_reprl_context);
    // return Py_BuildValue("iksssi", return_value, real_execution_time, fuzz_output, stdout_output, stderr_output, engine_was_restarted);

    return Py_BuildValue("ikssi", return_value, real_execution_time, fuzz_output, stderr_output, engine_was_restarted);
}


void remove_possible_unicode_characters(unsigned char *tmp) {
    /*
    Ok, that was a crazy one which took me way too long to figure out...
    The testcase was something like:

    Infinity == parseInt('1000000000000000000000000000000000000000000000'
    + "\uD800");

    And my fuzzer added the following (pseudo) code during fuzzing / state file creation:

    Infinity == parseInt('1000000000000000000000000000000000000000000000'
    ,line_number += 1
    + "\uD800");
    fuzzilli(FUZZILLI_PRINT, line_number);

    The result is that it will also print to the fuzzer-stdout-channel the "\uD800" string (the 2nd line doesn't has a ";" at the end)
    This is unicode which means this C-library will reflect this string back to my Python code
    And during transformation to Python code it will attempt to unicode-encode the string.
    However, since I'm fuzzing, it is of course invalid unicode which means that this doesn't work.
    This leads to a python exception. (the exception occurs when invoking the execute_script() function;
    not in argument passing but instead when values are returned)

    => I'm therefore removing here all potential unicode symbols so that encoding can't lead to an exception
    */
    int idx = 0;
    while(tmp[idx] != 0x00) {
        if(tmp[idx] >= 0x80) {
            tmp[idx] = 0x20;    // Replace possible unicode symbols with spaces
        }
        ++idx;
    }
}


static PyObject *shutdown(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	reprl_terminate_child(current_reprl_context);
	coverage_shutdown();
	return Py_BuildValue("i", 0);
}

static PyObject *evaluate_coverage(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	int num_new_edges = 0;
	int num_edges = 0;		// num_edges will only be set if there are new edges (because of performance reasons)
    coverage_internal_evaluate(context.virgin_bits, context.shmem->edges, &num_new_edges, &num_edges);
	return Py_BuildValue("ii", num_new_edges, num_edges);
}




static PyObject *evaluate_coverage_step1_check_for_new_coverage(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	//printf("coverage_evaluate_step1_check_for_new_coverage() called\n");
	int has_new_coverage = coverage_evaluate_step1_check_for_new_coverage();
	return Py_BuildValue("i", has_new_coverage);
}


static PyObject *evaluate_coverage_step2_finish_query_coverage(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	//printf("evaluate_coverage_step2_finish_query_coverage() called\n");
	int num_new_edges = 0;
	int num_edges = 0;		// num_edges will only be set if there are new edges (because of performance reasons)
    coverage_evaluate_step2_finish_query_coverage(&num_new_edges, &num_edges);
	return Py_BuildValue("ii", num_new_edges, num_edges);
}



static PyObject *save_global_coverage_map_in_file(PyObject *self, PyObject *args) {
	const char *backup_filepath;
	if (!PyArg_ParseTuple(args, "s", &backup_filepath)) { return NULL; }
	coverage_save_virgin_bits_in_file(backup_filepath);
	return Py_BuildValue("i", 0);
}

static PyObject *load_global_coverage_map_from_file(PyObject *self, PyObject *args) {
	const char *backup_filepath;
	if (!PyArg_ParseTuple(args, "s", &backup_filepath)) { return NULL; }
	int number_edges = coverage_load_virgin_bits_from_file(backup_filepath);
	return Py_BuildValue("i", number_edges);
}


static PyObject *backup_global_coverage_map(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	coverage_backup_virgin_bits();
	return Py_BuildValue("i", 0);
}

static PyObject *restore_global_coverage_map(PyObject *self, PyObject *args) {
	if (!PyArg_ParseTuple(args, "")) { return NULL; }
	coverage_restore_virgin_bits();
	return Py_BuildValue("i", 0);
}

// ================ End Python wrapped module ================

// ================ Start helper functions ==================
static char *dup_str(const char *str) {
	size_t len = strlen(str) + 1;
	char *dup = malloc(len);
	if (dup != NULL)
		memmove(dup, str, len);
	return dup;
}
// ================ End helper functions ==================


// ================ Start performance functions ==================
// This are functions originally developed in Python and which were ported to C to increase the
// performance of the fuzzer
static int internal_get_line_number_of_offset(const char *content, int offset) {
    size_t len = 0;
    int current_line_number = 0;
    int skipped_unicode_bytes = 0;
    int i = 0;
    for (i = 0; content[i] != '\0'; ++i) {
        if((i-skipped_unicode_bytes) >= offset) {
            return current_line_number;
        }
        if(content[i] == '\n') {
            current_line_number += 1;
        } else if((unsigned int)(content[i]) >= 0x80) {
            // Calculate unicode characters with the correct length
            len = mbrlen(&content[i], 4, NULL);
            //printf("mbrlen returned %d\n", len);
            if(len != (size_t)-1) {
                len -= 1;   // -1 because at the start of the next iteration I will +1 anyway
                i += len;   // Skip the remaining unicode bytes from the current character
                skipped_unicode_bytes += len;
            }      
        }
    }
    if((i-skipped_unicode_bytes) == offset) {
        // This is the offset at the end of the testcase (e.g. for an append operation)
        // and should also return the correct line number (and not -1)     
        return current_line_number;
    }
    return -1;
}



// If you find this function, just skip over it and don't waste time trying to understand whats going on..
// The function was written after one.. two.. ok, maybe multiple beer.
// Woke up next morning, had no memory, but a working function. I don't know what this code is exactly doing,
// but it seems to work.
// Later I ported the code from Python to C code to boost performance, but it seems to still work.
static int internal_get_index_of_next_symbol_not_within_string(const char *content, const char symbol) {
    if(symbol == '\\' || symbol == '*') {
        printf("TODO, this symbol is currently not supported: %c\n", symbol);
        _exit(-1);
    }
    unsigned int idx = 0;
    bool in_str_double_quote = false;
    bool in_str_single_quote = false;
    bool in_template_str = false;
    bool in_regex_str = false;
    bool previous_forward_slash = false;
    bool previous_backward_slash = false;
    bool in_multiline_comment = false;
    bool previous_was_star = false;
    int bracket_depth = 0;
    int curly_bracket_depth = 0;
    int square_bracket_depth = 0;
    char current_char = 0x00;
    unsigned int content_len = strlen(content);
    size_t len = 0;
    int skipped_unicode_bytes = 0;

    for(idx = 0; idx < content_len; ++idx) {
        current_char = content[idx];
        //printf("Current char: %s\n", current_char);
        if(in_multiline_comment == true && !(current_char == '*' || current_char == '/')) {
            previous_was_star = false;
            previous_backward_slash = false;
            previous_forward_slash = false;
            continue;    // ignore stuff inside multi-line comments
        }
        if(current_char == '"') {
            if(in_str_single_quote || in_template_str || in_regex_str) {
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(previous_backward_slash) {
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(current_char == symbol) {
                return idx - skipped_unicode_bytes;
            }
            in_str_double_quote = !in_str_double_quote;
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == '\'') {
            if(in_str_double_quote || in_template_str || in_regex_str) {
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(previous_backward_slash) {
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(current_char == symbol) {
                return idx - skipped_unicode_bytes;
            }
            in_str_single_quote = !in_str_single_quote;
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == '`') {
            if(in_str_double_quote || in_str_single_quote || in_regex_str) {
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(previous_backward_slash) {
                // `\`` === '`' // --> true
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;
            }
            if(current_char == symbol) {
                return idx - skipped_unicode_bytes;
            }
            in_template_str = !in_template_str;
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == '/') {
            if(previous_was_star == true) {
                // This means we were in a multi-line comment && it now terminated
                previous_was_star = false;
                in_multiline_comment = false;
                previous_forward_slash = false;
                previous_backward_slash = false;
                continue;    // ignore the current character && continue with next character normally
            }
            if(in_str_double_quote || in_str_single_quote || in_template_str) {
                // inside a string
                previous_backward_slash = false;
                continue;
            } else {
                if(previous_forward_slash == true) {
                    // That means we are inside a comment
                    // TODO implement
                    in_regex_str = false;
                } else {
                    // That means it's the first /
                    if(!previous_backward_slash) {
                        // in_regex_str = !in_regex_str # that means it could be an regex str
                        // pass
                        if(current_char == symbol) {
                            return idx - skipped_unicode_bytes;
                        }
                        // for the moment I ignore the regex strings which look e.g.: like:
                        // /abc+/i
                        // Reason: it can also be math code like a division like:
                        // 0/0
                        // I don't know how I can differentiate here...
                    }
                }
                previous_forward_slash = true;
            }
            previous_backward_slash = false;
        } else if(current_char == '\\') {
            previous_backward_slash = !previous_backward_slash;
            previous_forward_slash = false;
        } else if(current_char == '*') {
            if(in_multiline_comment) {
                previous_was_star = true;
                continue;
            }
            if(previous_forward_slash == true) {
                // Start of a multi line comment
                in_multiline_comment = true;
            }
        } else if(current_char == '{') {
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                // We are not inside a string or comment
                // TODO: I don't check here for simple comments like // bla
                if(previous_backward_slash == false) {
                    if(current_char == symbol) {
                        return idx - skipped_unicode_bytes;
                    }
                    curly_bracket_depth += 1;
                }
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == '[') {
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                // We are not inside a string or comment
                // TODO: I don't check here for simple comments like // bla
                if(previous_backward_slash == false) {
                    if(current_char == symbol) {
                        return idx - skipped_unicode_bytes;
                    }
                    square_bracket_depth += 1;
                }
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == ']') {
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                // We are not inside a string or comment
                // TODO: I don't check here for simple comments like // bla
                if(current_char == symbol) {
                    if(square_bracket_depth == 0) {
                        return idx - skipped_unicode_bytes;
                    }
                }
                square_bracket_depth -= 1;
            }
            previous_forward_slash = false;
            previous_backward_slash = false; 
        } else if(current_char == '(') {
            //print("Start (")
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                // We are not inside a string or comment
                // TODO: I don't check here for simple comments like // bla
                if(previous_backward_slash == false) {
                    if(current_char == symbol) {
                        return idx - skipped_unicode_bytes;
                    }
                    bracket_depth += 1;
                }
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == ')') {
            // print("End )")
            // print(in_str_double_quote)
            // print(in_str_single_quote)
            // print(in_regex_str)
            // print(in_template_str)
            // print(bracket_depth)

            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                //  We are not inside a string or comment
                //  TODO: I don't check here for simple comments like // bla
                if(current_char == symbol) {
                    if(bracket_depth == 0) {
                        return idx - skipped_unicode_bytes;
                    }
                }
                bracket_depth -= 1;
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == '}') {
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                //  We are not inside a string or comment
                //  TODO: I don't check here for simple comments like // bla
                if(current_char == symbol) {
                    if(curly_bracket_depth == 0) {
                        return idx - skipped_unicode_bytes;
                    }
                }
                curly_bracket_depth -= 1;
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else if(current_char == ',') {
            if(in_str_double_quote == false && in_str_single_quote == false && in_template_str == false && in_multiline_comment == false && in_regex_str == false) {
                //  We are not inside a string or comment
                if(current_char == symbol) {
                    if(bracket_depth == 0 && curly_bracket_depth == 0 && square_bracket_depth == 0) {
                        return idx - skipped_unicode_bytes;
                    }
                }
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
        } else {
            if(current_char == symbol) {
                return idx - skipped_unicode_bytes;
            }
            previous_forward_slash = false;
            previous_backward_slash = false;
            
            // Fix for unicode strings
            if((unsigned int)current_char >= 0x80) {
                len = mbrlen(&content[idx], 4, NULL);   // TODO the 4 can maybe crash if the unicode character is at the end; Maybe I should dynamically calculate it
                if(len != (size_t)-1) {
                    len -= 1;   // -1 because at the start of the next iteration I will +1 anyway
                    idx += len;
                    skipped_unicode_bytes += len;
                }
            }
        }
    }
    return -1;       //  Symbol is not within the content
}

// ================ Start REPRL code =======================



#define REPRL_CHILD_CTRL_IN 100
#define REPRL_CHILD_CTRL_OUT 101
#define REPRL_CHILD_DATA_IN 102
#define REPRL_CHILD_DATA_OUT 103

#define MIN(x, y) ((x) < (y) ? (x) : (y))

static uint64_t current_usecs()
{
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000000 + ts.tv_nsec / 1000;
}



static int reprl_error(struct reprl_context* ctx, const char *format, ...)
{
    va_list args;
    va_start(args, format);
    free(ctx->last_error);
    int ret = vasprintf(&ctx->last_error, format, args);
    if(ret == -1) { fprintf(stderr, "vasprintf() failed: %s\n", strerror(errno)); _exit(-1);}
    return -1;
}

static struct data_channel* reprl_create_data_channel(struct reprl_context* ctx)
{
    int fd = memfd_create("REPRL_DATA_CHANNEL", MFD_CLOEXEC);
    if (fd == -1 || ftruncate(fd, REPRL_MAX_DATA_SIZE) != 0) {
        reprl_error(ctx, "Failed to create data channel file: %s", strerror(errno));
        return NULL;
    }
    char* mapping = mmap(0, REPRL_MAX_DATA_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
    if (mapping == MAP_FAILED) {
        reprl_error(ctx, "Failed to mmap data channel file: %s", strerror(errno));
        return NULL;
    }
    
    struct data_channel* channel = malloc(sizeof(struct data_channel));
    channel->fd = fd;
    channel->mapping = mapping;
    return channel;
}

static void reprl_destroy_data_channel(struct reprl_context* ctx, struct data_channel* channel)
{
    if (!channel) return;
    close(channel->fd);
    munmap(channel->mapping, REPRL_MAX_DATA_SIZE);
    free(channel);
}

static void reprl_child_terminated(struct reprl_context* ctx)
{
    if (!ctx->pid) return;
    ctx->pid = 0;
    close(ctx->ctrl_in);
    close(ctx->ctrl_out);
}

static void reprl_terminate_child(struct reprl_context* ctx)
{
    if (!ctx->pid) return;
    int status;
    kill(ctx->pid, SIGKILL);
    waitpid(ctx->pid, &status, 0);
    reprl_child_terminated(ctx);
}

static int reprl_spawn_child(struct reprl_context* ctx)
{
	int ret = 0;
    // This is also a good time to ensure the data channel backing files don't grow too large.
    ret = ftruncate(ctx->data_in->fd, REPRL_MAX_DATA_SIZE);
	if(ret != 0) { fprintf(stderr, "ftruncate() failed: %s\n", strerror(errno)); _exit(-1);}
    ret = ftruncate(ctx->data_out->fd, REPRL_MAX_DATA_SIZE);
	if(ret != 0) { fprintf(stderr, "ftruncate() failed: %s\n", strerror(errno)); _exit(-1);}
    if (ctx->stdout) {
		ret = ftruncate(ctx->stdout->fd, REPRL_MAX_DATA_SIZE);
		if(ret != 0) { fprintf(stderr, "ftruncate() failed: %s\n", strerror(errno)); _exit(-1);}
	}
    if (ctx->stderr) {
		ret = ftruncate(ctx->stderr->fd, REPRL_MAX_DATA_SIZE);
		if(ret != 0) { fprintf(stderr, "ftruncate() failed: %s\n", strerror(errno)); _exit(-1);}
	}
    
    int crpipe[2] = { 0, 0 };          // control pipe child -> reprl
    int cwpipe[2] = { 0, 0 };          // control pipe reprl -> child

    if (pipe(crpipe) != 0) {
        return reprl_error(ctx, "Could not create pipe for REPRL communication: %s", strerror(errno));
    }
    if (pipe(cwpipe) != 0) {
        close(crpipe[0]);
        close(crpipe[1]);
        return reprl_error(ctx, "Could not create pipe for REPRL communication: %s", strerror(errno));
    }

    ctx->ctrl_in = crpipe[0];
    ctx->ctrl_out = cwpipe[1];
    fcntl(ctx->ctrl_in, F_SETFD, FD_CLOEXEC);
    fcntl(ctx->ctrl_out, F_SETFD, FD_CLOEXEC);

    int pid = fork();
    if (pid == 0) {
        if (dup2(cwpipe[0], REPRL_CHILD_CTRL_IN) < 0 ||
            dup2(crpipe[1], REPRL_CHILD_CTRL_OUT) < 0 ||
            dup2(ctx->data_out->fd, REPRL_CHILD_DATA_IN) < 0 ||
            dup2(ctx->data_in->fd, REPRL_CHILD_DATA_OUT) < 0) {
            fprintf(stderr, "dup2 failed in the child: %s\n", strerror(errno));
            _exit(-1);
        }

        close(cwpipe[0]);
        close(crpipe[1]);

        int devnull = open("/dev/null", O_RDWR);
        dup2(devnull, 0);
		
		// The following lines can be commented out to see the stdout/stderr of the JS engine in the main console (for debugging)
        if (ctx->stdout) dup2(ctx->stdout->fd, 1);
        else dup2(devnull, 1);
        if (ctx->stderr) dup2(ctx->stderr->fd, 2);
        else dup2(devnull, 2);

        close(devnull);
        
        // close all other FDs. We try to use FD_CLOEXEC everywhere, but let's be extra sure we don't leak any fds to the child.
        int tablesize = getdtablesize();
        for (int i = 3; i < tablesize; i++) {
            if (i == REPRL_CHILD_CTRL_IN || i == REPRL_CHILD_CTRL_OUT || i == REPRL_CHILD_DATA_IN || i == REPRL_CHILD_DATA_OUT) {
                continue;
            }
            close(i);
        }
        execve(ctx->argv[0], ctx->argv, ctx->envp);
        
        fprintf(stderr, "Failed to execute child process %s: %s\n", ctx->argv[0], strerror(errno));
        fflush(stderr);
        _exit(-1);
    }
    
    close(crpipe[1]);
    close(cwpipe[0]);
    
    if (pid < 0) {
        close(ctx->ctrl_in);
        close(ctx->ctrl_out);
        return reprl_error(ctx, "Failed to fork: %s", strerror(errno));
    }
    ctx->pid = pid;

    char helo[5] = { 0 };
    if (read(ctx->ctrl_in, helo, 4) != 4) {
        reprl_terminate_child(ctx);
        return reprl_error(ctx, "Did not receive HELO message from child: %s", strerror(errno));
    }
    
    if (strncmp(helo, "HELO", 4) != 0) {
        reprl_terminate_child(ctx);
        return reprl_error(ctx, "Received invalid HELO message from child: %s", helo);
    }
    
    if (write(ctx->ctrl_out, helo, 4) != 4) {
        reprl_terminate_child(ctx);
        return reprl_error(ctx, "Failed to send HELO reply message to child: %s", strerror(errno));
    }

    return 0;
}

struct reprl_context* reprl_create_context()
{
    // "Reserve" the well-known REPRL fds so no other fd collides with them.
    // This would cause various kinds of issues in reprl_spawn_child.
    // It would be enough to do this once per process in the case of multiple
    // REPRL instances, but it's probably not worth the implementation effort.
    int devnull = open("/dev/null", O_RDWR);
    dup2(devnull, REPRL_CHILD_CTRL_IN);
    dup2(devnull, REPRL_CHILD_CTRL_OUT);
    dup2(devnull, REPRL_CHILD_DATA_IN);
    dup2(devnull, REPRL_CHILD_DATA_OUT);
    close(devnull);

    struct reprl_context* ctx = malloc(sizeof(struct reprl_context));
    memset(ctx, 0, sizeof(struct reprl_context));
    return ctx;
}
                    
int reprl_initialize_context(struct reprl_context* ctx, char** argv, char** envp, int capture_stdout, int capture_stderr)
{
    if (ctx->initialized) {
        return reprl_error(ctx, "Context is already initialized");
    }
    
    // We need to ignore SIGPIPE since we could end up writing to a pipe after our child process has exited.
    signal(SIGPIPE, SIG_IGN);
    
	ctx->argv = argv;
	ctx->envp = envp;
    //ctx->argv = copy_string_array(argv);
    //ctx->envp = copy_string_array(envp);
    
    ctx->data_in = reprl_create_data_channel(ctx);
    ctx->data_out = reprl_create_data_channel(ctx);
    if (capture_stdout) {
        ctx->stdout = reprl_create_data_channel(ctx);
    }
    if (capture_stderr) {
        ctx->stderr = reprl_create_data_channel(ctx);
    }
    if (!ctx->data_in || !ctx->data_out || (capture_stdout && !ctx->stdout) || (capture_stderr && !ctx->stderr)) {
        // Proper error message will have been set by reprl_create_data_channel
        return -1;
    }
    
    ctx->initialized = 1;
    return 0;
}

void reprl_destroy_context(struct reprl_context* ctx)
{
    reprl_terminate_child(ctx);
    
    //free_string_array(ctx->argv);
    //free_string_array(ctx->envp);
    
    reprl_destroy_data_channel(ctx, ctx->data_in);
    reprl_destroy_data_channel(ctx, ctx->data_out);
    reprl_destroy_data_channel(ctx, ctx->stdout);
    reprl_destroy_data_channel(ctx, ctx->stderr);
    
    free(ctx->last_error);
    free(ctx);
}

int reprl_execute(struct reprl_context* ctx, const char* script, uint64_t script_length, uint64_t timeout, uint64_t* execution_time, int fresh_instance)
{
    if (!ctx->initialized) {
        return reprl_error(ctx, "REPRL context is not initialized");
    }
    if (script_length > REPRL_MAX_DATA_SIZE) {
        return reprl_error(ctx, "Script too large");
    }
    
    // Terminate any existing instance if requested.
    if (fresh_instance && ctx->pid) {
        reprl_terminate_child(ctx);
    }
    
    // Reset file position so the child can simply read(2) and write(2) to these fds.
    lseek(ctx->data_out->fd, 0, SEEK_SET);
    lseek(ctx->data_in->fd, 0, SEEK_SET);
    if (ctx->stdout) {
        lseek(ctx->stdout->fd, 0, SEEK_SET);
    }
    if (ctx->stderr) {
        lseek(ctx->stderr->fd, 0, SEEK_SET);
    }
    
    // Spawn a new instance if necessary.
    if (!ctx->pid) {
        int r = reprl_spawn_child(ctx);
        if (r != 0) return r;
    }

    // Copy the script to the data channel.
    memcpy(ctx->data_out->mapping, script, script_length);

    // Note:
    // I think resetting the current coverage map (in shared memory) here is not required because
    // the code in d8 should already reset it. However, I detected some flaws (especially when the global coverage map
    // was restored. I therefore added also the call here to just get 100% sure
    // If I later start to boost performance I can maybe remove this code again
    // (since this code will be executed in every iteration)
    // TODO: Check this
    coverage_clear_bitmap(); 

    // Tell child to execute the script.
    if (write(ctx->ctrl_out, "exec", 4) != 4 ||
        write(ctx->ctrl_out, &script_length, 8) != 8) {
        // These can fail if the child unexpectedly terminated between executions.
        // Check for that here to be able to provide a better error message.
        int status;
        if (waitpid(ctx->pid, &status, WNOHANG) == ctx->pid) {
            reprl_child_terminated(ctx);
            if (WIFEXITED(status)) {
                return reprl_error(ctx, "Child unexpectedly exited with status %i between executions", WEXITSTATUS(status));
            } else {
                return reprl_error(ctx, "Child unexpectedly terminated with signal %i between executions", WTERMSIG(status));
            }
        }
        return reprl_error(ctx, "Failed to send command to child process: %s", strerror(errno));
    }

    // Wait for child to finish execution (or crash).
    int timeout_ms = timeout / 1000;
    uint64_t start_time = current_usecs();
    struct pollfd fds = {.fd = ctx->ctrl_in, .events = POLLIN, .revents = 0};
    int res = poll(&fds, 1, timeout_ms);
    *execution_time = current_usecs() - start_time;
    if (res == 0) {
        // Execution timed out. Kill child and return a timeout status.
        reprl_terminate_child(ctx);
        return 1 << 16;
    } else if (res != 1) {
        // An error occurred.
        // We expect all signal handlers to be installed with SA_RESTART, so receiving EINTR here is unexpected and thus also an error.
        return reprl_error(ctx, "Failed to poll: %s", strerror(errno));
    }
    
    // Poll succeeded, so there must be something to read now (either the status or EOF).
    int status;
    ssize_t rv = read(ctx->ctrl_in, &status, 4);
    if (rv < 0) {
        return reprl_error(ctx, "Failed to read from control pipe: %s", strerror(errno));
    } else if (rv != 4) {
        // Most likely, the child process crashed and closed the write end of the control pipe.
        // Unfortunately, there probably is nothing that guarantees that waitpid() will immediately succeed now,
        // and we also don't want to block here. So just retry waitpid() a few times...
        int success = 0;
        do {
            success = waitpid(ctx->pid, &status, WNOHANG) == ctx->pid;
            if (!success) usleep(10);
        } while (!success && current_usecs() - start_time < timeout);
        
        if (!success) {
            // Wait failed, so something weird must have happened. Maybe somehow the control pipe was closed without the child exiting?
            // Probably the best we can do is kill the child and return an error.
            reprl_terminate_child(ctx);
            return reprl_error(ctx, "Child in weird state after execution");
        }

        // Cleanup any state related to this child process.
        reprl_child_terminated(ctx);

        if (WIFEXITED(status)) {
            status = WEXITSTATUS(status) << 8;
        } else if (WIFSIGNALED(status)) {
            status = WTERMSIG(status);
        } else {
            // This shouldn't happen, since we don't specify WUNTRACED for waitpid...
            return reprl_error(ctx, "Waitpid returned unexpected child state %i", status);
        }
    }
    
    // The status must be a positive number, see the status encoding format below.
    // We also don't allow the child process to indicate a timeout. If we wanted,
    // we could treat it as an error if the upper bits are set.
    status &= 0xffff;

    return status;
}

/// The 32bit REPRL exit status as returned by reprl_execute has the following format:
///     [ 00000000 | did_timeout | exit_code | terminating_signal ]
/// Only one of did_timeout, exit_code, or terminating_signal may be set at one time.
int RIFSIGNALED(int status) {
    return (status & 0xff) != 0;
}

int RIFEXITED(int status) {
    return !RIFSIGNALED(status) && !RIFTIMEDOUT(status);
}

int RIFTIMEDOUT(int status) {
    return (status & 0xff0000) != 0;
}

int RTERMSIG(int status) {
    return status & 0xff;
}

int REXITSTATUS(int status) {
    return (status >> 8) & 0xff;
}

static char* fetch_data_channel_content(struct data_channel* channel) {
    if (!channel) return "";
    size_t pos = lseek(channel->fd, 0, SEEK_CUR);
    pos = MIN(pos, REPRL_MAX_DATA_SIZE - 1);
    channel->mapping[pos] = 0;
    return channel->mapping;
}

char* reprl_fetch_fuzzout(struct reprl_context* ctx) {
    return fetch_data_channel_content(ctx->data_in);
}

char* reprl_fetch_stdout(struct reprl_context* ctx) {
    return fetch_data_channel_content(ctx->stdout);
}

char* reprl_fetch_stderr(struct reprl_context* ctx) {
    return fetch_data_channel_content(ctx->stderr);
}

char* reprl_get_last_error(struct reprl_context* ctx) {
    return ctx->last_error;
}


// ===================== End REPRL Code =========================




// ===================== Start code coverage code ======================



int coverage_initialize(int shm_id) {
	char shm_key[1024];
	snprintf(shm_key, 1024, "shm_id_%d_%d", getpid(), shm_id);
	context.id = shm_id;
	if(context.shmem != NULL) {
		coverage_shutdown();
	}
	int fd = shm_open(shm_key, O_RDWR | O_CREAT, S_IREAD | S_IWRITE);
	if (fd <= -1) {
		fprintf(stderr, "Failed to create shared memory region\n");
		return -1;
	}
	int tmp_ret = ftruncate(fd, SHM_SIZE);
	if(tmp_ret != 0) {
		fprintf(stderr, "ftruncate() failed\n");
		return -1;
	}

	if(context.shmem != NULL) {
		munmap(context.shmem, SHM_SIZE);
	}
	context.shmem = mmap(0, SHM_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
	close(fd);	

	// The correct bitmap size is calculated in the >coverage_finish_initialization< function
	// This function must be called after the first execution, however, the first execution
	// Already uses the bitmap_size. I therefore set it here to zero so that the
	// coverage_clear_bitmap() function does not write something in the first call
	context.bitmap_size	= 0;	

	// printf("Mapped %s to %p\n", shm_key, context.shmem);
	return 0;
}


// The num_edges variable depends on the JS engine and gets initialized
// during the first execution. Therefore this function must be called once
// after the first execution.
// The num_edges can be calculated based on the size of the loaded module
uint32_t coverage_finish_initialization() {
    uint64_t num_edges = context.shmem->num_edges;
    uint64_t bitmap_size = (num_edges + 7) / 8;
    if (num_edges > MAX_EDGES) {
        fprintf(stderr, "[libJSEngine] Too many edges\n");
        exit(-1);           // TODO
    }
    
    context.bitmap_size = bitmap_size;
    
	if(context.virgin_bits != NULL) {
		free(context.virgin_bits);
	}
	if(context.virgin_bits_backup != NULL) {
		free(context.virgin_bits_backup);
	}
	/*
	if(context.crash_bits != NULL) {
		free(context.crash_bits);
	}
	*/
	if(context.coverage_map_backup != NULL) {
		free(context.coverage_map_backup);
	}

    context.virgin_bits = malloc(bitmap_size);
	context.virgin_bits_backup = malloc(bitmap_size);
    // context.crash_bits = malloc(bitmap_size);
	context.coverage_map_backup = malloc(bitmap_size);	// To filter unreliable results I need to backup the coverage map of a run if new coverage is triggered
    memset(context.virgin_bits, 0xff, bitmap_size);
	coverage_backup_virgin_bits();
    // memset(context.crash_bits, 0xff, bitmap_size);
	// context.coverage_map_backup must not be initialized because it's always written first before it is read

	return (uint32_t)num_edges;	// Should be no problem because >context.shmem->num_edges< is also just uint32_t
}


void coverage_save_virgin_bits_in_file(const char *filepath) {
	FILE *write_ptr= fopen(filepath,"wb");  // w for write, b for binary
	fwrite(context.virgin_bits,context.bitmap_size,1,write_ptr);
	fclose(write_ptr);
}

int coverage_load_virgin_bits_from_file(const char *filepath) {
	FILE *ptr = fopen(filepath,"rb");
	if (fread(context.virgin_bits, context.bitmap_size,1,ptr) == 0) {
	    // This error occurs when you update the JS engine and try to load an old coverage map with a new JS engine
		fprintf(stderr, "Fread() error in coverage_load_virgin_bits_from_file(). Was the coverage map created with this JS engine?\n");
 		exit(-1);
	}
	coverage_backup_virgin_bits();
	fclose(ptr);

    coverage_clear_bitmap();    // This call is important: Otherwise an execute-call after the load virgin bits call will lead to incorrect results 

	return get_number_edges_virgin((uint64_t*)context.virgin_bits, (uint64_t*)(context.virgin_bits + context.bitmap_size));
}

void coverage_backup_virgin_bits() {
	memcpy(context.virgin_bits_backup, context.virgin_bits, context.bitmap_size);
}

// Restores the virgin bits to the original value or to the value stored via the
// coverage_backup_virgin_bits() function call
void coverage_restore_virgin_bits() {
	memcpy(context.virgin_bits, context.virgin_bits_backup, context.bitmap_size);
}

void coverage_shutdown() {
    char shm_key[1024];
    snprintf(shm_key, 1024, "shm_id_%d_%d", getpid(), context.id);
    shm_unlink(shm_key);
}

static inline int coverage_is_edge_set(const uint8_t* bits, uint64_t index) {
    return (bits[index / 8] >> (index % 8)) & 0x1;
}

// A zero means edge is set in virgin map
static inline int virgin_is_edge_set(const uint8_t* bits, uint64_t index) {
    return 1 - coverage_is_edge_set(bits, index);
}

static inline void coverage_mark_edge_as_visited(uint8_t* bits, uint64_t index) {
    bits[index / 8] &= ~(1u << (index % 8));
}


static int get_number_edges(uint64_t* start, uint64_t* end) {
	uint64_t* current = start;
	int tmp_count_edges = 0;
	while (current < end) {
		if (*current) {
			uint64_t index = ((uintptr_t)current - (uintptr_t)start) * 8;
			for (uint64_t i = index; i < index + 64; i++) {
				if (coverage_is_edge_set((const uint8_t*)start, i) == 1) {
					tmp_count_edges += 1;
				}
			}
		}
		current++;
	}
	return tmp_count_edges;
}

// In Virgin map an edge is a 0 and not a 1
static int get_number_edges_virgin(uint64_t* start, uint64_t* end) {
	uint64_t* current = start;
	int tmp_count_edges = 0;
	while (current < end) {
		uint64_t index = ((uintptr_t)current - (uintptr_t)start) * 8;
		for (uint64_t i = index; i < index + 64; i++) {
			if (virgin_is_edge_set((const uint8_t*)start, i) == 1) {
				tmp_count_edges += 1;
			}
		}
		current++;
	}
	return tmp_count_edges;
}


static int coverage_internal_has_new_coverage(uint8_t* virgin_bits, uint8_t* current_coverage_map) {
	uint64_t* current = (uint64_t*)current_coverage_map;
    uint64_t* end = (uint64_t*)(current_coverage_map + context.bitmap_size);
    uint64_t* virgin = (uint64_t*)virgin_bits;

/*
	while (current < end) {
        if (*current && unlikely(*current & *virgin)) {
            // New edge(s) found!
            return 1;
        }
        current++;
        virgin++;
    }
	return 0;
	*/

	int tmp_count_new_edges = 0;
 
    while (current < end) {
        if (*current && unlikely(*current & *virgin)) {
            // New edge(s) found!
            uint64_t index = ((uintptr_t)current - (uintptr_t)current_coverage_map) * 8;
            for (uint64_t i = index; i < index + 64; i++) {
                if (coverage_is_edge_set(current_coverage_map, i) == 1 && coverage_is_edge_set(virgin_bits, i) == 1) {
                    tmp_count_new_edges += 1;
                }
            }
        }
        current++;
        virgin++;
    }	
	return tmp_count_new_edges;
}

static void coverage_internal_evaluate(uint8_t* virgin_bits, uint8_t* current_coverage_map, int *num_new_edges, int *num_edges) {
    uint64_t* current = (uint64_t*)current_coverage_map;
    uint64_t* end = (uint64_t*)(current_coverage_map + context.bitmap_size);
    uint64_t* virgin = (uint64_t*)virgin_bits;
	int tmp_count_new_edges = 0;
 
	//printf("UPDATE COVERAGE MAP\n");
    while (current < end) {
        if (*current && unlikely(*current & *virgin)) {
            // New edge(s) found!
            uint64_t index = ((uintptr_t)current - (uintptr_t)current_coverage_map) * 8;
            for (uint64_t i = index; i < index + 64; i++) {
                if (coverage_is_edge_set(current_coverage_map, i) == 1 && coverage_is_edge_set(virgin_bits, i) == 1) {
					coverage_mark_edge_as_visited(virgin_bits, i);
                    tmp_count_new_edges += 1;
                }
            }
        }
        current++;
        virgin++;
    }
	
	// Calculate number of edges (only if there was a new edge)
	if(tmp_count_new_edges > 0) {
		// If there was a new edge I also want to know how many edges the testcase triggers
		// This can be used to focus fuzzing samples which trigger more code
		*num_edges = get_number_edges((uint64_t*)current_coverage_map, (uint64_t*)(current_coverage_map + context.bitmap_size));
	} else {
		*num_edges = 0;	// Set it to zero if we don't query the exact number
	}

	// Return the values
	*num_new_edges = tmp_count_new_edges;
}

/*
static void print_hash_debugging(uint8_t* coverage_map) {
	uint64_t* current = (uint64_t*)coverage_map;
    uint64_t* end = (uint64_t*)(coverage_map + context.bitmap_size);

	int result = 0;
 
    while (current < end) {
        if (*current) {
            result += *current;		// Will overflow, but I just want to quickly debug
        }
        current++;
    }	
	printf("Result: %i\n", result);
}
*/


static int coverage_evaluate_step1_check_for_new_coverage() {
	int num_new_edges = coverage_internal_has_new_coverage(context.virgin_bits, context.shmem->edges);
	if(num_new_edges != 0) {
		// New coverage was found, however the coverage map was not updated yet
		// This new coverage can be new indeterministic behavior and to verify that it is 
		// really new triggered functionality, the code is executed again
		// After the second execution the function >coverage_evaluate_step2_finish_query_coverage()<
		// is called. This function would update the coverage map with the newly found coverage
		// (this is also done to remove indeterministic behavior so that this isn't detect later again)
		// For this a backup of the coverage map must be created
		memcpy(context.coverage_map_backup, context.shmem->edges, context.bitmap_size);
	}
	return num_new_edges;
}


static void coverage_evaluate_step2_finish_query_coverage(int *num_new_edges, int *num_edges) {
	int num_new_edges_second = 0;
	int num_edges_second = 0;
	int num_new_edges_first = 0;
	int num_edges_first = 0;

	uint8_t* virgin_bits = context.virgin_bits;

	int has_second_code_also_new_coverage = coverage_internal_has_new_coverage(context.virgin_bits, context.shmem->edges);

	// Let's first update the the coverage map with the FIRST execution results
	// This is important because the function returns the execution result of the FIRST execution
	// If the 2nd would be updated first, the "num_new_edges" could be too low

	coverage_internal_evaluate(virgin_bits, context.coverage_map_backup, &num_new_edges_first, &num_edges_first);

	// Update the coverage map with the SECOND result
	coverage_internal_evaluate(virgin_bits, context.shmem->edges, &num_new_edges_second, &num_edges_second);

	if(has_second_code_also_new_coverage != 0) {
		// Return the first results
		*num_new_edges = num_new_edges_first;
		*num_edges = num_edges_first;
	} else {
		// New coverage was NOT triggered again, that means the new coverage from the first execution was indeterministic behavior
		// => Return num_new_edges as zero which says this sample did not trigger new behavior
		*num_new_edges = 0;
		*num_edges = 0;
	}
}


// Sets the coverage back to zero (should be called before every execution)
void coverage_clear_bitmap() {
    memset(context.shmem->edges, 0, context.bitmap_size);
}


// ===================== End code coverage code ======================
