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
            "https://forums.somethingawful.com/showthread.php"))
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

def get_target_context(thread_id, page_number, target_re, context_chars):
    try:
        posts = get_posts(thread_id, page_number)
        if not posts:
            return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            return None
        raise
    compiled_re = re.compile(target_re, flags=re.IGNORECASE)
    for post_text in posts:
        match = re.search(compiled_re, post_text)
        if match:
            start_pos = max(match.start() - context_chars, 0)
            end_pos = min(match.end() + context_chars, len(post_text) - 1)
            context = post_text[start_pos:end_pos].strip()
            return context
    return None

def get_matching_pages(thread_id, target_re, max_workers, context_chars):
    max_page = get_max_page_number(thread_id)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_page_number = {executor.submit(get_target_context, thread_id, i, target_re, context_chars): i for i in range(1, max_page + 1)}
        for future in concurrent.futures.as_completed(future_to_page_number):
            page_number = future_to_page_number[future]
            result = future.result()
            if result:
                yield page_number, result
        return matches

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="Awful Search", description="Search a Something Awful thread.")
    parser.add_argument("--thread-id", type=int, required=True, help="The thread ID.")
    parser.add_argument("--target", type=str, required=True, help="The string or regex to search for.")
    parser.add_argument("--max-workers", type=int, default=10, help="The number of threads with which to make requests.")
    parser.add_argument("--context", type=int, default=50, help="The number of characters to show around a successfully matched string.")

    args = parser.parse_args()

    matches = []
    for page_number, context in get_matching_pages(args.thread_id, args.target, args.max_workers, args.context):
        matches.append(page_number)
        print("Matched on page %d: %s" % (page_number, context))
		print("-" * 50)
    matches.sort()
    print("Matched on pages %s" % matches)
