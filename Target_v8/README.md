# How to compile v8 for the fuzzer

## 1. Download Depot-Tools from v8

To compile v8, it's required to first install the Chromium compilation tools (depot tools).
To install them, execute the following commands:

```
sudo apt install git
cd /opt/
sudo git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git
sudo chown -R $(whoami):$(whoami) /opt/depot_tools/
```

The following command can be used to make the depot tools available in your path (e.g.: add the export-command to your ~/.bashrc file)
```
export PATH=$PATH:/opt/depot_tools/
```

## 2. Download the current v8 version via depot tools
I would recommend downloading v8 outside the fuzzer folder (otherwise an IDE can get confused by the additional files).
Execution of the below commands can take a while (it doesn't show output in the first minutes).
```
cd /some/path/where/you/want/to/store/v8
fetch --nohooks v8
cd v8
```


## 3. Optional: Change to a specific commit / tag of v8
If you want to change to a specific v8 commit, use the following command:
```
git checkout fd856cebb3515699d942d0f2517f6658a0cf720b
```

Version used during development:\
Google Chrome: 81.0.4044.92\
v8 version: 8.1.307.28\
v8 git commit: d3a6f4bb6d01e91c7929feec3cf91eb62f3c2d3a\
\
A older v8 which is prone to some public PoCs (which can be used to test if the debugger detects crashes)\
v8 git commit: 26dad80ff512b256c2cde7c97175d36e55adc0c0\
\
2nd version used during development:\
Google Chrome: 87.0.4280.88\
v8 version: 8.7.220.29\
v8 git commit: 45d51f3f97a6058fced26b9c378fba5dcd924704\
\
Version I later used during fuzzing:\
Google Chrome: 91.0.4472.77\
v8 version: 9.1.269.28\
v8 git commit: fd856cebb3515699d942d0f2517f6658a0cf720b\
\
Command to see the current v8 commit hash:
```
git rev-parse --verify HEAD
```


## 4. Optional: Apply a patch
Applying a patch should not be required anymore.
At the start, the required modifications in v8 were not committed
and a patch had therefore be applied. This is no longer required.
However, if you want to modify v8 to enhance fuzzing, then you 
should create a patch file and always apply it after updating v8.

Apply the patch:
```
// patch < v8_patch_file.patch
git apply --stat v8_patch_file.patch
```

To create the patch file:
```
git diff > my_new_patch.patch
```


## 5. Sync everything and install dependencies for the specified v8 commit
Everytime you update the code or change to another commit, you should re-execute the following commands.
```
gclient sync --with_branch_heads
sudo ./build/install-build-deps.sh --unsupported --no-prompt
```


## 6. Compile v8
You should compile v8 at least 3 times and configure the resulting paths in config.py.
* v8 without coverage feedback enabled (config.py variable v8_path_without_coverage)
* v8 with coverage feedback enabled (config.py variable v8_path_with_coverage)
* v8 in a debug build (config.py variable v8_path_debug_without_coverage)

The debug-build is not strictly required, it will later be used for automated crash triage (not implemented yet).
The "coverage enabled"/"coverage not enabled" versions are also not strictly required.
If you just want to fuzz without coverage, then you must not create the coverage-enabled binary.

You don't need to keep all output files (the result folder has a size of several GB).
I always just keep the following files:
* d8
* icudtl.dat
* icudtl_extra.dat
* snapshot_blob.bin
* v8_shell

## Compile with coverage enabled
```
gn gen out/fuzzbuild --args='is_debug=false dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_fuzzilli=true v8_enable_verify_predictable=true sanitizer_coverage_flags="trace-pc-guard" target_cpu="x64"'
ninja -C ./out/fuzzbuild
```


## Compile with coverage enabled & builtin instrumentation enabled ("full instrumentation", but very slow; not recommended)
```
gn gen out/fuzzbuild --args='is_debug=false dcheck_always_on=true v8_enable_builtins_profiling=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_fuzzilli=true v8_enable_verify_predictable=true sanitizer_coverage_flags="trace-pc-guard" target_cpu="x64"'
ninja -C ./out/fuzzbuild
```


## Compile without coverage enabled
Hint:\
Compiling with the below flags will result in 5 errors because some return values are not used by the fuzzilli code\
=> just add code like "int ret = .." and then access the returned variable (e.g. if(ret) {} or use something like UNUSED(ret))\
Moreover, the final d8 binary will crash when you start it because coverage is not enabled\
You can either start the binary with the following flag to avoid the crash:\
--no-fuzzilli-enable-builtins-coverage\
Or you can open src/d8/d8.cc and search for "fuzzilli_enable_builtins_coverage and remove all 3 if-blocks which would be executed if coverage would be enabled.

But if you just get started with the fuzzer, you likely don't need a v8 binary without coverage enabled (so just skip this).
```
gn gen out/fuzzbuild --args='is_debug=false dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_fuzzilli=true v8_enable_verify_predictable=true target_cpu="x64"'
ninja -C ./out/fuzzbuild
```


## Compile a debug binary without coverage feedback (but with fuzzilli REPRL mode enabled)
The fuzzilli REPRL mode must be enabled so that the fuzzer "can speak" with v8.
```
gn gen out/fuzzbuild --args='is_debug=true dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_fuzzilli=true v8_enable_verify_predictable=true target_cpu="x64"'
ninja -C ./out/fuzzbuild
```


## Compile a debug binary without coverage feedback (and with fuzzilli REPRL mode disabled)
Since fuzzilli is not enabled in this build, you can't run this d8 binary together with the fuzzer.
But you can use it for manual crash triage.
```
gn gen out/fuzzbuild --args='is_debug=true dcheck_always_on=true v8_static_library=true v8_enable_slow_dchecks=true v8_enable_v8_checks=true v8_enable_verify_heap=true v8_enable_verify_csa=true v8_enable_verify_predictable=true target_cpu="x64"'
ninja -C ./out/fuzzbuild
```
or
```
tools/dev/gm.py x64.debug
```


## Compile a release binary (e.g.: for exploit development)
```
tools/dev/gm.py x64.release
```
