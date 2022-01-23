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


# This script is not well tested. I collected all the commands from different sources / fuzzers
# It's likely possible to further increase fuzzer performance by changing these configurations to better settings

sysctl -w kernel.core_pattern=core
sysctl -w kernel.randomize_va_space=0
sysctl -w kernel.sched_child_runs_first=1
sysctl -w kernel.sched_autogroup_enabled=1
sysctl -w kernel.sched_migration_cost_ns=50000000
sysctl -w kernel.sched_latency_ns=250000000
echo never > /sys/kernel/mm/transparent_hugepage/enabled
test -e /sys/devices/system/cpu/cpufreq/scaling_governor && echo performance | tee /sys/devices/system/cpu/cpufreq/scaling_governor
test -e /sys/devices/system/cpu/cpufreq/policy0/scaling_governor && echo performance | tee /sys/devices/system/cpu/cpufreq/policy*/scaling_governor
test -e /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor && echo performance | tee /sys/devices/system/cpu/cpu*/cpufreq/scaling_governor
test -e /sys/devices/system/cpu/intel_pstate/no_turbo && echo 0 > /sys/devices/system/cpu/intel_pstate/no_turbo
test -e /sys/devices/system/cpu/cpufreq/boost && echo 1 > /sys/devices/system/cpu/cpufreq/boost

 
echo "Manually disable spectre:"
echo "vim /etc/default/grub"
echo "Change first line to:"
echo "GRUB_CMDLINE_LINUX_DEFAULT=\"noibrs noibpb nopti nospectre_v2 nospectre_v1 l1tf=off nospec_store_bypass_disable no_stf_barrier mds=off mitigations=off\""
echo ""
echo "cp /etc/default/grub /etc/default/grub.conf"
echo "grub2-mkconfig -o /bin/grub2.cfg"

echo ""
echo "Check if spectre is disabled:"
cat /proc/cmdline
fgrep -r '' /sys/devices/system/cpu/vulnerabilities