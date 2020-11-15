#!/usr/bin/python3

from __future__ import annotations  # see PEP 563

import argparse
import datetime
from typing import Mapping, List, Optional

from bs4 import BeautifulSoup, Tag, ResultSet


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", action="store_true",
                        help="Write a summary to the standard output.")
    parser.add_argument("xml_file", type=str, help="exported BE XML file")
    args = parser.parse_args()
    with open(args.xml_file, "r") as fh:
        file_content = fh.read()
    converter = Converter(file_content)
    if args.dump:
        converter.print_summary()


class Converter:

    def __init__(self, file_content: str):
        soup = BeautifulSoup(file_content, "xml")
        bug_tags = soup.bugs.find_all("bug")
        target_map = self.extract_targets(bug_tags)
        self.bug_list = self.convert_bugs(bug_tags, target_map)

    def print_summary(self):
        for bug in self.bug_list:
            print(bug.summary())
        print("%d bugs read" % len(self.bug_list))

    @staticmethod
    def extract_targets(bug_tags: ResultSet) -> Mapping[str, Target]:
        """Convert BeautifulSoup ResultSet to a targets dictionary

        Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
        bugs, included targets represented as bugs.

        Return a dictionary mapping target UUID strings to Target objects.
        """

        target_map = {}

        for bug_tag in bug_tags:
            severity = bug_tag.severity.get_text()
            if severity == "target":
                target_map[bug_tag.uuid.get_text()] = Target(bug_tag)
        return target_map

    @staticmethod
    def convert_bugs(
            bug_tags: ResultSet, target_map: Mapping[str, Target]
    ) -> List[Bug]:
        """Convert BeautifulSoup ResultSet to a list of bugs

        Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
        bugs and a map from target UUIDs to their summaries.

        Return a chronologically sorted list of bug objects.
        """

        bug_list = []
        for bug_tag in bug_tags:
            severity = bug_tag.severity.get_text()
            if severity != "target":
                bug_list.append(Bug(bug_tag, target_map))

        return sorted(bug_list, key=lambda b: b.created_at)


class Bug:

    labels: List[str]
    state: str
    created_at: datetime.datetime
    title: str
    body: str
    comments: List[Comment]
    milestone: Optional[Target]

    def __init__(self, soup_tag: Tag, target_map: Mapping[str, Target]):
        # Bug elements: uuid, short-name, severity, status, reporter, creator,
        # created, summary, extra-string

        self.labels = []
        be_status = soup_tag.status.get_text()
        self.state = "open" if be_status == "open" else "closed"
        if be_status == "wontfix":
            self.labels.append("wontfix")

        self.created_at = get_be_creation_date(soup_tag)
        self.title = soup_tag.summary.get_text()

        comment_tags = soup_tag.find_all("comment")
        comments = sorted([Comment(ct) for ct in comment_tags],
                          key=lambda c: c.created_at)
        if comments:
            self.body = comments[0].body_text
            self.comments = comments[1:]
        else:
            self.body = ""
            self.comments = []

        self.milestone = None
        extra_strings = soup_tag.find_all("extra-string")
        for extra_string in extra_strings:
            content = extra_string.get_text()
            if content.startswith("BLOCKS:"):
                uuid = content[7:]
                if uuid in target_map:
                    self.milestone = target_map[uuid]

    def summary(self) -> str:
        bug_line = self.created_at.strftime("%Y-%m-%d ") + str(self.milestone) \
                   + " " + self.state[0] + " " + self.title
        comment_lines = ["\n  " + c.created_at.strftime("%Y-%m-%d ")
                         + c.body_text.translate({ord("\n"): ord(" ")})[:60]
                         for c in self.comments]
        return bug_line + "".join(comment_lines)


class Comment:

    def __init__(self, soup_tag: Tag):
        # Comment elements: uuid, short-name, author, date, content-type, body
        self.created_at = get_be_creation_date(soup_tag, "date")
        self.body_text = soup_tag.body.get_text()


class Target:

    def __init__(self, soup_tag: Tag):
        self.title = soup_tag.summary.get_text()
        self.created_at = get_be_creation_date(soup_tag)
        self.closed = (soup_tag.status.get_text() != "open")

    def __str__(self):
        return self.title


def get_be_creation_date(
        soup_tag: Tag, subtag_name: str = "created"
) -> datetime.datetime:
    # Date format is RFC2822, e.g. "Wed, 01 Apr 2009 22:12:16 +0000".
    # Timezone specifier is always +0000.
    return datetime.datetime.strptime(soup_tag.find(subtag_name).get_text(),
                                      "%a, %d %b %Y %H:%M:%S +0000")


if __name__ == "__main__":
    main()
