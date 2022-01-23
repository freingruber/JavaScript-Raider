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


# This script can be used to download JavaScript testcases from different sources.
# The script is standalone. The output should later be used to start the fuzzer for the first time
# or to start the fuzzer with the import-mode to add new regression tests from browser test suites
# to the current fuzzer corpus.
# The script can be improved by better parsing test suites from browsers which depend on multiple files

# Expected runtime: Some minutes (depending on the crawling timeout value and your internet connection)
# In my case it took ~7 minutes

# And I got something like 148 362 testcases out of it. Bear in mind that
# most of the testcases must further be adapted (e.g.: they use native functions
# which are specific to SpiderMonkey, Chakra or v8. Moreover, they use special
# functions from the test suite of the engine. When importing these files into my fuzzer,
# the fuzzer will handle this. If you want to important the files into another fuzzer,
# you must likely first modify them. My recommendation would be to adapt my fuzzer to
# dump all files (during import mode) instead of actually executing them to dump all
# adapted testcases.

import os
import git      # pip3 install gitpython
import shutil
import tempfile
import glob
import hashlib
import sys
import scrapy   # pip3 install scrapy
import time
from scrapy.crawler import CrawlerProcess
import w3lib.html
import logging


# All found javascript files will be stored in this directory.
# It's recommended to configure the dir output the fuzzers main directory
OUTPUT_DIR = "/home/user/Desktop/temp_js_files/"

CRAWLING_TIMEOUT_BETWEEN_REQUESTS = 0.1


def main():
    handle_ChakraCore_corpus()
    handle_DIE_corpus()
    handle_JavaScript_code_snippets()
    handle_Mozilla_interactive_examples()
    handle_SpiderMonkey_corpus()
    handle_Sputniktests()
    handle_WebKit_corpus()
    handle_v8_corpus()

    process = CrawlerProcess()
    process.crawl(Mozilla_Developer_Spider)
    process.crawl(W3_Exercises_Crawler)
    process.crawl(W3_Resources_Crawler)
    process.start()

    # Add here some other sources, e.g.: you can let fuzzilli run for some time and use it's corpus here as input
    # E.g.: Samuel (the author of fuzzilli) shared privately with me one of his created corpus files
    # Another idea would be start start some other grammar-based fuzzers and feed the input into the exec engine of
    # this fuzzer to get a corpus.



def handle_v8_corpus():
    temp_dir = download_from_git("https://github.com/v8/v8/", "master")
    js_dir = os.path.join(temp_dir, "test")
    find_and_save_all_javascript_files_in_dir(js_dir)
    regex_tests_file = os.path.join(js_dir, "mjsunit", "third_party", "regexp-pcre", "regexp-pcre.js")
    handle_v8_regex_testcase_file(regex_tests_file)
    shutil.rmtree(temp_dir)


# TODO: A lot can be improved like "shouldBe()" should just be replaced with the function call
# The description line must be removed and so on
def handle_v8_regex_testcase_file(filepath):
    id_to_value = dict()
    id_to_code = dict()
    with open(filepath, 'r') as fobj_in:
        content = fobj_in.read()
        for line in content.split("\n"):
            if line == "":
                continue
            if line.startswith("//"):
                continue
            if line.startswith("var res = new Array();"):
                continue
            if line.startswith("res["):
                # E.g.:
                # res[1] = /abc/i;
                line = line[len("res["):]

                id_str = line[:line.index("]")]
                id_value = int(id_str, 10)

                value_with_equal = line[line.index("="):]
                # print("%d %s" % (id_value, value_with_equal))

                id_to_value[id_value] = value_with_equal

            elif line.startswith("assertToStringEquals("):
                # E.g.:
                # assertToStringEquals("abc", res[1].exec("abc"), 0);
                line = line[line.index("res[") + len("res["):]
                id_str = line[:line.index("]")]
                id_value = int(id_str, 10)
                line = line[line.index("]") + 1:]
                parts = line.rsplit(",", 1)
                """
                if len(parts) != 2:
                    print("TODO2 line: %s" % line)
                    sys.exit(-1)
                """
                value = parts[0]

                if id_value not in id_to_code:
                    id_to_code[id_value] = []
                id_to_code[id_value].append(value)

            elif line.startswith("assertNull("):
                # E.g.:
                # assertNull(res[1].exec("*** Failers", 3));
                line = line[line.index("res[") + len("res["):]
                id_str = line[:line.index("]")]
                id_value = int(id_str, 10)
                line = line[line.index("]") + 1:]
                value = line.replace(");", "")
                # print("%d %s" % (id_value, value))

                if id_value not in id_to_code:
                    id_to_code[id_value] = []
                id_to_code[id_value].append(value)

            elif line.startswith("assertThrows("):
                # E.g.:
                # assertThrows("var re = /)/;");
                continue

            else:
                print("TODO line: %s" % line)
                sys.exit(-1)

    for id_value in id_to_value:
        if id_value in id_to_code:
            code = id_to_code[id_value]
        else:
            code = []
        code_to_create_variable = "var var_1_ %s" % id_to_value[id_value]
        save_testcase(code_to_create_variable)
        for code_called_on_variable in code:
            tmp = code_to_create_variable + "\nvar_1_%s;" % code_called_on_variable
            save_testcase(tmp)


def handle_WebKit_corpus():
    temp_dir = download_from_git("https://github.com/WebKit/webkit/", "main")
    examples_dir = os.path.join(temp_dir, "JSTests")
    find_and_save_all_javascript_files_in_dir(examples_dir)
    shutil.rmtree(temp_dir)


def handle_Sputniktests():
    temp_dir = download_from_git("https://github.com/kangax/sputniktests-webrunner/", "master")
    examples_dir = os.path.join(temp_dir, "src", "tests")
    find_and_save_all_javascript_files_in_dir(examples_dir)
    shutil.rmtree(temp_dir)


def handle_SpiderMonkey_corpus():
    temp_dir = download_from_git("https://github.com/mozilla/gecko-dev/", "master")

    examples_dir = os.path.join(temp_dir, "js", "src", "tests")
    find_and_save_all_javascript_files_in_dir(examples_dir)

    examples_dir2 = os.path.join(temp_dir, "js", "src", "jit-test")
    find_and_save_all_javascript_files_in_dir(examples_dir2)
    shutil.rmtree(temp_dir)


def handle_Mozilla_interactive_examples():
    temp_dir = download_from_git("https://github.com/mdn/interactive-examples/", "main")
    examples_dir = os.path.join(temp_dir, "live-examples", "js-examples")
    find_and_save_all_javascript_files_in_dir(examples_dir)
    shutil.rmtree(temp_dir)


def handle_JavaScript_code_snippets():
    # Some random github projects with JavaScript code (many will create testcases with exceptions
    # because they require dependencies or are connected, but at least some will work)

    temp_dir = download_from_git("https://github.com/paulcarroty/JavaScript-Snippets/", "master")
    find_and_save_all_javascript_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/bsansouci/javascript-snippets/", "master")
    find_and_save_all_javascript_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/BolajiAyodeji/js-code-snippets/", "master")
    find_and_save_all_javascript_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/XXXMrG/javascript-snippets/", "master")
    find_and_save_all_javascript_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/Nift/useful-js-snippets/", "master")
    find_and_save_all_javascript_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    # Stuff below here has .md files instead of .js files:

    temp_dir = download_from_git("https://github.com/30-seconds/30-seconds-of-code/", "master")
    sub_dir = os.path.join(temp_dir, "snippets")
    find_and_parse_all_md_files_in_dir(sub_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/JSsnippets/JavaScript-snippets/", "master")
    find_and_parse_all_md_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/bmkmanoj/js-by-examples/", "master")
    find_and_parse_all_md_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)

    temp_dir = download_from_git("https://github.com/tunz/js-vuln-db/", "master")
    find_and_parse_all_md_files_in_dir(temp_dir)
    shutil.rmtree(temp_dir)


def handle_ChakraCore_corpus():
    chakra_dir = download_from_git("https://github.com/microsoft/ChakraCore/", "master")
    test_dir = os.path.join(chakra_dir, "test")
    find_and_save_all_javascript_files_in_dir(test_dir)
    shutil.rmtree(chakra_dir)


def handle_DIE_corpus():
    # This corpus is from the DIE fuzzer paper:
    # https://gts3.org/assets/papers/2020/park:die.pdf
    # I asked the author if she could upload her corpus and she made it available here:
    # https://github.com/sslab-gatech/DIE-corpus
    die_corpus = download_from_git("https://github.com/sslab-gatech/DIE-corpus/", "master")
    find_and_save_all_javascript_files_in_dir(die_corpus)
    shutil.rmtree(die_corpus)


def download_from_git(git_url, branch_name):
    temp_dir = tempfile.mkdtemp()
    print("Going to clone GIT repo: %s" % git_url)
    git.Repo.clone_from(git_url, temp_dir, branch=branch_name, depth=1)
    print("Finished downloading GIT repo!")
    return temp_dir


def calc_hash(content):
    content = content.strip()
    m = hashlib.md5()
    m.update(content.encode("utf-8"))
    content_hash = str(m.hexdigest())
    return content_hash


def find_and_save_all_javascript_files_in_dir(root_dir):
    for filepath in glob.iglob(root_dir + '**/**', recursive=True):
        if filepath.lower().endswith(".js") is False:
            continue
        if os.path.isdir(filepath):
            continue    # skip dirs which end with ".js"

        try:
            with open(filepath, 'r') as fobj_in:
                content = fobj_in.read()
        except:
            # Try with a different encoding
            try:
                with open(filepath, "r", encoding="iso-8859-1") as fobj_in:
                    content = fobj_in.read()
            except:
                print("Skipping testcase because of strange UTF-8 code %s" % filepath)
                continue
        save_testcase(content)


def find_and_parse_all_md_files_in_dir(root_dir):
    for filepath in glob.iglob(root_dir + '**/**', recursive=True):
        if filepath.lower().endswith(".md") is False:
            continue
        if os.path.isdir(filepath):
            continue    # skip dirs which end with ".js"
        with open(filepath, 'r') as fobj_in:
            content = fobj_in.read()

        current_content = ""
        inside_code = False
        for line in content.split("\n"):
            if line.startswith("```js") or line.startswith("```javascript"):
                inside_code = True
                current_content = ""
            elif line.startswith("```") and inside_code:
                save_testcase(current_content.strip())
                current_content = ""
            elif inside_code:
                current_content += line + "\n"


class W3_Resources_Crawler(scrapy.Spider):
    name = "W3 Resources Crawler"
    start_urls = ['https://www.w3resource.com/javascript/javascript.php']

    def __init__(self):
        super().__init__()
        logging.getLogger('scrapy').setLevel(logging.WARNING)  # disable scapy log messages

    def parse(self, response):
        global CRAWLING_TIMEOUT_BETWEEN_REQUESTS
        print("Crawling website: %s" % response.url)
        time.sleep(CRAWLING_TIMEOUT_BETWEEN_REQUESTS)  # throttle requests

        for code in response.xpath('//pre[contains(@class, "well_syntax")]'):
            code_to_store = w3lib.html.remove_tags(code.get()).strip()
            code_to_store = remove_comments_and_empty_lines(code_to_store)
            save_testcase(code_to_store)

        for code in response.xpath('//code[contains(@class, "language-javascript")]'):
            code_to_store = w3lib.html.remove_tags(code.get()).strip()
            code_to_store = remove_comments_and_empty_lines(code_to_store)
            save_testcase(code_to_store)

        other_links = response.css('a::attr(href)').getall()
        for link in other_links:
            if link.startswith("/"):
                full_url = response.urljoin(link)
            elif link.lower().startswith("https://www.w3resource"):
                full_url = link
            else:
                full_url = response.urljoin(link)  # like referenced example files.. but I think I don't need them but just include them to get sure...
            if full_url.lower().startswith("https://www.w3resource.com/javascript/"):
                yield scrapy.Request(full_url, callback=self.parse)


class W3_Exercises_Crawler(scrapy.Spider):
    name = "W3 Exercises Crawler"
    start_urls = ['https://www.w3resource.com/javascript-exercises']

    def __init__(self):
        super().__init__()
        logging.getLogger('scrapy').setLevel(logging.WARNING)  # disable scapy log messages

    def parse(self, response):
        global CRAWLING_TIMEOUT_BETWEEN_REQUESTS
        print("Crawling website: %s" % response.url)
        time.sleep(CRAWLING_TIMEOUT_BETWEEN_REQUESTS)  # throttle requests

        for code in response.xpath('//code[contains(@class, "language-javascript")]'):
            code_to_store = w3lib.html.remove_tags(code.get()).strip()
            code_to_store = remove_comments_and_empty_lines(code_to_store)
            save_testcase(code_to_store)

        other_links = response.css('a::attr(href)').getall()
        for link in other_links:
            if link.startswith("/"):
                full_url = response.urljoin(link)
            elif link.lower().startswith("https://www.w3resource.com/javascript-exercises"):
                full_url = link
            else:
                full_url = response.urljoin(link)
            if full_url.lower().startswith("https://www.w3resource.com/javascript-exercises/"):
                yield scrapy.Request(full_url, callback=self.parse)


class Mozilla_Developer_Spider(scrapy.Spider):
    name = "Mozilla Developer Spider"
    start_urls = ['https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference']

    def __init__(self):
        super().__init__()
        logging.getLogger('scrapy').setLevel(logging.WARNING)  # disable scapy log messages

    def parse(self, response):
        global CRAWLING_TIMEOUT_BETWEEN_REQUESTS
        print("Crawling website: %s" % response.url)

        valid_baseurl1 = "https://developer.mozilla.org/en-US/docs/Web/JavaScript/".lower()
        valid_baseurl2 = "https://developer.mozilla.org/en-US/docs/Learn/JavaScript/".lower()
        valid_relative_baseurl1 = "/en-US/docs/Web/JavaScript".lower()
        valid_relative_baseurl2 = "/en-US/docs/Learn/JavaScript/".lower()

        time.sleep(CRAWLING_TIMEOUT_BETWEEN_REQUESTS)  # throttle requests

        for code in response.xpath('//pre[contains(@class, "brush: js")]'):
            code_to_store = w3lib.html.remove_tags(code.get()).strip()
            code_to_store = remove_comments_and_empty_lines(code_to_store)
            save_testcase(code_to_store)

        # Please note: the above code just crawls the "examples"
        # The interactive examples are not extracted because this is already done from GIT
        # via the handle_Mozilla_interactive_examples() function

        other_links = response.css('a::attr(href)').getall()
        for link in other_links:
            if "$revision" in link.lower():
                continue  # Revisions would go very very deep which would take very long to crawl...
            if link.lower().startswith(valid_relative_baseurl1) or link.lower().startswith(valid_relative_baseurl2):
                yield scrapy.Request(response.urljoin(link), callback=self.parse)
            if link.lower().startswith(valid_baseurl1) or link.lower().startswith(valid_baseurl2):
                yield scrapy.Request(link, callback=self.parse)


def remove_comments_and_empty_lines(code):
    code_new = ""
    for line in code.split("\n"):
        line = line.rstrip()
        if line == "":
            continue

        # I'm just removing lines which start with a comment, not comments
        # at the end/middle of a line
        # => This would require a better parsing to be always correct
        # It's better to remove these comments during testcase standardization with the real fuzzer
        # which implements better parsing
        tmp = line.lstrip(" \t")
        if tmp.startswith("//"):
            continue
        code_new += line + "\n"
    return code_new


def save_testcase(content):
    global OUTPUT_DIR

    content_hash = calc_hash(content)
    output_filename = os.path.join(OUTPUT_DIR, content_hash + ".js")
    if os.path.isfile(output_filename) is False:    # only save if the file was not saved yet
        with open(output_filename, "w") as fobj_out:
            fobj_out.write(content)


if __name__ == '__main__':
    main()
