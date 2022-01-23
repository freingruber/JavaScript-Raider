#!/bin/bash

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



# This script is used to find performance bottlenecks in the fuzzer
# It can be started with cProfiler and Line_Profile (just change the variable below)
# It's recommended to first run cProfiler to get an overview which functions are slow
# Then you should annotate ("@profile") functions which are slow and restart
# this script with Line_Profiler to understand which code lines of a function are slow.
# The cProfiler output is passed to a Python script to better visualize the results

# Note: You must adapt the paths in the below fuzzer Commands (output and template corpus)
# It's recommended to perform at least 50 000 executions to get a good overview
# Since the Line_profiler is a lot slower, I would just do 1000 executions

# Valid entries are for now "cprofiler" and "line_profiler" 
profiler="cprofiler"

if [ "$profiler" = "cprofiler" ] ; then
    echo "Starting cprofiler"

    rm profile.stats

    # The following command will create "profile.stats" (runtime: several minutes)
    # --skip_executions \
    python3 -m cProfile \
        -s cumulative \
        -o profile.stats \
        JS_FUZZER.py \
        --output_dir /home/user/Desktop/input/OUTPUT/ \
        --resume \
        --seed 5 \
        --disable_coverage \
        --max_executions 50000

    # The following command will analyse the "profile.stats" output file
    python3 profile_analyse_output_stats.py
elif [ "$profiler" = "line_profiler" ] ; then
    echo "Starting line_profiler"

    rm JS_FUZZER.py.lprof
    # The following command will create "JS_FUZZER.py.lprof"
    # Requires that a function gets annotated with "@profile"

    # Note: Line Profiler is very slow (e.g. instead of 200 exec/sec it drops to 5 exec/sec)
    # I'm therefore not making too many executions
    kernprof -l JS_FUZZER.py \
        --output_dir /home/user/Desktop/input/OUTPUT/ \
        --resume \
        --seed 5 \
        --skip_executions \
        --max_executions 1000

    python3 -m line_profiler JS_FUZZER.py.lprof
else
    echo "Unkown profiler selected"
fi
