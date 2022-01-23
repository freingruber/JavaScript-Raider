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



# In general you should sync files via GCE buckets instead.
# I developed this script because I was not sure if really all files were successfully uploaded to the GCE buckets.
# As it turned out, all files were really uploaded.
# You can also use this script to download files, but this requires
# to start all fuzzing machines again (which costs money) and the script is pretty slow.
# The script can also fail because a VM gets preempted
# And, as already mentioned, the runtime is very long. For 270 VM's it takes several days to download everything...
# Maybe I should multi-thread it or create a .zip / .tar.gz file first on the server...
# but you can currently use GCE buckets to get results and in the future a better sync-mechanism will be implemented.
# So this script will not be improved.

# ATTENTION: This script currently also DELETES the instances afterwards.
# You must modify the script to just stop the instances if you don't want to delete them.

import os
import paramiko
import time
import subprocess


ssh = paramiko.SSHClient() 
ssh.set_missing_host_key_policy(paramiko.WarningPolicy())

ssh_username = 'gce_user'
basepath_server = "/home/gce_user/fuzzer/"

# You must create this folder before the script is started
output_path_local = os.path.abspath("ssh_downloaded_files")


project_name = "your-gce-project-name-goes-here"
path_to_ssh_private_key = '/home/user/fuzzer_data/private_key.pem'
private_key_password = 'Your-ssh-password-goes-here'
ssh_key = paramiko.RSAKey.from_private_key_file(path_to_ssh_private_key, password=private_key_password)


def get_all_fuzzer_hostnames():
    ret = []
    result = subprocess.run(['gcloud', 'compute', 'instances', 'list'], stdout=subprocess.PIPE)
    tmp = result.stdout.decode('utf-8')
    for line in tmp.split("\n"):
        line = line.strip()
        if line == "":
            continue
        if "TERMINATED" not in line:
            continue
        parts = line.split()
        instance_name = parts[0]
        instance_zone = parts[1]
        if instance_name == "developer-machine":
            continue    # skip my developer machine
            
        ret.append((instance_name, instance_zone))
    return ret
            
            
            
    
def start_instance(instance_name, instance_zone):
    global project_name
    start_result = subprocess.run(['gcloud', 'beta', 'compute', 'instances', 'start', '--zone', '%s' % instance_zone, '%s' % instance_name, '--project', project_name], stdout=subprocess.PIPE)
    

def get_ip_of_hostname(hostname):
    process_result = subprocess.run(['gcloud', 'compute', 'instances', 'list', hostname], stdout=subprocess.PIPE)
    output = process_result.stdout.decode('utf-8')
    for line in output.split("\n"):
        if hostname in line:
            parts = line.split()
            return parts[5]    # 5 just works with preemptive VMs, if it's not preemptive use 4
    return None


def delete_instance(instance_name, instance_zone):
    remove_result = subprocess.run(['gcloud', 'compute', 'instances', 'delete', instance_name, '--zone', instance_zone, '--quiet'], stdout=subprocess.PIPE)
            

def download_files_from_server(ip, hostname):
    global ssh_key, basepath_server, output_path_local

    output_path_for_this_host = os.path.join(output_path_local, hostname)
    if not os.path.exists(output_path_for_this_host):
        os.makedirs(output_path_for_this_host)
    
    ssh.connect(ip, username=ssh_username, pkey=ssh_key, timeout=5)
    ssh.exec_command("sudo tmux kill-session -t fuzzing")    # kill the fuzzer which may try to load the input files which would slow down the copy process
    time.sleep(2)
    sftp = ssh.open_sftp()

    targets_paths_to_download = []
    targets_paths_to_download.append("OUTPUT")
    for i in range(2, 16+1):
        targets_paths_to_download.append("OUTPUT%d" % i)

    for target_path in targets_paths_to_download:
        local_path_output_folder = os.path.join(output_path_for_this_host, target_path)
        if not os.path.exists(local_path_output_folder):
            os.makedirs(local_path_output_folder)
        
        for folder_name in ["crashes", "crash_exceptions"]:
            target_path_on_server = os.path.join(basepath_server, target_path, folder_name)
            
            local_path = os.path.join(local_path_output_folder, folder_name)
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            item_list = sftp.listdir(target_path_on_server)

            for item in item_list:
                if item.endswith(".js"):
                    # Download the file
                    local_item_path = os.path.join(local_path, item)
                    if os.path.exists(local_item_path):
                        continue    # file was already downloaded
                    sftp.get(os.path.join(target_path_on_server, item), local_item_path)
                elif item.endswith("_previous"):
                    # It's a folder, so download the full folder
                    tmp_folder_path = os.path.join(local_path, item)
                    tmp_target_server_path = os.path.join(target_path_on_server, item)
                    if not os.path.exists(tmp_folder_path):
                        os.makedirs(tmp_folder_path)
                    item_list2 = sftp.listdir(tmp_target_server_path)
                    for item2 in item_list2:
                        sftp.get(os.path.join(tmp_target_server_path, item2), os.path.join(tmp_folder_path, item2))
                
    ssh.close()
    


def main():
    all_fuzzers = get_all_fuzzer_hostnames()
    for fuzzer_entry in all_fuzzers:
        (instance_name, instance_zone) = fuzzer_entry

        # If downloading fails and the script throws an exception (e.g. because preemptive VM was preempted)
        # you must adapt the code slightly to download just from one specific system
        print("Going to handle: %s (zone: %s)" % (instance_name, instance_zone))
        start_instance(instance_name, instance_zone)
        print("Going to sleep for 30 seconds to give enough time to start....")
        time.sleep(30)
        print("After 30 seconds: Now going to get IP of %s" % instance_name)
        ip = get_ip_of_hostname(instance_name)
        print("IP of %s is: %s" % (instance_name, ip))
        print("Going to download all files from %s..." % instance_name)

        download_files_from_server(ip, instance_name)
        print("Finished downloading crashes from: %s\n\n" % instance_name)

        delete_instance(instance_name, instance_zone)
        print("Deleted instance!")
        print("-"*80 + "\n\n\n")

    print("DONE")


if __name__ == "__main__":
    main()
