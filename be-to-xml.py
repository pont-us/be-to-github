#!/usr/bin/python2

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
