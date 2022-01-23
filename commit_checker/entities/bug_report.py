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


# This script contains the class definition for a Bug Report.


class Bug_Report:

    def __init__(self):
        self.number = 0
        self.permission_denied = False
        self.type = ""
        self.status = ""
        self.openedTimestamp = 0
        self.reporter_name = ""
        self.reporter_id = 0
        self.owner_name = ""
        self.owner_id = 0
        self.assigned_persons = []  	# TODO
        self.summary = ""
        self.text = ""

        self.referenced_change_data = []
        self.labels = []
        self.fields = dict()
        self.components = []
        self.priority = 0
        self.comments = []
        self.print_verbose = False
        self.does_not_exist = False

    def does_bug_not_exist(self):
        try:
            if self.does_not_exist:
                return True
            return False
        except:
            return False
        
    def is_restricted(self):
        if self.permission_denied:
            return True
        return False

    def __str__(self):
        tmp = ""
        tmp += "Chromium Bug: %d ( https://bugs.chromium.org/p/v8/issues/detail?id=%d )\n" % (self.number, self.number)
        try:
            if self.does_not_exist:
                tmp += "Bug does not exist!\n"
                return tmp
        except:
            pass
        if self.permission_denied:
            tmp += "Restricted security bug!\n"
            return tmp
        
        tmp += "Summary: %s\n" % self.summary
        tmp += "Type: %s\n" % self.type
        tmp += "Priority: %s\n" % self.priority
        tmp += "Status: %s\n" % self.status
        tmp += "Opened Timestamp: %d\n" % self.openedTimestamp
        tmp += "Reported: %s (%d)\n" % (self.reporter_name, self.reporter_id)
        if self.owner_name == "" and self.owner_id == 0:
            tmp += "Owner: <not assigned yet>\n"
        else:
            tmp += "Owner: %s (%d)\n" % (self.owner_name, self.owner_id)

        
        tmp += "Components: %s\n" % ', '.join(self.components)

        # tmp += "Labels: %s\n" % ', '.join(self.labels)
        tmp += "Labels:\n"
        for label_name in self.labels:
            tmp += "\t%s\n" % label_name
        tmp += "\n"

        tmp += "Fields:\n"
        for field_name in self.fields:
            tmp += "\t%s: %s\n" % (field_name, self.fields[field_name])
        tmp += "\n"

        tmp += "Assigned persons:\n"
        for entry in self.assigned_persons:
            (displayName, userId) = entry
            tmp += "\t%s (%s)\n" % (displayName, userId)
        tmp += "\n"

        if self.print_verbose:
            tmp += "Text:\n%s\n" % self.text
            pass    # TODO implement when I need it
            """
            tmp += "Comments:\n"
            for entry in self.comments:
                (sequence_number, text, comment_author_name, comment_author_id, timestamp) = entry
                
                tmp += "\tComment
            """

        # TODO:
        # self.assigned_persons = []
        # self.text = ""
        # self.referenced_change_data = []
    
        return tmp
