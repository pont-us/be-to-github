#!/usr/bin/python2

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

import libbe
import libbe.storage.base
import libbe.storage.vcs.git
import libbe.bugdir


def main():
    storage = libbe.storage.vcs.git.ExecGit(".")
    storage.connect()
    bugdir = libbe.bugdir.BugDir(storage, from_storage=True)
    uuids = bugdir.uuids()
    bugs = sorted([bugdir.bug_from_uuid(u) for u in uuids],
                  key=lambda bug: bug.time)
    print("<bugs>")
    for bug in bugs:
        print(bug.xml(indent=2, show_comments=True).encode("utf-8"))
    print("</bugs>")


if __name__ == "__main__":
    main()
