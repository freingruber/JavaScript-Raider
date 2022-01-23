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



# This script will be executed via "profile_performance_of_fuzzer.sh"
# The bash script will create a profile.stats file when executed via cProfiler
# This script then parses the profile.stats file and displays the results (filtered and sorted)

import pstats
import io
import sys

# "tottime" is the time spend inside the function EXCLUDING sub calls (e.g. used to find long loops)
# "cumtime" is the time spend inside the function INCLUDING sub calls (e.g. used to find functions which call slow builtin functions)


console_width = 160
number_of_entries_to_show = 15


def parse_profile_stats(filename):
    s = io.StringIO()
    p = pstats.Stats(filename, stream=s)
    p.strip_dirs()
    p.sort_stats("tottime")    # 'tottime', 'cumulative'

    p.print_stats()
    output = s.getvalue()

    total_runtime = 0
    all_entries_stats = []
    should_parse = False
    for line in output.split("\n"):
        line = line.rstrip()
        if line == "":
            continue
        if "function calls" in line and "primitive calls)" in line:
            line = line.strip()
            total_runtime = float(line.split(" ")[7])
            continue
        if "built-in method builtins.exec" in line:
            continue
        if "JS_FUZZER.py" in line and "(<module>)" in line:
            continue
        if "JS_FUZZER.py" in line and "(main)" in line:
            continue
        if "ncalls" in line and "tottime" in line:
            should_parse = True
            continue
        if should_parse:
            # print(line)
            parts = line.split(None, 5)
            tottime = float(parts[1])
            cumtime = float(parts[3])
            filename = parts[5]
            # print("{0:>8} Sec\t{1:>8} Sec\t\t{2}".format(tottime, cumtime,filename))
            if "(" in filename:
                parts2 = filename.split("(", 1)
                filename = parts2[0]
                methodname = parts2[1].rstrip(")")
            else:
                methodname = ""
            all_entries_stats.append((tottime, cumtime, filename, methodname))

    s.truncate(0)
    s.seek(0)
    # p.sort_stats("tottime")
    p.print_callers()
    output = s.getvalue()

    # print(output)
    # sys.exit(-1)
    all_entries_callers = []
    should_parse = False
    start_ncalls = 0
    for line in output.split("\n"):
        line = line.rstrip()
        if line == "":
            continue
        if "ncalls" in line and "tottime" in line and "cumtim" in line:
            should_parse = True
            start_ncalls = line.find("ncalls")
            continue
        if should_parse:
            # print(line)
            try:
                split_offset = start_ncalls
                while line[split_offset] != " ":
                    split_offset -= 1
            except:
                continue

            called_function = line[:split_offset].strip().strip("<-").strip()
            right_part = line[split_offset:]
            parts = right_part.split(None, 3)
            if len(parts) != 4:
                continue
            total_time = float(parts[1])
            cumulative_time = float(parts[2])
            calling_function = parts[3].strip()
            
            all_entries_callers.append((total_time, cumulative_time, calling_function, called_function, line))


    return total_runtime, all_entries_stats, all_entries_callers


def print_first_stats_entries(label, data, number_of_entries=10):
    global console_width
    print("")
    print("="*console_width)
    print("%s" % label)
    print("-"*console_width)
    counter = 0
    for entry in data:
        (tottime, cumtime, filename, methodname) = entry
        print("{0:>8.3f} Sec\t{1:>8.3f} Sec\t\t{2:<45}\t\t{3}".format(tottime, cumtime, methodname, filename))
        counter += 1
        if counter >= number_of_entries:
            break
    print("-"*console_width)
    print("")


def print_first_callers_entries(label, data, number_of_entries=10):
    global console_width
    print("")
    print("="*console_width)
    print("%s" % label)
    print("-"*console_width)
    counter = 0
    for entry in data:
        (total_time, cumulative_time, calling_function, called_function, line) = entry
        print("{0:>8.3f} Sec\t{1:>8.3f} Sec\t\t{2:<65}\t<-\t{3}".format(total_time, cumulative_time, called_function, calling_function))
        counter += 1
        if counter >= number_of_entries:
            break
    print("-"*console_width)
    print("")


def main():
    (total_runtime, stats, callers) = parse_profile_stats("profile.stats")

    print("\n")
    print("=" * console_width)
    print("Total runtime: %.0f Seconds" % total_runtime)
    print("-" * console_width)

    stats.sort(key=lambda x: x[0], reverse=True)  # Sort by TOTTIME
    print_first_stats_entries("STATS sorted by TOTAL TIME:", stats, number_of_entries_to_show)

    stats.sort(key=lambda x: x[1], reverse=True)  # Sort by CUMTIME
    print_first_stats_entries("STATS sorted by CUMULATIVE TIME:", stats, number_of_entries_to_show)

    callers.sort(key=lambda x: x[0], reverse=True)  # Sort by TOTTIME
    print_first_callers_entries("CALLERS sorted by TOTAL TIME:", callers, number_of_entries_to_show)

    callers.sort(key=lambda x: x[1], reverse=True)  # Sort by CUMTIME
    print_first_callers_entries("CALLERS sorted by CUMULATIVE TIME:", callers, number_of_entries_to_show)

    # p.print_stats(10) # only print 10 functions
    # p.dump_stats('/path/to/stats_file.dat')

    # p.print_callers()
    # p.print_callees()   # which functions call other functions

    # with open('path/to/output', 'w') as stream:
    #    stats = pstats.Stats('path/to/input', stream=stream)
    #    stats.print_stats()


if __name__ == "__main__":
    main()
