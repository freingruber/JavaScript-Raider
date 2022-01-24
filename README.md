# JavaScript Raider:

JavaScript Raider is a coverage-guided JavaScript fuzzing framework designed for the v8 JavaScript engine.
Operations and mutations are directly applied on the JavaScript code - an intermediate language is not used.
The majority of the code is written in Python with a small amount of functions implemented in native C code.
The integration of the JavaScript engine is based on the REPRL and LibCoverage code from 
[Fuzzilli](https://github.com/googleprojectzero/fuzzilli).
Fuzzing is therefore performed in-memory with a typical execution speed of 5-15 exec/sec/core 
(coverage feedback enabled) or 20-30 exec/sec/core (coverage feedback disabled).

You can find more details in [my blog post](https://apt29a.blogspot.com/2022/01/fuzzing-chromes-javascript-engine-v8.html).

## Introduction

The mentioned execution speed can be achieved with a good input corpus.
If you start the fuzzer with a complete new input corpus, 
a lot of executions will result in new behavior and new testcases must therefore be analyzed.
Since this requires a lot of engine restarts, fuzzing will be slower at the beginning.

One goal of the project is therefore, besides uncovering new security vulnerabilities, 
to obtain a good JavaScript input corpus.
The fuzzer framework then offers different functionality which can be applied on the corpus.
For example, to inject JavaScript code into all possible locations in every testcase from the input corpus.
Or to wrap all possible code-parts within some other JavaScript code like function calls.
Hence, I would categorize this project more as a fuzzing framework than just as a fuzzer.
I never had the goal to develop a standalone fuzzer which can be used by everyone.
Instead, I wanted to create a framework which can be used (by myself) to implement or test new ideas.

The code was developed as part of my Master Thesis (see the Docs folder) and later improved during a project for the 
[Fuzzilli Research Grant Program](https://googleprojectzero.blogspot.com/2020/10/announcing-fuzzilli-research-grant.html).

The code is currently in early Alpha.

Today I'm releasing the code because it was one of the conditions to receive the research credits.
The code is in my opinion not really 100% ready to use, but since I'm a perfectionist, 
this will likely never be the case ;)

I can't guarantee that everything works as expected and if something fails, you are on your own.
You can of course try to contact me and if I have time, I'm happy to help you, but I can't guarantee this.

The code currently implements basic functionality like testcase standardization, minimization, analysis
and mutation. Nothing particularly good, nothing particularly bad (hopefully).
More complex tasks are not implemented yet, but since the foundation is now working 
(the boring tasks are done), I can begin to improve all algorithms 
(and starting working on the interesting challenges ;)). 


## Getting started

So let's say you want to test the fuzzer. This would be your first steps:


### Step 1: Install the required dependencies
Execute the script: "bash_scripts/install_requirements_gce.sh"

### Step 2: Create an initial JavaScript corpus

If you already have a corpus of JavaScript testcases, you can skip this step.
Or you could merge your corpus with a new downloaded one (which you get from this step).
To download a complete new corpus, you can use the script "create_initial_corpus/create_initial_corpus.py".
First configure the OUTPUT_DIR variable in this script and then just start it:

```
python3 create_initial_corpus.py
```
After ~10 minutes you should have something like 150 000 JavaScript testcases
(a lot of them will throw exceptions; but it's a starting point).
The testcases will still contain function calls to test suite specific functions or
native function invocations for specific JS engines (SpiderMonkey, JSC, ...).
The fuzzer will later remove these calls when importing them.


### Step 3: Compile v8

To perform this step, the instructions in "Target_v8/README.md" must be followed.
After that, ensure that the generated v8 binary path is correctly configured in
the variable "v8_path_with_coverage" in config.py. Make sure to compile a v8 binary
with coverage enabled because coverage feedback is required to create/import a corpus.


### Step 4: Compile the C-library which performs in-memory fuzzing in v8
This library is used to communicate with the v8 JavaScript engine and is based on fuzzilli's
REPRL and LibCoverage code. It's implemented in C and must therefore be compiled.

To perform this step, change into the "native_code" directory and execute the "compile.sh" script.
You can test if the communication with the JS engine works by executing the following command in the directory:
```
python3 example_usage_Executor.py
```
or
```
python3 example_usage_speed_optimized_functions.py
```


### Step 5: Prepare the system for fuzzing
Execute the "prepare_system_for_fuzzing.sh" script in the "bash_scripts" folder.


### Step 6: Let the fuzzer create an output directory & import JavaScript files into the corpus
This can be done with the following command:

```
python3 JS_FUZZER.py \
--corpus_js_files_dir /home/user/Desktop/input/new_downloaded_corpus/ \
--output_dir /home/user/Desktop/input/OUTPUT
```

The command has a runtime of several weeks (but you can stop at any time).
Currently, importing a corpus is not synchronized,
it must therefore be executed on a single CPU core.
In my case, it started pretty fast (~60 exec/sec) because it starts with the small testcases.
However, since it will find at the start a lot of testcases with new coverage, the fuzzer overhead
will be huge (263 % in my case). One reason for this is that I restart the v8 engine
before testcase analysis, minimization and standardization (which is slow).
While you wait, you can check the "current_corpus" directory in the output folder.
You should see new files being stored in the directory. The first files will be boring,
but after several minutes the fuzzer should come to the bigger files which use variables.
If everything works as expected, token renaming should work and you should just see variable
names like "var_1_" and so on (or functions like "func_1_").
If this does not work, then the coverage feedback is not reliable and variable renaming was
skipped because the coverage could not be triggered again after renaming.
This can occur with some testcases (maybe it's coverage from the syntax parser (?)).

What else can you do while you wait? Well, if the fuzzer found already some testcases with variables and
multiple operations, you can check the extracted state of the testcase. States are
stored in the "tc<ID>.js.pickle" files. Copy the path of one of the state files 
into the "filepath_state" variable in "debugging/display_state_of_testcase.py".
Then change into this directory and execute it:

```
python3 display_state_of_testcase.py
```

You should see the analysis result and the information which would
be available for the fuzzer to do something with the testcase (apply mutations, testcase merging, ...).
Note: The current analysis result is not optimal and needs a lot of improvements.

If you want to pause the import-mode, the best option would be to just stop the fuzzer and
run the whole import mode later again. The slow tasks are just performed when new coverage is found,
so the fuzzer should handle the first (already imported) files pretty quickly, which means
you should soon be at the point where you stopped.
Example: You started the script for 1 week and processed 100 000 of the 150 000 files, 
then it suddenly threw a Python exception while processing a testcase.
You can then fix the exception and start the import mode again (with the below command)
and it should now just take some hours to reach again testcase 100 000.
In fact, I would recommend to re-run the import command a second time at the end to make
sure that really all files were imported (which will be a lot faster than the first execution). 
It makes sense to first re-calculate the coverage map.
This can be done by this command:

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--recalculate_coverage_map_mode \
--resume
```

It will basically start the execution engine with an empty coverage map and re-execute all
testcases from the corpus. This can be useful because in import-mode you executed a lot of testcases
which were not imported. Some of these testcases could have triggered in-deterministic behavior
and where therefore not imported. After recalculation of the coverage map, this in-deterministic
behavior will no longer be stored in the coverage map which means you can maybe find testcases which
trigger the behavior reliably. Btw, you should recalculate the coverage map everytime you update
the target JavaScript engine because the coverage map is specific to the used engine binary.

To start the import mode again (into an already existing corpus), you can use this command:

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT/ \
--import_corpus /path/to/new/files/to/import/ \
--resume
```

I can't tell you the size of the resulting corpus because I did not execute the command yet.
I created my initial corpus using a different (standalone) script, 
but I would expect that the corpus contains at the end something like 6 000 - 10 000 testcases (with ~24% coverage).

To give you some numbers:

* After processing 15 000 files you should have ~15,0 % coverage
* After processing 35 000 files you should have ~18,2 % coverage
* After processing 69 000 files you should have ~19,4 % coverage
* After processing 91 500 files you should have ~20,0 % coverage 
* (at that point I stopped the script because I expect that it's working)

The current approach has many opportunities for improvement. For example, state creation doesn't require
coverage feedback and could therefore be done with a faster JS engine without coverage feedback enabled.
Theoretically, you can also already divide the workload on multiple systems and manually synchronize.
Just split the input folder into multiple input folders and import each folder separately.
Then, at the end, import the other results into the first output folder 
using the --import_corpus_precalculated_files_mode.

You can also try to execute the deterministic mode afterwards (--deterministic_preprocessing_mode_start_tc_id)
to further enhance your corpus. During fuzzing, you should again find several new testcases.
My corpus currently contains something like 18 000 testcases with a coverage of ~30% in v8.
Please bear in mind that it should be relatively trivial to go from 24% to 26% coverage, but it's a lot harder
to go from 28% coverage to 30% coverage.
Please also bear in mind that you can't compare the coverage from my fuzzer with the coverage from another fuzzer.
I'm not counting in-deterministic coverage, coverage from testcases which throw exceptions or other
specific modules (e.g.: WebAssembly code is completely skipped).


### Step 7: Extract data from the corpus: numbers and strings
Before you can start fuzzing, you should first extract some data from the corpus.
This can be done with the following command:

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--extract_data numbers_and_strings \
--resume
```

This command stores strings and numbers which occur in the corpus 
in a database which is used during fuzzing.


### Step 8: Start fuzzing
Now you can start the real fuzzing.
For this, the fuzzer must be started with the --resume flag.
You can configure the fuzzing in "config.py" and the frequency of mutation strategies in
"mutators/testcase_mutator.py"

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--resume
```


### Step 9: Optional: Crash Triage
Check the scripts in the "result_analysis" folder. I typically call them in numeric order
to perform crash triage. 
The 1.* scripts are used to download crashes from a GCE (Google Cloud Engine) bucket or via SSH.
The 2.* script is used to remove obvious uninteresting crashes by doing static pattern matching.
This is used to reduce the number of crash files which must be executed
(to extract runtime information for deeper analysis). This step is typically just required 
if you fuzz in the cloud for several thousand of euros and you find tens of thousands of crashes.
The 3.* script executes the crash files and extracts additional information from them for analysis.
I'm then executing the 4.* script multiple times and after each execution, I add new code
(in the function analyze_crash_information()) to generically detect the last analyzed bug.
In the next execution, the code then skips all already handled bugs and shows a new, 
currently not handled, bug. I then manually analyze this bug, add new detection code for the bug
and continue until the script doesn't show new bugs.


### Step 10: Optional: Data Extraction
At some point you should start extraction of JavaScript operations.
This can be done with this command:

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--extract_data operations \
--resume
```

This command will extract all JavaScript operations from the corpus and store them in a database.
Later fuzzing sessions will load this database and use the extracted operations to mutate testcases.
The runtime of the script is something between 1 and 3 days, depending on the size of your corpus.
The extraction of JavaScript operations is currently not optimal, so it maybe makes sense to skip
this step until I upload a better implementation.

### Step 11: Optional: Test the quality of your corpus / run the testsuite
The fuzzer has a testsuite which contains functional and quality tests.
The quality tests measure how good the JavaScript engine feedback works, how good
your input corpus is and how well the extraction of JavaScript operations worked.

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--testsuite all \
--resume
```


## Other useful commands
These are the commands I typically use to start the fuzzer:

### Resume a fuzzing session (no template files, coverage disabled)

You can use this command after having already a good corpus because coverage feedback is disabled.
I typically use it after the fuzzer doesn't find new testcases for some time.
I then manually change the mutation-strategies to include more strategies which find vulnerabilities
and then I start the fuzzer with this command:

```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--disable_coverage \
--resume
```

### Resume a fuzzing session with a specific seed
This is mainly useful to re-execute a specific fuzzing session (e.g.: for debugging).
The log file should contain the used seed value.
```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--resume \
--seed 25
```

### Kill a fuzzer session
Sometimes ctrl+c doesn't work and you have to manually kill the process.
For this I'm using the following alias:
```
alias kill_fuzzer="kill -9 \$(ps -aux | grep -v 'grep' | grep 'python3 JS_FUZZER.py' | awk '{print \$2}')"
```


### Start fuzzing with template files
The integration of template files (files which specify callback locations in JavaScript) is currently not optimal.
I would therefore not recommend using this mode.
That's also the reason why I'm not explaining how template files can be generated.
The mode will later be improved.

```
python3 JS_FUZZER.py \
--corpus_template_files_dir /home/user/Desktop/input/template_files_2021jan \
--output_dir /home/user/Desktop/input/OUTPUT \
--resume
```



### Import new JavaScript files to the current corpus:
When new JavaScript files from another fuzzer are available, they can be imported using this command.
It's also useful to regularly integrate new regression tests from JavaScript engines to the corpus.
```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT/ \
--import_corpus /path/to/new/files/to/import/ \
--resume
```


### Developer mode:
This mode is used during development. I typically add a new mutation strategy (or something else)
and then modify the code in "modes/developer_mode.py" to call the new functionality.
To test if the new code works, I'm then calling the developer mode.
```
python3 JS_FUZZER.py \
--output_dir /home/user/Desktop/input/OUTPUT \
--seed 25 \
--resume \
--developer
```

### Start measure mode:
Measure mode is basically normal fuzzing (e.g. applying multiple mutations per testcase + templates)
but it stops execution after X iterations.
X is defined by >cfg.status_update_after_x_executions< * >cfg.measure_mode_number_of_status_updates<
This mode is used to measure the execution speed 
and success rate for comparison of different enabled mutation strategies.
It's an old mode and maybe does not work at the moment.
```
python3 JS_FUZZER.py \
--corpus_template_files_dir /home/user/Desktop/input/template_files_2021jan/ \
--output_dir /home/user/Desktop/input/OUTPUT \
--seed 5 \
--verbose 0 \
--measure_mode
```


### Test mode:
Test mode performs X iterations with the first mutation strategy, then X iterations
with the next mutation strategy and so on.
It's used to compare different mutation strategies (same testcases are 
used for all mutation strategies; => this allows to compare them).
X iterations are defined via >cfg.test_mode_number_iterations<
This is useful to see which mutation strategies often lead to exceptions.
It's an old mode and maybe does not work at the moment. I'm now using 
the tagging approach instead.
```
python3 JS_FUZZER.py \
--corpus_template_files_dir /home/user/Desktop/input/template_files_2021jan \
--output_dir /home/user/Desktop/input/OUTPUT \
--seed 25 \
--test_mode
```

### Other modes
There are other modes, for example, to minimize the size of the corpus or to re-execute
the testcase minimizer on all testcases in the corpus. Or a mode to skip executions to
measure the generation speed of testcases of the fuzzer.
Check the help-message or the modes-directory yourself to learn more about these modes.


## V8 Flags to reproduce crashes:

These are the flags which the fuzzer currently internally uses to start v8.
If you can't reproduce a crash, try to add these flags:
```
--debug-code --expose-gc --single-threaded --predictable --allow-natives-syntax --interrupt-budget=1024 --fuzzing 
```


## FAQ

#### Where can I find your JavaScript corpus?
I'm sorry, I'm not sharing my corpus at the moment. But you can create your own with the fuzzer.
If you are a student or working for a university, you can contact me and we maybe work something out.


#### How can I use the fuzzer for other JS engines (SpiderMonkey, JSC, ...)
At the moment the fuzzer only supports v8 and everything was implemented for v8.
You can see this by looking at testcases in the corpus which can contain v8 native function calls.
The best option would be to rewrite a generated testcase before actually executing it 
(to remove the v8 native functions calls).
This way, the same corpus can be used for different engines 
(but you should remove testcases which throw an exception/crash in the new engine)
The engine integration should be trivial because I built my fuzzer on top of the REPRL implementation from fuzzilli.
Fuzzilli ships patch files to support other engines. The integration should therefore work out of the box,
but I didn't test this yet.


#### Why a new fuzzer? Why didn't you adapt fuzzilli?
I think [fuzzilli](https://github.com/googleprojectzero/fuzzilli) is a great fuzzer, but I wanted to develop my own fuzzer.
Fuzzilli is well-designed and is likely better in a lot of areas.
However, I think friendly competition is good and can hopefully also help to improve fuzzilli in the future.
But first, my fuzzer has to prove that it can keep up with fuzzilli.


#### Your fuzzer does not work
Can happen. I'm sharing here **my** fuzzing framework which **I** use to fuzz v8.
My goal was not to develop a fuzzer for others, I'm just sharing my code in case it helps others.
If you don't want to touch code and still want to fuzz JavaScript engines, you should take a look at fuzzilli.
With my fuzzer, it can happen that some specific modes, which I don't regularly use, don't work.
For example, the code to create an initial corpus is not well tested because I'm not using this functionality anymore.
I'm just working on my current corpus to improve it.


#### What is the best mutation configuration?
Good question. I think this is an open research problem.
I typically try to achieve 50-70% success rate and just 2-5% timeout rate.
Everything else is just a rough guess from my side (and can be completely wrong).
Side node: The uploaded configuration has just a success rate of 45-50%. 
I wanted to upload the configuration which I used in the fuzzing session described in 
my blog post (so that results are reproducible). It maybe makes sense to perform fewer
mutations to obtain a better success rate of ~70%.


#### Any other hints before I start fuzzing?
My recommendation would be to first start the fuzzer for some hours on the target system 
without the watchdog script. The watchdog script restarts the fuzzer in case a problem (e.g.: python exception)
occurs. You don't want to start hundreds of fuzzer instances and then all instances constantly restart the
fuzzer because an exception occurs after 10 minutes. The fuzzer should run fine for at least 8-10 hours without
an exception. Just for comparison: 
In my fuzzing sessions just 3 exceptions occurred in 13,6 CPU years of fuzzing.


#### How many bugs have you found with the fuzzer?
In total, I found 18 unique bugs in v8. 7 of these bugs were security vulnerabilities.
4 of these 7 security vulnerabilities were already known and duplicates.
From the 3 remaining vulnerabilities, 2 were similar.
You can find more details in [my blog post](https://apt29a.blogspot.com/2022/01/fuzzing-chromes-javascript-engine-v8.html).
Btw, if you find a new vulnerability with the fuzzer, it would be nice if you drop me a short message.
Especially, if you plan to sell and get rich with it ;)


#### Can I push code to the fuzzer? Can I help with development?
I'm not planning this at the moment. Regular updates are not scheduled, 
but I'm maybe going to push newer versions all 4-8 months.
If you push new code, you likely push to an old code base.
If you really want to help with development (e.g.: for a university project),
you should first contact me. There are lots of interesting open challenges.


#### What are your future plans for the fuzzer?
First, continue refactoring the code (more compliance to PEP8, reduce module dependencies, 
better exception handling, better execution flow, ...), then improve different submodules (e.g.: better testcase minimization).
Minimization and standardization are important because I can't execute these steps later again because I maybe 
don't have the JS engine binary anymore which detected the unique behavior for a testcase.
Minimization is important for a lot of other modules (e.g.: JS operations extraction) and should
therefore really work well.
The testcase state creation code must be rewritten and I plan to store the state in a different form to 
improve the performance of the fuzzer. After that, I can start to implement more mutation strategies
and fine-tune the configurations. The currently implemented mutation strategies were just a simple PoC
and are far from complete.  In my opinion, the majority of the code of the fuzzer
currently ensures that the input data source is good. But the fuzzer lacks code which combines the data in
meaningful ways to trigger vulnerabilities.
Code to detect and extract JavaScript operations must also be heavily improved (maybe with a 3rd party library).
I also plan to implement a JavaScript grammar. This is an important step because currently the fuzzer
just fuzzes with data from the corpus or data extracted from the JS engine (e.g.: the fuzzer doesn't know
the data type of arguments from builtin functions; it doesn't have defines which specify the JavaScript language).
Another open point is the implementation of different generators (e.g.: to apply mutations on
regression tests or a better selection of testcases for the next iteration).
The generation of template files must be improved by adding a check to detect 
callback duplicates to reduce the size of the template corpus (and also other callback techniques must be added).
Further research areas would be to fine-tune the coverage feedback from the JS engine (e.g.: skip the syntax parser
or get better feedback from the JIT engine; or a totally different feedback; I also plan to extract additional
data per corpus entry, for example, via a taint engine).
And one of the most important challenges is to find a solution to reduce the search space of the fuzzer
(the current search space is huge and not optimized in any way yet).
Finally, I also plan to fuzz other JavaScript engines (SpiderMonkey & JSC).
But for this, I need computation resources, which I currently don't have.



### How can I fuzz in the cloud?
Let's say you tested the fuzzer and you actually want to start the fuzzer on multiple systems.
Currently, the fuzzer just supports GCE (Google Cloud Platform) because synchronization is implemented
via GCE buckets (but it's trivial to implement another synchronization mechanism). 
In this case, you can check the scripts in the "automation_gce" folder.
Basically, you first create a GCE instance and install the fuzzer and copy your corpus to the system.
After that, you create a GCE bucket (open config.py and search for "bucket_" and read the instructions there).
Then you test if the bucket works together with the fuzzer running on the GCE instance.
Next, you create output folders for every fuzzer session which should run on an instance 
(e.g.: a 6 core GCE instance should have 6 output/working folders for 6 running fuzzer sessions).
Then you should update the "automation_gce/start_fuzzing_16.sh" script with the correct paths and number
of CPUs. Also configure the "watchdog.sh" script with the correct fuzzer path on the GCE system
and the correct fuzzer invocation command you want to use.
Next, I would fill out and test the "automation_gce/start_gce_instances.sh" script to 
start one fuzzer instance. For this, you must first create a snapshot of the GCE instance.
Make sure that the fuzzer was running for 8-10 hours before the GCE snapshot was created.
The fuzzer disables testcases which often throw exceptions or hang. These testcases should already be
disabled before fuzzing is started on multiple systems.
Check if fuzzing automatically starts when the GCE instance gets started and if results are regularly 
written to the GCE bucket. Let the instance run at least for one day and check if everything runs smoothly.
If this works, nothing should stop you from going big ;)
Some final tips: Don't forget to increase your CPU quota (and maybe IP-Addresses quota).
Ensure that your GCE instance hard disk is big enough - not only with pure disk space, but also with the number
of available file system inodes.


#### Which IDE are you using?
I started with notepad and later switched to PyCharm.
I know that I'm not following the max-79-chars per line recommendation, but I
also have a big monitor ;)


#### Why develop a fuzzer? Isn't manual source code analysis more promising?
I guess you can identify new bugs in JS engines faster by doing manual source code analysis, 
but I think automation via fuzzing is an interesting technical challenge.


#### Your code is shit
I know, that's why I'm working as penetration tester and not as developer :)
Bear in mind that most of the code was written late at night in my spare time.
I also know that some code areas are not really implemented well (I hope you never find them...), 
but rewriting the code would require a re-calculation of the corpus which requires 
several weeks of computation power.
I also wanted to publish the code similar to the version which I used during the project,
so that results are reproducible (the code was just refactored - functionality was not changed).
But yes, a lot of modules require heavy improvements.


#### How can I contact you?
The best option is to drop [me](https://twitter.com/ReneFreingruber) a DM on Twitter.
If I don't answer, I likely didn't see the message and you should send me a tweet.
