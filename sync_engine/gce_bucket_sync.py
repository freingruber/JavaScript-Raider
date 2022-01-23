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



# This file implements synchronization via GCE buckets.
# For the future I would not recommend using GCE buckets for this because they are too slow
#
# Command to manually download the bucket:
# mkdir new_corpus_files/
# gsutil auth login
# gsutil -m cp -r gs://your_bucket_name/new_corpus_files/* new_corpus_files/
#
# Hint: I think this sends a lot of DNS requests..

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)
from google.cloud import storage
import utils
import config as cfg
import pickle


storage_client = None
bucket = None
already_imported_files = set()


def initialize():
    global bucket, storage_client
    if not cfg.synchronization_enabled:
        return  # nothing to do
    if cfg.gce_bucket_credential_path is not None:
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = cfg.gce_bucket_credential_path
        storage_client = storage.Client(cfg.gce_bucket_credential_path)
    else:
        # Running on a GCE instance, so the client should find the correct credentials itself
        storage_client = storage.Client()
    bucket = storage_client.get_bucket(cfg.bucket_name)

    __load_already_imported_files()


def __save_already_imported_files():
    global already_imported_files
    with open(cfg.synchronization_already_imported_files_filepath, 'wb') as fout:
        pickle.dump(already_imported_files, fout, pickle.HIGHEST_PROTOCOL)


def __load_already_imported_files():
    global already_imported_files
    if os.path.exists(cfg.synchronization_already_imported_files_filepath):
        with open(cfg.synchronization_already_imported_files_filepath, 'rb') as finput:
            already_imported_files = pickle.load(finput)


def _upload_file(folder_name, filename, file_content):
    global bucket
    blob = bucket.blob("%s/%s" % (folder_name, filename))
    blob.upload_from_string(file_content)


def _download_file(folder_name, filename):
    global bucket
    blob_path = "%s/%s" % (folder_name, filename)
    file_content = bucket.blob(blob_name=blob_path).download_as_string()
    return file_content.decode("utf-8")


def _download_file_raw(folder_name, filename):
    global bucket
    blob_path = "%s/%s" % (folder_name, filename)
    file_content = bucket.blob(blob_name=blob_path).download_as_string()
    return file_content


def _get_all_filenames_in_folder(folder_name):
    global bucket
    ret = []
    for filename in list(bucket.list_blobs(prefix=folder_name + "/")):
        real_filename = filename.name.split("/", 1)[1]
        if real_filename == "":
            continue  # it's the folder entry
        ret.append(real_filename)
    return ret


def _check_if_file_exists_in_folder(folder_name, filename):
    global bucket
    blob_path = "%s/%s" % (folder_name, filename)
    blob = bucket.blob(blob_name=blob_path)
    return blob.exists()


def _save_new_file_if_not_already_exists(folder_name, hash_filename, testcase_content, testcase_tagging_file=None,
                                         testcase_state_file=None, required_coverage_file=None):
    if _check_if_file_exists_in_folder(folder_name, hash_filename):
        return  # File already exists, so it must not be uploaded

    _upload_file(folder_name, hash_filename, testcase_content)
    if testcase_tagging_file is not None:
        tagging_filename = hash_filename + cfg.tagging_filename_extension
        _upload_file(folder_name, tagging_filename, testcase_tagging_file)
    if testcase_state_file is not None:
        state_filename = hash_filename + ".pickle"
        _upload_file(folder_name, state_filename, testcase_state_file)
    if required_coverage_file is not None:
        required_coverage_filename = hash_filename[:-3] + "_required_coverage.pickle"
        _upload_file(folder_name, required_coverage_filename, required_coverage_file)


def save_new_crash_file_if_not_already_exists(hash_filename, crash_content, crash_tagging_file):
    if not cfg.synchronization_enabled:
        return  # nothing to do
    return _save_new_file_if_not_already_exists(cfg.bucket_crashes_folder, hash_filename, crash_content,
                                                testcase_tagging_file=crash_tagging_file, testcase_state_file=None)


def save_new_corpus_file_if_not_already_exists(hash_filename, testcase_content, state_file_content,
                                               required_coverage_content):
    global already_imported_files
    if not cfg.synchronization_enabled:
        return  # nothing to do

    if len(testcase_content) == 0:
        return  # should never occur, but just to get sure
    already_imported_files.add(
        hash_filename)  # ensure that the fuzzer later doesn't download it's own uploaded files again
    return _save_new_file_if_not_already_exists(cfg.bucket_new_corpus_files_folder, hash_filename, testcase_content,
                                                testcase_tagging_file=None, testcase_state_file=state_file_content,
                                                required_coverage_file=required_coverage_content)


def save_new_behavior_file_if_not_already_exists(hash_filename, testcase_content):
    if not cfg.synchronization_enabled:
        return  # nothing to do
    return _save_new_file_if_not_already_exists(cfg.bucket_new_behavior_folder, hash_filename, testcase_content,
                                                testcase_tagging_file=None, testcase_state_file=None)


def save_stats(stats_filename, stats_content):
    if not cfg.synchronization_enabled:
        return  # nothing to do
    # This will also overwrite existing files => I want this behavior because I want to update the old states with the current states
    _upload_file(cfg.bucket_stats_folder, stats_filename, stats_content)


def download_new_corpus_files():
    global already_imported_files
    if not cfg.synchronization_enabled:
        return []  # nothing to do

    utils.msg("[i] Check if new files are in bucket...")

    all_filenames = _get_all_filenames_in_folder(cfg.bucket_new_corpus_files_folder)
    downloaded_files = []
    for filename in all_filenames:
        if filename.endswith(".pickle") or filename.endswith(cfg.tagging_filename_extension):
            continue
        if filename in already_imported_files:
            continue  # skip the file because it was already handled
        already_imported_files.add(
            filename)  # mark the file as "imported" for the next function call because it will be imported after this function call returns
        file_content = _download_file(cfg.bucket_new_corpus_files_folder, filename)
        state_content = _download_file_raw(cfg.bucket_new_corpus_files_folder, filename + ".pickle")
        required_coverage_content = _download_file_raw(cfg.bucket_new_corpus_files_folder,
                                                       filename[:-3] + "_required_coverage.pickle")
        downloaded_files.append((file_content, state_content, required_coverage_content))

    if len(downloaded_files) > 0:
        utils.msg("[i] Download %d new testcases! Going to import them..." % len(downloaded_files))
        __save_already_imported_files()  # make downloaded files persistent
    return downloaded_files
