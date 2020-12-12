#!/usr/bin/env python3

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

import requests
import os
import argparse
import github


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command",
                        choices=["delete-issues", "delete-milestones"])
    parser.add_argument("owner")
    parser.add_argument("repo-name")
    args = parser.parse_args()
    print(args)
    if args.command == "delete-issues":
        delete_issues(args.owner, getattr(args, "repo-name"))
    elif args.command == "delete-milestones":
        delete_milestones(args.owner, getattr(args, "repo-name"))


def delete_milestones(owner: str, repo_name: str):
    gh = github.Github(os.environ["BE_TO_GITHUB_TOKEN"])
    repo = gh.get_repo(f"{owner}/{repo_name}")
    milestones = repo.get_milestones(state="all")
    for milestone in milestones:
        milestone.delete()


def delete_issues(owner: str, repo_name: str):
    query = """
    {
      repository(owner: "%s", name: "%s") {
          issues(states:[OPEN,CLOSED], first:100) {
            edges {
              node {
                id
              }
            }
      }
    }
    }
    """ % (owner, repo_name)

    result = graphql_query(query)
    print(result)
    edges = result["data"]["repository"]["issues"]["edges"]
    for edge in edges:
        issue_id = edge["node"]["id"]
        graphql_query("""
    mutation Operation1 {
        deleteIssue(input: {
            issueId: "%s"
            }) {
            clientMutationId
        }
    }
    """ % issue_id)


def graphql_query(query: str):
    request = requests.post(
        "https://api.github.com/graphql",
        json={"query": query},
        headers={"Authorization": "Bearer " +
                 os.environ["BE_TO_GITHUB_TOKEN"]})
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception(f"GraphQL query failed "
                        f"(Status code: {request.status_code})")


if __name__ == "__main__":
    main()
