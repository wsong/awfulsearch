#!/usr/bin/python3

import argparse
from bs4 import BeautifulSoup
import concurrent.futures
import re
import requests
import threading
import urllib.parse

# You can get these values by using Chrome or a similar tool to inspect your
# web requests in a logged-in Something Awful session.
COOKIES_STRING = """
bbuserid=<bbuserid cookie value>; bbpassword=<bbpassword cookie value>;
"""

def get_page_contents(thread_id, page_number):
    url_parts = list(urllib.parse.urlparse(
            "http://forums.somethingawful.com/showthread.php"))
    url_parts[4] = urllib.parse.urlencode(
        [("threadid", str(thread_id)), ("pagenumber", str(page_number))])
    resp = requests.get(urllib.parse.urlunparse(url_parts), headers={"Cookie": COOKIES_STRING.strip()})
    resp.raise_for_status()
    return resp.text

def get_posts(thread_id, page_number):
    contents = get_page_contents(thread_id, page_number)
    soup = BeautifulSoup(contents, "html.parser")
    posts = [s.get_text() for s in soup.find_all(class_="postbody")]
    return posts

def get_max_page_number(thread_id):
    first_page_contents = get_page_contents(thread_id, 1)
    soup = BeautifulSoup(first_page_contents, "html.parser")
    page_buttons = soup.select(".pages.bottom a")
    if not page_buttons:
        return 1
    return int(re.sub("[^0-9]", "", page_buttons[-1].get_text()))

def page_contains_target(thread_id, page_number, target_re):
    try:
        posts = get_posts(thread_id, page_number)
        if not posts:
            return False
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return False
        raise
    compiled_re = re.compile(target_re, flags=re.IGNORECASE)
    for post_text in posts:
        if re.search(compiled_re, post_text):
            return True
    return False

def get_matching_pages(thread_id, target_re, max_workers):
    max_page = get_max_page_number(thread_id)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page_number = {executor.submit(page_contains_target, thread_id, i, target_re): i for i in range(1, max_page + 1)}
        for future in concurrent.futures.as_completed(future_to_page_number):
            page_number = future_to_page_number[future]
            result = future.result()
            if result:
                yield page_number
        return matches

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Awful Search", description="Search a Something Awful thread.")
    parser.add_argument("--thread-id", type=int, required=True, help="The thread ID.")
    parser.add_argument("--target", type=str, required=True, help="The string or regex to search for.")
    parser.add_argument("--max-workers", type=int, default=10, help="The number of threads with which to make requests.")

    args = parser.parse_args()

    matches = []
    for page_number in get_matching_pages(args.thread_id, args.target, args.max_workers):
        matches.append(page_number)
        print("Matched on page %d" % page_number)
    print("Matched on pages %s" % matches)

