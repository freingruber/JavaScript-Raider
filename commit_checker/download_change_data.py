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
import time
import utils
import os
from entities.change import Change
import datetime

number_changes_to_query_per_iteration = 500         # I think 500 is max

new_downloaded_change_data = 0


def get_json_response(url):
    json_code = requests.get(url).text
    json_code = json_code[4:].strip()
    returned_data = json.loads(json_code)
    # print(json.dumps(returned_data, indent=4, sort_keys=True))
    return returned_data


def query_change_details(change_number):
    url = "https://chromium-review.googlesource.com/changes/v8%%2Fv8~%d/detail?O=916314" % change_number
    returned_data = get_json_response(url)

    created_date = returned_data["created"]
    hashtags = returned_data["hashtags"]
    status = returned_data["status"]
    subject = returned_data["subject"]
    updated_date = returned_data["updated"]
    try:
        owner = returned_data["owner"]["email"]
    except:
        owner = ""
    current_revision = returned_data["current_revision"]

    data = Change()
    data.number = change_number
    data.created = created_date
    data.updated = updated_date
    data.hashtags = hashtags
    data.subject = subject
    data.status = status
    data.owner = owner
    data.current_revision = current_revision

    all_reviewers = set()
    if "reviewer_updates" in returned_data:
        for entry in returned_data["reviewer_updates"]:
            try:
                reviewer = entry["reviewer"]["email"]
            except:
                continue
            if reviewer.startswith("v8-"):
                continue
            all_reviewers.add(reviewer)
    
    if "reviewers" in returned_data and "REVIEWER" in returned_data["reviewers"]:
        for entry in returned_data["reviewers"]["REVIEWER"]:
            try:
                reviewer = entry["email"]
            except:
                continue
            if reviewer.startswith("v8-"):
                continue
            all_reviewers.add(reviewer)
    data.reviewers = list(all_reviewers)


    main_commit_message = ""
    main_revision_commit_number = -1
    all_commit_messages = set()
    revisions = returned_data["revisions"]
    revision_entries = []
    for revision_number in revisions:
        commit_message = revisions[revision_number]["commit"]["message"]
        commit_author = revisions[revision_number]["commit"]["author"]["email"]
        commit_committer = revisions[revision_number]["commit"]["committer"]["email"]
        commit_subject = revisions[revision_number]["commit"]["subject"]

        revision_description = ""
        if "description" in revisions[revision_number]:
            revision_description = revisions[revision_number]["description"]
        revision_commit_number = revisions[revision_number]["_number"]
        revision_entries.append((commit_message, commit_author, commit_committer, commit_subject, revision_description))

        if revision_number == current_revision:
            # print("%s: %s" % (revision_number, commit_message))
            main_commit_message = commit_message
            main_revision_commit_number = revision_commit_number
    
    if main_revision_commit_number == -1:
        utils.perror("Flaw: didn't found correct revision commit number for change: %d" % change_number)
    data.commit_message = main_commit_message
    data.revisions = revision_entries
    
    
    messages = returned_data["messages"]
    messages_entries = []
    for message in messages:
        try:
            author = message["author"]["email"]
        except:
            author = ""
        try:
            real_author = message["real_author"]["email"]
        except:
            real_author = ""
        message = message["message"]
        messages_entries.append((author, real_author, message))
    data.messages = messages_entries

    # Extract the modified files:
    url = "https://chromium-review.googlesource.com/changes/v8%%2Fv8~%d/revisions/%d/files" % (change_number, main_revision_commit_number)
    returned_data = get_json_response(url)
    files = []
    for filename in returned_data:
        entry = returned_data[filename]

        lines_deleted = 0
        lines_inserted = 0
        size = 0
        size_delta = 0
        if "lines_inserted" in entry:
            lines_inserted = entry["lines_inserted"]
        if "lines_deleted" in entry:
            lines_deleted = entry["lines_deleted"]
        if "size" in entry:
            size = entry["size"]
        if "size_delta" in entry:
            size_delta = entry["size_delta"]

        new_entry = (filename, lines_inserted, lines_deleted, size, size_delta)
        files.append(new_entry)
    data.files = files
    
    return data


def load_database():
    if os.path.exists('database_change_data.pickle'):
        with open('database_change_data.pickle', 'rb') as handle:
            database_change_data = pickle.load(handle)
    else:
        database_change_data = []   # First invocation

    if os.path.exists('database_downloaded_change_numbers.pickle'):
        with open('database_downloaded_change_numbers.pickle', 'rb') as handle:
            database_downloaded_change_numbers = pickle.load(handle)
    else:
        database_downloaded_change_numbers = set()  # First invocation

    return database_change_data, database_downloaded_change_numbers


def save_database(database_change_data, database_downloaded_change_numbers):
    with open('database_change_data.pickle', 'wb') as handle:
        pickle.dump(database_change_data, handle, protocol=pickle.HIGHEST_PROTOCOL)

    with open('database_downloaded_change_numbers.pickle', 'wb') as handle:
        pickle.dump(database_downloaded_change_numbers, handle, protocol=pickle.HIGHEST_PROTOCOL)


def ensure_change_data_is_up_to_date(database_change_data, database_downloaded_change_numbers, last_date_to_download):
    global new_downloaded_change_data

    utils.msg("[i] Going to ensure change data is up-to-date...")

    url = "https://chromium-review.googlesource.com/changes/?O=81&S=%d&n=%d&q=project%%3Av8%%2Fv8" % (0, number_changes_to_query_per_iteration)
    returned_data = get_json_response(url)
    for entry in returned_data:
        change_number = entry["_number"]
        if change_number in database_downloaded_change_numbers:
            # TODO: This can be wrong, I could download a change data and later they can update it again... I should also
            # store the last_updated date and replace it if required; But for the moment I don't really care about such updates
            continue    # already downloaded!

        change_data = query_change_details(change_number)
        last_updated = datetime.datetime.strptime(change_data.updated.split(" ")[0], "%Y-%m-%d").date()
        if last_updated < last_date_to_download:
            break  # finished downloading all required data

        utils.msg("[i] Downloaded change data: %d" % change_number)

        database_downloaded_change_numbers.add(change_number)
        database_change_data.append(change_data)
        new_downloaded_change_data += 1
        if new_downloaded_change_data % 20 == 0:
            save_database(database_change_data, database_downloaded_change_numbers)

        time.sleep(0.1)         # sleep for a short time to not overload the website or to write too fast pickle files (this can lead to "permission denied" errors)
    utils.msg("[+] Finished downloading new change data!")
    return database_change_data, database_downloaded_change_numbers


# Old code used to download the full database
"""

    database_downloaded_change_numbers = set()
    database_change_data = []

    load_pickle_files()

    current_offset = 0
    while True:
        utils.msg("[i] Going to crawl from offset: %d" % current_offset)
        # Get all changes for the specified start offset:
        
        # With a year (to download old change data because offset can't be above  10 000)
        #url = "https://chromium-review.googlesource.com/changes/?O=81&S=%d&n=%d&q=project%%3Av8%%2Fv8%%20before%%3A2017-02-18%%20after%%3A2013-01-01" % (current_offset, number_changes_to_query_per_iteration)
        # Without a year:
        url = "https://chromium-review.googlesource.com/changes/?O=81&S=%d&n=%d&q=project%%3Av8%%2Fv8" % (current_offset, number_changes_to_query_per_iteration)
        current_offset += number_changes_to_query_per_iteration
        returned_data = get_json_response(url)
        count = 0
        for entry in returned_data:
            count += 1
            change_number = entry["_number"]
            if change_number in database_downloaded_change_numbers:
                continue    # already downloaded!
            
            utils.msg("[i] Going to download data for: %d" % change_number)
            change_data = query_change_details(change_number)
            database_downloaded_change_numbers.add(change_number)
            database_change_data.append(change_data)
            if count % 1 == 0:
                save_pickle_files()
"""
