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


# The content of this script must be saved in the "startup-script" meta information
# of a GCE machine (alternatively the >start_gce_instances.sh< script will pass it.
# => Then this script automatically starts fuzzing when a GCE machine is spawned

# The script currently starts 16 fuzzing jobs.
# If you want to use less/more cores, you must adapt this script
# Note: This also requires OUTPUT folders for every running fuzzer, e.g. 6 cores => 6 OUTPUT directories
# You must create these OUTPUT folders in the base-image of the fuzzer.

# TODO: Rewrite the script to use a loop...

tmux new-session -d -s "fuzzing";

tmux setw -g mouse on
tmux bind h split-window -h
tmux bind v split-window -v

tmux rename-window -t 0 "Fuzzer1"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./prepare_system_for_fuzzing.sh" C-m
sleep 1	# Give a second to make sure the preparation finished
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 1 "Fuzzer2"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT2" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 2 "Fuzzer3"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT3" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 3 "Fuzzer4"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT4" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 4 "Fuzzer5"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT5" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 5 "Fuzzer6"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT6" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 6 "Fuzzer7"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT7" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 7 "Fuzzer8"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT8" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 8 "Fuzzer9"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT9" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 9 "Fuzzer10"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT10" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 10 "Fuzzer11"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT11" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 11 "Fuzzer12"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT12" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 12 "Fuzzer13"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT13" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 13 "Fuzzer14"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT14" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 14 "Fuzzer15"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT15" C-m

sleep 1
tmux new-window -t "fuzzing"
tmux rename-window -t 15 "Fuzzer16"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/; ./watchdog.sh OUTPUT16" C-m

tmux new-window -t "fuzzing"
tmux rename-window -t 4 "Results1"
tmux send-keys -t "fuzzing" "cd /home/gce_user/fuzzer/OUTPUT/current_corpus; pwd" C-m


# Go back to the first fuzzer instance
tmux select-window -t 0
