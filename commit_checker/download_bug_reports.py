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



import requests
import json
import pickle
import utils
import os
import time
from entities.bug_report import Bug_Report


new_downloaded_bugs = 0


def get_chromium_bug_report(bug_number):
    report = Bug_Report()
    report.number = bug_number

    # Get the CSRF Token:
    csrf_token = ""
    response = requests.get("https://bugs.chromium.org/p/chromium/issues/detail?id=%d" % bug_number).text
    for line in response.split("\n"):
        if "'token':" in line:
            csrf_token = line.strip().split()[1]
            csrf_token = csrf_token.lstrip("'")
            csrf_token = csrf_token.rstrip("',")
            break
    if csrf_token == "":
        utils.perror("Error, couldn't get CSRF token!")

    # Download basic report information
    headers = {
        'accept': 'application/json',
        'x-xsrf-token': csrf_token,
        'content-type': 'application/json',
        'origin': 'https://bugs.chromium.org',
    }
    data = '{"issueRef":{"localId":%d,"projectName":"chromium"}}' % bug_number
    response = requests.post('https://bugs.chromium.org/prpc/monorail.Issues/GetIssue', headers=headers, data=data)
    if "Permission denied." in response.text:
        report.permission_denied = True
        return report
    if "The issue does not exist." in response.text:
        report.does_not_exist = True
        return report

    json_code = json.loads(response.text[4:].strip())

   
    report.status = json_code["issue"]["statusRef"]["status"]
    report.openedTimestamp = json_code["issue"]["openedTimestamp"]
    components = []
    if "componentRefs" in json_code["issue"]:
        for entry in json_code["issue"]["componentRefs"]:
            components.append(entry["path"])
    report.components = components
    report.summary = json_code["issue"]["summary"]
    
    report.reporter_name = json_code["issue"]["reporterRef"]["displayName"]
    report.reporter_id = int(json_code["issue"]["reporterRef"]["userId"], 10)

    labels = []
    if "labelRefs" in json_code["issue"]:
        for entry in json_code["issue"]["labelRefs"]:
            labels.append(entry["label"])
    report.labels = labels

    fields = dict()
    if "fieldValues" in json_code["issue"]:
        for entry in json_code["issue"]["fieldValues"]:
            field_name = entry["fieldRef"]["fieldName"]
            field_value = entry["value"]
            fields[field_name] = field_value
    report.fields = fields
    if "Pri" in fields:
        report.priority = int(fields["Pri"], 10)
    if "Type" in fields:
        report.type = fields["Type"]

    # Download comments:
    response = requests.post('https://bugs.chromium.org/prpc/monorail.Issues/ListComments', headers=headers, data=data)
    if "Permission denied." in response.text:
        utils.perror("Should not happen1: %d" % bug_number)
    json_code = json.loads(response.text[4:].strip())

    # print(json.dumps(json_code, indent=4, sort_keys=True))
    comments = []
    for entry in json_code["comments"]:
        text = ""
        if "content" in entry:
            text = entry["content"]

        if "sequenceNum" not in entry:
            sequence_number = 0
            if report.text != "":
                utils.perror("Logic flaw when setting report.text")
            report.text = text
        else:
            sequence_number = entry["sequenceNum"]

        timestamp = entry["timestamp"]

        isDeleted = False
        if "isDeleted" in entry:
            isDeleted = entry["isDeleted"]
        
        if isDeleted:
            comment_author_name = "<deleted>"
            comment_author_id = -1
        else:
            comment_author_name = entry["commenter"]["displayName"]
            comment_author_id = int(entry["commenter"]["userId"], 10)
            
        comments.append((sequence_number, text, comment_author_name, comment_author_id, timestamp, isDeleted))
    report.comments = comments

    # ReferencedIssues (include all CC names of assign persons)
    data = '{"issueRefs":[{"localId":%d,"projectName":"chromium"}]}' % bug_number
    response = requests.post('https://bugs.chromium.org/prpc/monorail.Issues/ListReferencedIssues', headers=headers, data=data)
    if "Permission denied." in response.text:
        utils.perror("Should not happen2: %d" % bug_number)
    json_code = json.loads(response.text[4:].strip())
    # print(json.dumps(json_code, indent=4, sort_keys=True))

    assigned_persons = []
    for ref_name in ["closedRefs", "openRefs"]:
        if ref_name not in json_code:
            continue
        for entry in json_code[ref_name]:
            if "ccRefs" in entry:
                for entry2 in entry["ccRefs"]:
                    displayName = entry2["displayName"]
                    userId = int(entry2["userId"], 10)
                    assigned_persons.append((displayName, userId))
            
            if "ownerRef" in entry:
                if report.owner_name != "":
                    utils.perror("todo in owner_name")
                report.owner_name = entry["ownerRef"]["displayName"]
                report.owner_id = int(entry["ownerRef"]["userId"], 10)

    report.assigned_persons = assigned_persons
    return report


def load_database():
    if os.path.exists('database_bug_reports.pickle'):
        with open('database_bug_reports.pickle', 'rb') as handle:
            database_bug_reports = pickle.load(handle)  # it's a dict and bug number is the key
    else:
        database_bug_reports = dict()    # First invocation
    return database_bug_reports


def save_database(database_bug_reports):
    with open('database_bug_reports.pickle', 'wb') as handle:
        pickle.dump(database_bug_reports, handle, protocol=pickle.HIGHEST_PROTOCOL)


def download_missing_bug_details(database_bug_reports, bug_number):
    global new_downloaded_bugs
    utils.msg("[i] Going to download missing bug details for crbug: %d" % bug_number)

    database_bug_reports[bug_number] = get_chromium_bug_report(bug_number)

    new_downloaded_bugs += 1
    if new_downloaded_bugs % 5 == 0:    # also save the database after every 5th bug to cache (in case script is stopped later)
        save_database(database_bug_reports)

    time.sleep(0.1)         # short sleep to not write too fast and to not send too fast requests
    return database_bug_reports
