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


# This script contains the class definition for a Change.
# Changes are pushed to https://chromium-review.googlesource.com for review.
# It's basically a commit together with messages to discuss a fix or modification.

import utils
import re


class Change:

    def __init__(self):
        self.number = 0
        self.created = ""
        self.updated = ""
        self.hashtags = []
        self.subject = ""
        self.status = ""
        self.owner = ""
        self.current_revision = ""
        self.reviewers = []
        self.commit_message = ""
        self.revisions = []
        self.messages = []
        self.files = []

        self.print_verbose = False

    def __str__(self):
        tmp = ""
        tmp += "Change: %d ( " % self.number + utils.bcolors.UNDERLINE + self.get_crbug_url() + utils.bcolors.ENDC + " ) \n"
        

        tmp += "Subject:\n\t" + utils.bcolors.RED + self.subject + utils.bcolors.ENDC + "\n"
        tmp += "Owner:\n\t" + utils.bcolors.RED + self.owner + utils.bcolors.ENDC + "\n"
        tmp += "Created:\n\t" + utils.bcolors.RED + self.created + utils.bcolors.ENDC + "\n"
        tmp += "Commit message:\n" + self.get_colorized_commit_message()
        tmp += "Files:\n"
        for entry in self.files:
            (filename, lines_inserted, lines_deleted, size, size_delta) = entry
            tmp += utils.bcolors.GREEN + "\t%s\n" % filename + utils.bcolors.ENDC

        tmp += "Reviewer: %s\n" % ', '.join(self.reviewers)
        tmp += "Status: %s\n" % self.status
        tmp += "Updated: %s\n" % self.updated
        tmp += "Hashtags: %s\n" % ', '.join(self.hashtags)
        tmp += "Current revision: %s\n" % self.current_revision

        if self.print_verbose:
            tmp += "\nRevisions:\n"
            for entry in self.revisions:
                (msg, author, committer, subject, description) = entry
                tmp += "\tSubject: %s\n" % subject
                tmp += "\tAuthor: %s\n" % author
                tmp += "\tCommitter: %s\n" % committer
                tmp += "\tMessage: %s\n" % msg
                tmp += "\tDescription: %s\n\n" % description

            tmp += "\nMessages:\n"      # Comments?
            for entry in self.messages:
                (author, real_author, message) = entry
                tmp += "\tAuthor: %s\n" % author
                tmp += "\tReal author: %s\n" % real_author
                tmp += "\tMessage: %s\n\n" % message
            
        return tmp

    def get_crbug_url(self):
        return "https://chromium-review.googlesource.com/c/v8/v8/+/%d" % self.number

    def get_colorized_commit_message(self):
        line_prefixes_to_ignore = ["No-Try:",
                                   "No-Presubmit:",
                                   "No-Tree-Checks:",
                                   "Change-Id:",
                                   "Reviewed-on:",
                                   "Bot-Commit:",
                                   "Cr-Commit-Position:",
                                   "Cr-Branched-From:",
                                   "Change-Id:",
                                   "Reviewed-on:",
                                   "Bug: chromium:",
                                   "Bug: v8:",
                                   "Commit-Queue:",
                                   "Reviewed-by",
                                   "Cr-Commit-Position:",
                                   "(cherry picked from commit",
                                   "Auto-Submit:",
                                   "Owners-Override:",
                                   "Cq-Include-Trybots:",
                                   "Cr-Original-Commit-Position:",
                                   "Cr-Original-Branched-From:"]


        tmp = ""
        for line in self.commit_message.split("\n"):
            line = line.strip()
            if line == "":
                continue

            line_starts_with_prefix_to_ignore = False
            for prefix_to_ignore in line_prefixes_to_ignore:
                if line.startswith(prefix_to_ignore):
                    line_starts_with_prefix_to_ignore = True
                    break
            if line_starts_with_prefix_to_ignore:
                # Don't colorize
                tmp += "\t" + utils.bcolors.ENDC + line + utils.bcolors.ENDC + "\n"
            else:
                # Colorize
                tmp += "\t" + utils.bcolors.BLUE + line + utils.bcolors.ENDC + "\n"


        # Colorize security related words in red:
        commit_message_lower = tmp.lower().replace("\n", " ").replace("\t", " ")
        offsets_to_patch = []
        for interesting_substrings in utils.security_related_words:

            all_occurrences = [m.start() for m in re.finditer(re.escape(interesting_substrings), commit_message_lower)]
            for entry in all_occurrences:
                offsets_to_patch.append((entry, entry + len(interesting_substrings)))


        # The following code is not really 100% correct. If I have "security related words" which overlap, then
        # I maybe just colorize the first part of the word, e.g. lets assume I have "Don't" in my words and "Don't do this"
        # Then I maybe just colorize "Don't" and not "do this". But that's ok for the moment.
        already_inserted_at = []
        added_chars = len(utils.bcolors.RED)
        while len(offsets_to_patch) != 0:
            (start_offset, end_offset) = offsets_to_patch.pop(0)
            for already_inserted_position in already_inserted_at:
                if already_inserted_position < start_offset:
                    start_offset += added_chars
                if already_inserted_position < end_offset:
                    end_offset += added_chars
            tmp = tmp[:start_offset] + utils.bcolors.RED + tmp[start_offset:end_offset] + utils.bcolors.BLUE + tmp[end_offset:]
            already_inserted_at.append(start_offset)
            already_inserted_at.append(end_offset + added_chars)

        return tmp
