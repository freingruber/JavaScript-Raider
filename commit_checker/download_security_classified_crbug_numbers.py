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


# We can use the "Chrome update news" to detect which bugs were security related.
# This information can be used to label older CRBugs (e.g. "security relevant" or "not security relevant")
# The labels are important when the data is passed to some learning logic.
# For example, a neuronal network can be used to detect if a commit fixes an interesting CRBug (an exploitable 1day).
# Data like "CRBug public viewable or not", authors of the commit patch, reviewers of the commit,
# how long did it take to fix the bug, date of the fix, referenced persons, which files were modified, which words occur in the commit message,
# which words are used in the discussion-messages, assigned tags, ... can be used as input to the neuronal network.
# With the correct labels (which this script downloads), the neuronal network can learn to detect if a commit is
# interesting or not.


import requests
import sys
import pickle
import re
import utils
import os

all_urls = """https://chromereleases.googleblog.com/2021/08/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/08/the-stable-channel-has-been-updated-to.html
https://chromereleases.googleblog.com/2021/07/stable-channel-update-for-desktop_20.html
https://chromereleases.googleblog.com/2021/07/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/06/stable-channel-update-for-desktop_17.html
https://chromereleases.googleblog.com/2021/06/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/05/stable-channel-update-for-desktop_25.html
https://chromereleases.googleblog.com/2021/05/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/04/stable-channel-update-for-desktop_26.html
https://chromereleases.googleblog.com/2021/04/stable-channel-update-for-desktop_20.html
https://chromereleases.googleblog.com/2021/04/stable-channel-update-for-desktop_14.html
https://chromereleases.googleblog.com/2021/04/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/03/stable-channel-update-for-desktop_30.html
https://chromereleases.googleblog.com/2021/03/stable-channel-update-for-desktop_12.html
https://chromereleases.googleblog.com/2021/03/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/02/stable-channel-update-for-desktop_16.html
https://chromereleases.googleblog.com/2021/02/stable-channel-update-for-desktop_4.html
https://chromereleases.googleblog.com/2021/02/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2021/01/stable-channel-update-for-desktop_19.html
https://chromereleases.googleblog.com/2021/01/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/12/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/11/stable-channel-update-for-desktop_17.html
https://chromereleases.googleblog.com/2020/11/stable-channel-update-for-desktop_11.html
https://chromereleases.googleblog.com/2020/11/stable-channel-update-for-desktop_9.html
https://chromereleases.googleblog.com/2020/11/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/10/stable-channel-update-for-desktop_20.html
https://chromereleases.googleblog.com/2020/10/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/10/beta-channel-update-for-desktop_6.html
https://chromereleases.googleblog.com/2020/09/stable-channel-update-for-desktop_21.html
https://chromereleases.googleblog.com/2020/09/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/08/stable-channel-update-for-desktop_25.html
https://chromereleases.googleblog.com/2020/08/stable-channel-update-for-desktop_18.html
https://chromereleases.googleblog.com/2020/08/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/07/stable-channel-update-for-desktop_27.html
https://chromereleases.googleblog.com/2020/07/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/06/stable-channel-update-for-desktop_22.html
https://chromereleases.googleblog.com/2020/06/stable-channel-update-for-desktop_15.html
https://chromereleases.googleblog.com/2020/06/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/05/stable-channel-update-for-desktop_19.html
https://chromereleases.googleblog.com/2020/05/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/04/stable-channel-update-for-desktop_27.html
https://chromereleases.googleblog.com/2020/04/stable-channel-update-for-desktop_21.html
https://chromereleases.googleblog.com/2020/04/stable-channel-update-for-desktop_15.html
https://chromereleases.googleblog.com/2020/04/stable-channel-update-for-desktop_7.html
https://chromereleases.googleblog.com/2020/03/stable-channel-update-for-desktop_31.html
https://chromereleases.googleblog.com/2020/03/stable-channel-update-for-desktop_18.html
https://chromereleases.googleblog.com/2020/03/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/02/stable-channel-update-for-desktop_24.html
https://chromereleases.googleblog.com/2020/02/stable-channel-update-for-desktop_18.html
https://chromereleases.googleblog.com/2020/02/stable-channel-update-for-desktop_13.html
https://chromereleases.googleblog.com/2020/02/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2020/01/stable-channel-update-for-desktop_16.html
https://chromereleases.googleblog.com/2020/01/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/12/stable-channel-update-for-desktop_17.html
https://chromereleases.googleblog.com/2019/12/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/11/stable-channel-update-for-desktop_18.html
https://chromereleases.googleblog.com/2019/10/stable-channel-update-for-desktop_31.html
https://chromereleases.googleblog.com/2019/10/stable-channel-update-for-desktop_22.html
https://chromereleases.googleblog.com/2019/10/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/09/stable-channel-update-for-desktop_18.html
https://chromereleases.googleblog.com/2019/09/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/08/stable-channel-update-for-desktop_26.html
https://chromereleases.googleblog.com/2019/08/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/07/stable-channel-update-for-desktop_30.html
https://chromereleases.googleblog.com/2019/07/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/06/stable-channel-update-for-desktop_13.html
https://chromereleases.googleblog.com/2019/06/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/05/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/04/stable-channel-update-for-desktop_30.html
https://chromereleases.googleblog.com/2019/04/stable-channel-update-for-desktop_23.html
https://chromereleases.googleblog.com/2019/04/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/03/stable-channel-update-for-desktop_12.html
https://chromereleases.googleblog.com/2019/03/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/02/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2019/01/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/12/stable-channel-update-for-desktop_12.html
https://chromereleases.googleblog.com/2018/12/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/11/stable-channel-update-for-desktop_19.html
https://chromereleases.googleblog.com/2018/11/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/10/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/09/stable-channel-update-for-desktop_17.html
https://chromereleases.googleblog.com/2018/09/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/07/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/06/stable-channel-update-for-desktop_12.html
https://chromereleases.googleblog.com/2018/06/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/05/stable-channel-update-for-desktop_58.html
https://chromereleases.googleblog.com/2018/05/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/04/stable-channel-update-for-desktop_26.html
https://chromereleases.googleblog.com/2018/04/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/03/stable-channel-update-for-desktop_20.html
https://chromereleases.googleblog.com/2018/03/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/02/stable-channel-update-for-desktop_13.html
https://chromereleases.googleblog.com/2018/02/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2018/01/stable-channel-update-for-desktop_24.html
https://chromereleases.googleblog.com/2017/12/stable-channel-update-for-desktop_14.html
https://chromereleases.googleblog.com/2017/12/stable-channel-update-for-desktop.html
https://chromereleases.googleblog.com/2017/11/stable-channel-update-for-desktop_13.html
https://chromereleases.googleblog.com/2017/11/stable-channel-update-for-desktop.html"""


def get_response(arg_url):
    response = requests.get(arg_url).text
    return response



def load_database():
    if os.path.exists('database_security_bugs_from_rewards.pickle'):
        with open('database_security_bugs_from_rewards.pickle', 'rb') as handle:
            database_security_bugs_from_rewards = pickle.load(handle)
    else:
        database_security_bugs_from_rewards = set()
    return database_security_bugs_from_rewards


def get_all_referenced_bugs(arg_url):
    chromium_bug_ids = set()

    response = get_response(arg_url)

    if "https://bugs.chromium.org/p/v8/issues/detail?id=" in arg_url:
        utils.perror("TODO: %s" % arg_url)

    for entry in re.findall(r'https://crbug.com/[0-9]+', response):
        chromium_bug_ids.add(int(entry[len("https://crbug.com/"):], 10))
    for entry in re.findall(r'https://bugs.chromium.org/p/chromium/issues/detail\?id=[0-9]+', response):
        chromium_bug_ids.add(int(entry[len("https://bugs.chromium.org/p/chromium/issues/detail?id="):], 10))
    return chromium_bug_ids


def main():
    all_security_bugs = set()
    for url in all_urls.split():
        url = url.strip()
        if url == "":
            continue
        utils.msg("[i] Going to download from: %s" % url)
        bugs = get_all_referenced_bugs(url)
        all_security_bugs.update(bugs)

    with open('database_security_bugs_from_rewards.pickle', 'wb') as handle:
        pickle.dump(all_security_bugs, handle, protocol=pickle.HIGHEST_PROTOCOL)


if __name__ == '__main__':
    main()
