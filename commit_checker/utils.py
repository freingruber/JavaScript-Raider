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


import sys
import re

words_to_number_occurrences = dict()
security_related_words = set()
skip_words = set()


class bcolors:
    # source: https://godoc.org/github.com/whitedevops/colors#pkg-constants
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'    
    RED = "\033[31m"
    MAGENTA = "\033[35m"


def perror(msg_to_print):
    print(bcolors.RED + bcolors.BOLD + msg_to_print + bcolors.ENDC)
    sys.exit(-1)
    

def msg(msg_to_print):
    if msg_to_print.startswith("[+]"):
        print(bcolors.GREEN + msg_to_print + bcolors.ENDC)
    elif msg_to_print.startswith("[-]"):
        print(bcolors.RED + msg_to_print + bcolors.ENDC)
    elif msg_to_print.startswith("[i]"):
        print(bcolors.MAGENTA + msg_to_print + bcolors.ENDC)
    else:
        print(bcolors.ENDC + msg_to_print + bcolors.ENDC)


def contains_security_related_words(arg_msg):
    global words_to_number_occurrences, security_related_words

    msg_lower = arg_msg.lower()
    count = 0
    for word in security_related_words:
        if word in msg_lower:
            if word not in words_to_number_occurrences:
                words_to_number_occurrences[word] = 0
            words_to_number_occurrences[word] += 1
            count += 1
    return count



def should_ignore_change(change_data):
    global skip_words
    subject = change_data.subject
    subject_lower = subject.lower()
    for word in skip_words:
        if word in subject_lower:
            return True

    if "wasm" in change_data.hashtags:
        return True

    if re.match(r"^version [\d\.]+$", subject_lower):   # something like: version 9.5.50
        return True

    return False


def print_commit_message(arg_msg):
    for line in arg_msg.split("\n"):
        if line.startswith("Bug:"):
            continue
        if line.startswith("Change-Id:"):
            continue
        if line.startswith("Reviewed-on:"):
            continue
        if line.startswith("Commit-Queue:"):
            continue
        if line.startswith("Cr-Commit-Position:"):
            continue
        if line.startswith("Reviewed-by:"):
            continue
        if line.startswith("Cr-Branched-From:"):
            continue
        if line.startswith("BUG="):
            continue
        if line.startswith(">"):
            continue
        if line.startswith(">"):
            continue
        print(line.encode("utf-8"))


def show_owner_summary(count_owners):
    count_owners_list = []
    for owner in count_owners:
        count_owners_list.append((owner, count_owners[owner]))
    count_owners_list.sort(key=lambda x: x[1])
    print("Owners:")
    for entry in count_owners_list:
        print("%s => %d changes!" % entry)



def show_word_statistic():
    global words_to_number_occurrences
    count_word_list = []
    for word in words_to_number_occurrences:
        count_word_list.append((word, words_to_number_occurrences[word]))
    count_word_list.sort(key=lambda x: x[1])
    print("Words and occurrences:")
    for entry in count_word_list:
        print("%s occurs %d times!" % entry)



def show_database_statistics(all_referenced_chromium_bugs, all_security_bugs_from_rewards, number_changes_with_restricted_bug_report):
    count_chromium_bugs_security = 0
    for chromium_bug in all_referenced_chromium_bugs:
        if chromium_bug in all_security_bugs_from_rewards:
            count_chromium_bugs_security += 1


    print("chromium bugs: %d" % len(all_referenced_chromium_bugs))
    print("number_changes_with_restricted_bug_report: %d" % number_changes_with_restricted_bug_report)
    print("count_chromium_bugs_security: %d" % count_chromium_bugs_security)


def initialize():
    global security_related_words, skip_words

    # Some words which often occur in commit messages of security fixes
    security_related_words.add("didn't correct".lower())
    security_related_words.add("correctly".lower())
    security_related_words.add("caused".lower())
    security_related_words.add("causes".lower())
    security_related_words.add("problem".lower())
    security_related_words.add("expect".lower())
    security_related_words.add("necessary".lower())
    security_related_words.add("correctness".lower())
    security_related_words.add("avoid".lower())
    security_related_words.add("crash".lower())
    security_related_words.add("fast path".lower())
    security_related_words.add("invalid".lower())
    security_related_words.add("not safe".lower())
    security_related_words.add("Harden".lower())
    security_related_words.add("assumption".lower())
    security_related_words.add("Do not assume".lower())
    security_related_words.add("Don't assume".lower())
    security_related_words.add("Ensure".lower())
    security_related_words.add("fits in".lower())
    security_related_words.add("fits the".lower())
    security_related_words.add("into a SMI".lower())
    security_related_words.add("It is possible".lower())
    security_related_words.add("side effect".lower())
    security_related_words.add("annotation".lower())
    security_related_words.add("must happen".lower())
    security_related_words.add("Fix ".lower())      # with space at the end
    security_related_words.add("Fix\n".lower())
    security_related_words.add("Check array".lower())
    security_related_words.add("array length".lower())
    security_related_words.add("element length".lower())
    security_related_words.add("wrong typing".lower())
    security_related_words.add("corrupt".lower())
    security_related_words.add("wrong assignments".lower())
    security_related_words.add("wrong ElementsKind ".lower())
    security_related_words.add("we should avoid".lower())
    security_related_words.add("refactor".lower())
    security_related_words.add("avoid".lower())
    security_related_words.add("maps unstable".lower())
    security_related_words.add("maps ".lower())
    security_related_words.add("map".lower())
    security_related_words.add("-0".lower())
    security_related_words.add("+0".lower())
    security_related_words.add("truncated".lower())
    security_related_words.add("truncation".lower())
    security_related_words.add("TypeCheck".lower())
    security_related_words.add("restrict".lower())
    security_related_words.add("elements kinds".lower())
    security_related_words.add("could be too".lower())
    security_related_words.add("must thus".lower())
    security_related_words.add("write barrier".lower())
    security_related_words.add("barrier".lower())
    security_related_words.add("Use correct".lower())
    security_related_words.add("access check".lower())
    security_related_words.add("require".lower())
    security_related_words.add("Check for prototype".lower())
    security_related_words.add("missing".lower())
    security_related_words.add("GetDerivedMap".lower())
    security_related_words.add("can invoke".lower())
    security_related_words.add("Stricter asserts".lower())
    security_related_words.add("checked".lower())
    security_related_words.add("reasoning".lower())
    security_related_words.add("Relax".lower())
    security_related_words.add("simplified lowering".lower())
    security_related_words.add("need to".lower())
    security_related_words.add("requires more".lower())
    security_related_words.add("sensitivity".lower())
    security_related_words.add("doesn't recognize".lower())
    security_related_words.add("crash".lower())
    security_related_words.add("Check bounds".lower())
    security_related_words.add("didn't expect".lower())
    security_related_words.add("might".lower())
    security_related_words.add("fix type widening bug".lower())
    security_related_words.add("SEGV".lower())
    security_related_words.add("raw pointer".lower())
    security_related_words.add("Typer::".lower())
    security_related_words.add("does not take into account".lower())
    security_related_words.add("incorrectly assumed".lower())
    security_related_words.add("assumed".lower())
    security_related_words.add("typing bugs".lower())
    security_related_words.add("Validate computed".lower())
    security_related_words.add("potential typer bugs".lower())
    security_related_words.add("has space for".lower())
    security_related_words.add("guard against".lower())
    security_related_words.add("fix type widening bug".lower())
    security_related_words.add("typing bug".lower())
    security_related_words.add("typer bug".lower())
    security_related_words.add("truncation bug".lower())
    security_related_words.add("fix bug".lower())
    security_related_words.add("materialization".lower())
    security_related_words.add("materializing".lower())
    security_related_words.add("confused".lower())
    security_related_words.add("overflow".lower())
    security_related_words.add("unsound".lower())
    security_related_words.add("in-place transition".lower())
    security_related_words.add("Add missing".lower())
    security_related_words.add("uninitialized".lower())
    security_related_words.add("accidentally".lower())
    security_related_words.add("Stricter checks".lower())
    security_related_words.add("invalid offset".lower())
    security_related_words.add("is too large".lower())
    security_related_words.add("backing store".lower())
    security_related_words.add("dangling".lower())
    security_related_words.add("We have to respect".lower())
    security_related_words.add("Defence in depth".lower())
    security_related_words.add("exploitation".lower())
    security_related_words.add("exploit".lower())
    security_related_words.add("abuses".lower())
    security_related_words.add("off-by-one".lower())
    security_related_words.add("off by one".lower())
    security_related_words.add("truncation bug".lower())
    security_related_words.add("confusion".lower())
    security_related_words.add("We must ensure".lower())
    security_related_words.add("free list".lower())
    security_related_words.add("GC issue".lower())
    security_related_words.add("OOB".lower())
    security_related_words.add("escape".lower())
    security_related_words.add("don't elide".lower())
    security_related_words.add("do not use".lower())
    security_related_words.add("don't use".lower())
    security_related_words.add("manipulation".lower())
    security_related_words.add("regression".lower())

    # skip_words.add("performance improvements".lower())  # text can be something like "fixed vuln1 and added performance improvements" => don't skip
    skip_words.add("PPC ".lower())
    skip_words.add("PPC]".lower())
    skip_words.add("PPC\\".lower())
    skip_words.add("s390 ".lower())
    skip_words.add("s390]".lower())
    skip_words.add("s390\\".lower())
    skip_words.add("[wasm]".lower())
    skip_words.add("[wasm-gc]".lower())
    skip_words.add("[infra]".lower())
    skip_words.add("[mips]".lower())
    skip_words.add("[riscv64]".lower())
    skip_words.add("Update V8 DEPs".lower())
