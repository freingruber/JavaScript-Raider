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



# Code to (manually) test if GCE sync via buckets works
# This is some very old code, not sure if this really still works
# Some function names or arguments must maybe be changed (I currently don't have a bucket to test it)

import sys
import os
base_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), '..'))
if base_dir not in sys.path: sys.path.append(base_dir)

import sync_engine.gce_bucket_sync as gce_bucket_sync


gce_bucket_sync.initialize()

gce_bucket_sync.save_new_corpus_file_if_not_already_exists("new_behavior.js", "test new behavior", None, None)
gce_bucket_sync.save_stats("test1.result", "result after time 2a")
gce_bucket_sync.save_new_corpus_file_if_not_already_exists("new_behavior3.js", "test new behavior3", None, None)

content_list = gce_bucket_sync.download_new_corpus_files()
for entry in content_list:
    print(entry)
    print("--------------")

gce_bucket_sync._upload_file("crashes", "test1.js", "crash_content")
content = gce_bucket_sync._download_file("crashes", "test1.js")
print(content)
