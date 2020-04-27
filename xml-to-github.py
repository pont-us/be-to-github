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
    for bug in bug_list:
        print(bug.one_line_summary())
    print("%d bugs read" % len(bug_list))


def extract_targets(bug_tags):
    """Convert BeautifulSoup ResultSet to a targets dictionary

    Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
    bugs, included targets represented as bugs.

    Return a dictionary mapping target UUIDs to Target objects.
    """

    target_map = {}

    for bug_tag in bug_tags:
        severity = bug_tag.severity.get_text()
        if severity == "target":
            target_map[bug_tag.uuid.get_text()] = Target(bug_tag)
    return target_map


def convert_bugs(be_bugs, target_map):
    """Convert BeautifulSoup ResultSet to a list of bugs

    Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
    bugs and a map from target UUIDs to their summaries.

    Return a chronologically sorted list of bug objects.
    """

    bug_list = []
    for be_bug in be_bugs:
        severity = be_bug.severity.get_text()
        if severity != "target":
            bug_list.append(Bug(be_bug))
    
    return sorted(bug_list, key=lambda b: b.created_at)


class Bug:

    def __init__(self, soup_tag):
        self.labels = []
        be_status = soup_tag.status.get_text()
        self.state = "open" if be_status == "open" else "closed"
        if be_status == "wontfix":
            self.labels.append("wontfix")

        # Date format sample: Wed, 01 Apr 2009 22:12:16 +0000
        # Timezone specifier is always +0000.
        
        self.created_at = get_be_creation_date(soup_tag)
        self.title = soup_tag.summary.get_text()

        comment_tags = soup_tag.find_all("comment")
        comments = [Comment(ct) for ct in comment_tags]

    def one_line_summary(self):
        return self.created_at.strftime("%Y-%m-%d") + " " + \
                self.state[0] + " " + self.title


class Comment:

    def __init__(self, soup_tag):
        pass


class Target:

    def __init__(self, soup_tag):
        self.title = soup_tag.summary.get_text()
        self.created_at = get_be_creation_date(soup_tag)
        self.closed = not (soup_tag.status.get_text() == "open")


def get_be_creation_date(soup_tag):
    return datetime.datetime.strptime(soup_tag.created.get_text(),
                                      "%a, %d %b %Y %H:%M:%S +0000")


if __name__ == "__main__":
    main()
