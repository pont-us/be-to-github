#!/usr/bin/python3

# Copyright 2020 Pontus Lurcock
#
# This file is part of be-to-github.
#
# be-to-github is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by the
# Free Software Foundation, either version 3 of the License, or (at your
# option) any later version.
#
# be-to-github is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with be-to-github. If not, see <https://www.gnu.org/licenses/>.

from __future__ import annotations  # see PEP 563

import argparse
import datetime
import re

import requests
import os
from typing import Mapping, List, Optional, Set

from bs4 import BeautifulSoup, Tag, ResultSet
import github


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump-to", type=str, metavar="FILENAME",
                        help="Write a summary to the specified file.")
    parser.add_argument("--owner", type=str,
                        help="GitHub username of repository owner")
    parser.add_argument("--repo", type=str,
                        help="name of GitHub repository")
    parser.add_argument("--verbose", action="store_true",
                        help="Report conversion progress to standard output.")
    parser.add_argument("--preserve-newlines", metavar="FILENAME", type=str,
                        help="File listing UUIDs for which newlines should be "
                             "preserved.")
    parser.add_argument("xml_file", type=str, help="exported BE XML file")
    args = parser.parse_args()
    with open(args.xml_file, "r") as fh:
        file_content = fh.read()
    converter = Converter(file_content, args.preserve_newlines)
    if args.dump_to:
        converter.print_summary(args.dump_to)
    if args.owner and args.repo:
        converter.export_via_pygithub(args.owner, args.repo, args.verbose)


class Converter:

    def __init__(self, file_content: str,
                 preserve_newlines_file: Optional[str]):
        soup = BeautifulSoup(file_content, "xml")
        bug_tags = soup.bugs.find_all("bug")
        self.target_map = self.extract_targets(bug_tags)
        self._graphql_headers = \
            {"Authorization": "Bearer " + os.environ["BE_TO_GITHUB_TOKEN"]}
        self.bug_list = self.convert_bugs(bug_tags)
        self.preserve_newlines = set()
        if preserve_newlines_file is not None:
            with open(preserve_newlines_file, "r") as fh:
                for line in fh.readlines():
                    self.preserve_newlines.add(line.strip())

    def print_summary(self, filename):
        with open(filename, "w") as fh:
            fh.writelines(bug.summary() + "\n" for bug in self.bug_list)
            fh.write("%d bugs read\n" % len(self.bug_list))

    def export_to_github(self, owner: str, repo_name: str):
        # Note: at present only exports the first bug
        repo_id = self._get_repo_id(owner, repo_name)
        self._graphql_query(self.bug_list[0].to_graphql(repo_id))

    def _get_repo_id(self, owner, repo_name):
        query = """
            query Operation1 {
                repository(owner: "%s", name: "%s") {
                    id
                }
            }
        """ % (owner, repo_name)
        result = self._graphql_query(query)
        return result["data"]["repository"]["id"]

    def _graphql_query(self, query: str) -> Mapping:
        request = requests.post(
            "https://api.github.com/graphql",
            json={"query": query}, headers=self._graphql_headers)
        if request.status_code == 200:
            return request.json()
        else:
            raise Exception(f"GraphQL query failed "
                            f"(Status code: {request.status_code})")

    def export_via_pygithub(
            self, owner: str, repo_name: str, verbose: bool
    ) -> None:
        gh = github.Github(os.environ["BE_TO_GITHUB_TOKEN"])
        repo = gh.get_repo(f"{owner}/{repo_name}")
        # TODO: export more than two bugs (currently restricted for testing)
        milestone_map = {}
        for target in self.target_map.values():
            milestone_map[target.title] = repo.create_milestone(
                title=target.title, state="closed" if target.closed else "open")
        for bug in self.bug_list[:2]:
            bug.export_via_pygithub(repo, milestone_map, verbose,
                                    self.preserve_newlines)

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

    def convert_bugs(self, bug_tags: ResultSet) -> List[Bug]:
        """Convert BeautifulSoup ResultSet to a list of bugs

        Take a BeautifulSoup ResultSet containing exported Bugs Everywhere
        bugs and a map from target UUIDs to their summaries.

        Return a chronologically sorted list of bug objects.
        """

        bug_list = []
        for bug_tag in bug_tags:
            severity = bug_tag.severity.get_text()
            if severity != "target":
                bug_list.append(Bug(bug_tag, self.target_map))

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

        self.uuid = soup_tag.uuid.get_text()
        self.short_name = soup_tag.find("short-name").get_text()
        self.severity = soup_tag.severity.get_text()
        self.reporter = soup_tag.reporter.get_text()
        self.creator = soup_tag.creator.get_text()
        self.labels = []
        self.be_status = soup_tag.status.get_text()
        self.state = "open" if self.be_status == "open" else "closed"
        if self.be_status == "wontfix":
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

    def to_graphql(self, repo_id: str) -> str:
        # Currently only includes title and body, and doesn't add comments.
        # (But comments may need a separate method anyway, since we don't
        # know the Issue ID until it's been created.)
        query = '''
        mutation Operation1 {
            createIssue(input: {
                repositoryId: "%s",
                title: "%s",
                body: """
        %s
                """}) {
                issue {
                    id
                }
            }
        }''' % (repo_id, self.title, self.body)
        return query

    def export_via_pygithub(self, repo, milestone_map, verbose: bool,
                            preserve_newlines: Set[str]):
        # TODO: add mechanism to selectively disable line break removal
        match = re.search(r"^(.*) \[(\d+)]$", self.title)
        if match is not None:
            title, ditz_index = match.groups()
        else:
            title, ditz_index = self.title, None
        create_args = dict(
            title=title,
            body=(self.body if self.uuid in preserve_newlines
                  else unwrap_lines(self.body)),
        )
        if self.milestone is not None:
            create_args["milestone"] = milestone_map[self.milestone.title]
        issue = repo.create_issue(**create_args)
        issue.edit(state=self.state)
        ditz_part = "" if ditz_index is None else \
            ("Ditz bug index: %s\n" % ditz_index)
        issue.create_comment(f"""```
Bugs Everywhere data:
Created at: {self.created_at.isoformat(" ")}
Status: {self.be_status}
Severity: {self.severity}
UUID: {self.uuid}
Short name: {self.short_name}
{ditz_part}```""")
        if verbose:
            print(title)
        for comment in self.comments:
            comment.export_via_pygithub(issue, verbose, preserve_newlines)


class Comment:

    def __init__(self, soup_tag: Tag):
        # Comment elements: uuid, short-name, author, date, content-type, body
        self.created_at = get_be_creation_date(soup_tag, "date")
        self.body_text = soup_tag.body.get_text()
        self.uuid = soup_tag.uuid.get_text()

    def to_graphql(self, issue_id: str) -> str:
        query = '''
        mutation Operation1 {
            addComment(input: {
              subjectId: "%s",
              body: """
        %s
              """
            }) {
              clientMutationId
            }
            }
        ''' % (issue_id, self.body_text)
        return query

    def export_via_pygithub(self, issue, verbose, preserve_newlines):
        issue.create_comment(
            self.created_at.isoformat(" ") + "\n\n" +
            (self.body_text if self.uuid in preserve_newlines
             else unwrap_lines(self.body_text))
            + "\n\n" +
            f"UUID: {self.uuid}")
        if verbose:
            print("  " + self.body_text[:40] + "...")


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


def unwrap_lines(wrapped: str) -> str:
    """Replace newlines with spaces.

    Multiple successive newlines are not replaced. Neither is a newline
    at the end of the string."""
    return re.sub(r"(?<!\n)\n(?!(\n|$))", " ", wrapped)

if __name__ == "__main__":
    main()
