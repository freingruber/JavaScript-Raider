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



# Note: This script will take forever.
# Use the Python download script (>1.1_sync_files_from_gce_bucket.py<) instead.

BUCKET_NAME="your-bucket-name-goes-here"

gsutil auth login

mkdir crashes
gsutil -m cp -r gs://$BUCKET_NAME/crashes/* crashes/

mkdir stats
gsutil -m cp -r gs://$BUCKET_NAME/stats/* stats/

# mkdir new_corpus_files
# gsutil -m cp -r gs://$BUCKET_NAME/new_corpus_files/* new_corpus_files/

# mkdir new_behavior
# gsutil -m cp -r gs://$BUCKET_NAME/new_behavior/* new_behavior/
