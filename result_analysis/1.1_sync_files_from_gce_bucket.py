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



# This script downloads results from the GCE bucket
# Please note: You can also download files via command line (gcloud), but this is extremely slow
# (I mean really, really slow..)
# This script is a lot faster (but still slow...)

from google.cloud import storage
import os


# Output folders to which the GCE bucket files should be downloaded.
# These folders must already exist before the script is started
crashes_out_dir = os.path.abspath("crashes")
stats_out_dir = os.path.abspath("stats")

# False... The script will just download discovered crashes
# True... The script will also download stats files
# Be aware: Depending on the runtime and number of your machines,
# the stats files can easily consuming several GB of disk space
also_download_stats = True

gce_bucket_credential_path = "/home/user/key/your_gce_service_account_credentials.json"
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = gce_bucket_credential_path
storage_client = storage.Client(gce_bucket_credential_path)
bucket = storage_client.get_bucket("your_gce_bucket_name")


def get_all_filenames_in_folder(folder_name):
    global bucket
    ret = []
    for filename in list(bucket.list_blobs(prefix=folder_name + "/")):
        real_filename = filename.name.split("/", 1)[1]
        if real_filename == "":
            continue    # it's the folder entry
        ret.append(real_filename)    
    return ret


def download_file(folder_name, filename):
    global bucket
    blob_path = "%s/%s" % (folder_name, filename)
    file_content = bucket.blob(blob_name=blob_path).download_as_string()
    return file_content.decode("utf-8") 



def main():
    global also_download_stats

    print("Going to query all crash names...")
    all_crash_names = get_all_filenames_in_folder("crashes")

    idx = 0
    total = len(all_crash_names)
    for crash_name in all_crash_names:
        idx += 1
        output_fullpath = os.path.join(crashes_out_dir, crash_name)
        if os.path.exists(output_fullpath):
            continue    # file must not be downloaded again

        file_content = download_file("crashes", crash_name)
        print("Downloaded file %s (%d / %d)" % (crash_name, idx, total))
        with open(output_fullpath, "w") as fobj:
            fobj.write(file_content)

    print("Downloaded in total %d crash files!" % len(all_crash_names))

    if also_download_stats is False:
        return
    # Below code is to download the .stats files (which can easily consume several GB!
    print("Going to query all stats names...")
    all_stats_names = get_all_filenames_in_folder("stats")

    idx = 0
    total = len(all_stats_names)
    for stats_name in all_stats_names:
        idx += 1
        output_fullpath = os.path.join(stats_out_dir, stats_name)
        if os.path.exists(output_fullpath):
            continue    # file must not be downloaded again

        file_content = download_file("stats", stats_name)
        print("Downloaded file %s (%d / %d)" % (stats_name, idx, total))
        with open(output_fullpath, "w") as fobj:
            fobj.write(file_content)

    print("Downloaded in total %d stats files!" % len(all_stats_names))


if __name__ == "__main__":
    main()
