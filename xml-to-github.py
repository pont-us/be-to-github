#!/usr/bin/python3

import sys
from bs4 import BeautifulSoup
import datetime


def main():
    with open(sys.argv[1], "r") as fh:
        file_content = fh.read()
    soup = BeautifulSoup(file_content, "xml")
    bugs = soup.bugs.find_all("bug")
    target_map = extract_targets(bugs)
    bug_list = convert_bugs(bugs, target_map)
    print("%d bugs read" % len(bug_list))


def extract_targets(bugs):
    """Convert BeautifulSoup ResultSet to a targets dictionary

    Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
    bugs, included targets represented as bugs.

    Return a dictionary mapping target UUIDs to target summaries.
    """

    target_map = {}

    for bug in bugs:
        severity = bug.severity.get_text()
        if severity == "target":
            target_map[bug.uuid.get_text()] = bug.summary.get_text()

    return target_map


def convert_bugs(be_bugs, target_map):
    """Convert BeautifulSoup ResultSet to a list of bugs

    Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
    bugs and a map from target UUIDs to their summaries.

    Return a chronologically sorted list of bug objects.
    """

    bug_list = []
    for be_bug in be_bugs:
        bug_list.append(Bug(be_bug))
    
    return bug_list


class Bug:

    def __init__(self, bs_tag):
        self.labels = []
        be_status = bs_tag.status.get_text()
        self.state = "open" if be_status == "open" else "closed"
        if be_status == "wontfix":
            self.labels.append("wontfix")

        # Date format sample: Wed, 01 Apr 2009 22:12:16 +0000
        # Timezone specifier is always +0000.
        
        self.created_at = datetime.datetime.strptime(
            bs_tag.created.get_text(),
            "%a, %d %b %Y %H:%M:%S +0000")
        self.title = bs_tag.summary.get_text()


if __name__ == "__main__":
    main()
