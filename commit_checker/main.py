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


# This script downloads all v8 changes from the last X days together with the referenced
# Chromium bug reports. This data is then used to decide if the change is security-relevant or not.
# (currently this is just based on the fact if the referenced bug report is public viewable or not,
# but a better logic can be implemented).
# Then, it shows the identified possible security related changes and let the end user
# decide if further investment is required or not.


import pickle
import datetime
import download_change_data
import download_bug_reports
import download_security_classified_crbug_numbers
import utils
import os
import sys
import webbrowser



# if this value is 60, the script will download change data from the last 60 days.
# Theoretically, you can go further back in time and download data from the whole time,
# but this is typically not required (unless you want to implement some learning logic
# like a neuronal network).
# Via the offset url parameter you can just download the last 10 000 entries.
# This is the current implemented method. You can also use the commented code
# in "download_change_data.py" to download older data (via the year parameter).
# Practically, changes older than 60 days aren't really useful for 1days
DOWNLOAD_LAST_X_DAYS = 60

# If you want to show commits not older than date X, then use this setting
# SHOW_ONLY_COMMITS_AFTER_DATE = datetime.datetime.strptime("2021-12-01", "%Y-%m-%d").date()
SHOW_ONLY_COMMITS_AFTER_DATE = datetime.date.today() - datetime.timedelta(days=30)  # show only last 30 day commits


# Typically the script makes 1-2 requests when it's started to check if new data is available
# This can be skipped by setting the next value to True (e.g. when the script is executed multiple times)
# to analyse a database or to modify the script (to skip these requests)
SKIP_DOWNLOADING_DATA = False

all_referenced_v8_bugs = set()
all_referenced_chromium_bugs = set()
number_changes_with_restricted_bug_report = 0
database_permanently_not_interesting_changes = set()
database_my_notes = dict()


def main():
    global DOWNLOAD_LAST_X_DAYS, all_referenced_v8_bugs, all_referenced_chromium_bugs, number_changes_with_restricted_bug_report, SKIP_DOWNLOADING_DATA

    utils.initialize()

    # Load the databases:
    (database_change_data, database_downloaded_change_numbers) = download_change_data.load_database()
    database_bug_reports = download_bug_reports.load_database()
    database_security_bugs_from_rewards = download_security_classified_crbug_numbers.load_database()
    load_permanently_not_interesting_changes_database()
    load_my_notes_database()

    utils.msg("[i] Initial loaded database-statistics:")
    utils.msg("[i] Number of changes in database: %d" % len(database_change_data))
    utils.msg("[i] Number crbug reports in database: %d" % len(database_bug_reports))
    utils.msg("[i] Number security-bugs from reward page in database: %d\n\n" % len(database_security_bugs_from_rewards))

    # Download the change data (commits) of the last days:
    download_data_back_to_date = datetime.date.today() - datetime.timedelta(days=DOWNLOAD_LAST_X_DAYS)

    if SKIP_DOWNLOADING_DATA is False:
        (database_change_data, database_downloaded_change_numbers) = \
            download_change_data.ensure_change_data_is_up_to_date(
                database_change_data,
                database_downloaded_change_numbers,
                download_data_back_to_date)

    utils.msg("[i] Database change_data contains after download %d entries" % len(database_change_data))
    download_change_data.save_database(database_change_data, database_downloaded_change_numbers)

    interesting_change_data_entries = []
    # First loop downloads potential missing bug details and checks if a change is interesting or not
    for change_data in database_change_data:
        # Extract referenced v8 bugs:
        # v8 bugs can be ignored because they are typically not security related
        # security bugs are reported in the chromium bug tracker
        # referenced_v8_bugs = get_referenced_v8_bugs(change_data.commit_message)

        # Extract referenced chromium bugs
        referenced_chromium_bugs = get_referenced_chromium_bugs(change_data.commit_message)

        # Download missing bug details:
        for bug in referenced_chromium_bugs:
            if bug not in database_bug_reports:
                database_bug_reports = download_bug_reports.download_missing_bug_details(database_bug_reports, bug)

        is_interesting = is_change_interesting(change_data, referenced_chromium_bugs, database_bug_reports, database_security_bugs_from_rewards)
        if is_interesting:
            interesting_change_data_entries.append(change_data)

    # Save the updated bug reports database:
    utils.msg("[i] Database bug details contains after download %d entries" % len(database_bug_reports))
    download_bug_reports.save_database(database_bug_reports)

    # And now show the interesting changes:
    current_position = 0
    while True:
        interesting_change_data_entries = remove_permanently_not_interesting_changes(interesting_change_data_entries)

        number_interesting_change_data_entries = len(interesting_change_data_entries)
        if number_interesting_change_data_entries == 0:
            break   # exit because there is no more data available

        # Ensure current position is within the bounds:
        if current_position >= number_interesting_change_data_entries:
            current_position = 0
        elif current_position < 0:
            current_position = number_interesting_change_data_entries - 1

        change_data = interesting_change_data_entries[current_position]
        ret = show_interesting_change(change_data, current_position, number_interesting_change_data_entries)
        current_position += ret

    # Some other analysis functions which are not really used but can be used to further understand the database
    # (e.g.: Analyse which persons patch frequently security vulnerabilities and so on)
    # utils.show_database_statistics(all_referenced_chromium_bugs, database_security_bugs_from_rewards, number_changes_with_restricted_bug_report)
    # utils.show_word_statistic()
    # owners = count_owners(database_change_data)
    # utils.show_owner_summary(owners)



def show_interesting_change(change_data, current_entry, number_of_entries):
    # Now print change details:
    while True:
        os.system("clear")
        header = "-" * 20 + " Potential security change %d of %d " % (current_entry + 1, number_of_entries) + "-"*20
        print(header)
        print(change_data)
        print("-" * len(header))

        notes = get_my_notes(change_data)
        if notes is not None:
            print("My Notes:")
            print(utils.bcolors.BLUE + notes + utils.bcolors.ENDC)
            print("-" * len(header))

        tmp = input("Options:\n\te... exit/quit\n\to... open in browser\n\ta... add notes\n\tc... clear notes\n\tm... mark as not interesting\n\tn... next (or enter)\n\tb... back\n> ")
        tmp = tmp.lower()
        if tmp == "q" or tmp == "quit" or tmp == "e" or tmp == "exit":
            sys.exit(0)
        elif tmp == "o" or tmp == "open":
            webbrowser.open(change_data.get_crbug_url(), new=2)
            continue        # show the bug again
        elif tmp == "n" or tmp == "next" or tmp == "\n" or tmp == "":
            return 1
        elif tmp == "b" or tmp == "back":
            return -1
        elif tmp == "a" or tmp == "add" or tmp == "note" or tmp == "notes":
            note = input("Notes to append (single line):")
            append_to_my_notes(change_data, note)
            continue        # show the bug again
        elif tmp == "c" or tmp == "clear":
            clear_my_notes(change_data)
            continue        # show the bug again
        elif tmp == "m" or tmp == "mark" or tmp == "not interesting":
            mark_change_as_permanently_not_interesting(change_data)
            return 0        # don't change position, because it gets removed we automatically show the next change
        else:
            input("Unkown selection")
            continue


def is_change_interesting(change_data, referenced_chromium_bugs, database_bug_reports, database_security_bugs_from_rewards):
    global number_changes_with_restricted_bug_report, SHOW_ONLY_COMMITS_AFTER_DATE

    updated_date = datetime.datetime.strptime(change_data.updated.split()[0], "%Y-%m-%d").date()
    if updated_date < SHOW_ONLY_COMMITS_AFTER_DATE:
        return False        # Commit is too old

    number_security_related_words = utils.contains_security_related_words(change_data.commit_message)
    should_ignore = utils.should_ignore_change(change_data)

    is_interesting_change = False  # per default bugs are not interesting
    is_bug_referenced_on_rewards_page = False
    is_bug_restricted = False
    for bug in referenced_chromium_bugs:
        if bug in database_security_bugs_from_rewards:
            is_bug_referenced_on_rewards_page = True

        bug_details = database_bug_reports[bug]
        if bug_details.does_bug_not_exist():
            continue  # they referenced a not existing bug, so still not interesting
        if bug_details.is_restricted():
            is_bug_restricted = True

    if is_bug_restricted or is_bug_referenced_on_rewards_page:
        is_interesting_change = True

    if is_bug_restricted:
        number_changes_with_restricted_bug_report += 1

    # This creates currently too many false positives:
    # if should_ignore == False and number_security_related_words >= 2:
    #    is_interesting_change = True
    # if "[sandbox]" in change_data.subject or change_data.owner == "saelo@chromium.org":
    #    # Commits which harden v8
    #    is_interesting_change = True

    return is_interesting_change


def load_permanently_not_interesting_changes_database():
    global database_permanently_not_interesting_changes
    if os.path.exists('database_permanently_not_interesting_changes.pickle'):
        with open('database_permanently_not_interesting_changes.pickle', 'rb') as handle:
            database_permanently_not_interesting_changes = pickle.load(handle)
    else:
        database_permanently_not_interesting_changes = set()    # First invocation


def mark_change_as_permanently_not_interesting(change_data):
    global database_permanently_not_interesting_changes
    database_permanently_not_interesting_changes.add(change_data.number)
    with open('database_permanently_not_interesting_changes.pickle', 'wb') as handle:
        pickle.dump(database_permanently_not_interesting_changes, handle, protocol=pickle.HIGHEST_PROTOCOL)


def is_change_permanently_not_interesting(change_data):
    global database_permanently_not_interesting_changes
    if change_data.number in database_permanently_not_interesting_changes:
        return True
    return False


def remove_permanently_not_interesting_changes(interesting_change_data_entries):
    tmp = []
    for entry in interesting_change_data_entries:
        if is_change_permanently_not_interesting(entry) is False:
            tmp.append(entry)
    return tmp


def load_my_notes_database():
    global database_my_notes
    if os.path.exists('database_my_notes.pickle'):
        with open('database_my_notes.pickle', 'rb') as handle:
            database_my_notes = pickle.load(handle)
    else:
        database_my_notes = dict()    # First invocation


def append_to_my_notes(change_data, msg_to_append):
    global database_my_notes

    if change_data.number not in database_my_notes:
        database_my_notes[change_data.number] = ""
    database_my_notes[change_data.number] += msg_to_append + "\n"

    with open('database_my_notes.pickle', 'wb') as handle:
        pickle.dump(database_my_notes, handle, protocol=pickle.HIGHEST_PROTOCOL)



def clear_my_notes(change_data):
    global database_my_notes

    if change_data.number in database_my_notes:
        del database_my_notes[change_data.number]

    with open('database_my_notes.pickle', 'wb') as handle:
        pickle.dump(database_my_notes, handle, protocol=pickle.HIGHEST_PROTOCOL)


def get_my_notes(change_data):
    global database_my_notes
    if change_data.number in database_my_notes:
        return database_my_notes[change_data.number]
    return None


def get_referenced_v8_bugs(commit_message):
    global all_referenced_v8_bugs

    referenced_v8_bugs = set()
    if "v8:" in commit_message:
        parts = commit_message.split("v8:")
        first = True
        for entry in parts:
            if first:
                first = False
                continue
            entry = entry.strip()
            if entry == "":
                continue
            entry = entry.split()[0]
            if entry.isnumeric():
                all_referenced_v8_bugs.add(int(entry, 10))
                referenced_v8_bugs.add(int(entry, 10))
    return referenced_v8_bugs


def get_referenced_chromium_bugs(commit_message):
    global all_referenced_chromium_bugs
    referenced_chromium_bugs = set()

    if "chromium:" in commit_message:
        parts = commit_message.split("chromium:")
        first = True
        for entry in parts:
            if first:
                first = False
                continue
            entry = entry.strip()
            if entry == "":
                continue
            entry = entry.split()[0]
            if entry.isnumeric():
                all_referenced_chromium_bugs.add(int(entry, 10))
                referenced_chromium_bugs.add(int(entry, 10))
    return referenced_chromium_bugs


def count_owners(database_change_data):
    owners = dict()
    for change_data in database_change_data:
        if change_data.owner not in owners:
            owners[change_data.owner] = 0
        owners[change_data.owner] += 1
    return owners


if __name__ == '__main__':
    main()
