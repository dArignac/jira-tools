#!/usr/bin/env python
import argparse
import json
import os
import re
import sys
import textwrap
from datetime import datetime
from functools import reduce

import graphviz
import requests

from jira_tools.config import ConfigAndOptions
from jira_tools.logging import Logging
from jira_tools.search import JiraSearch

# FIXME move to props
MAX_SUMMARY_LENGTH = 30


class JiraTraversal(Logging):
    def __init__(self, config: dict, options: dict, jira: JiraSearch):
        # FIXME init can be extracted
        self.config = config
        self.options = options
        self.jira = jira

    # FIXME copied
    def __belongs_to_allowed_project(self, issue_key):
        if (
            "allowed_project_keys" in self.config["jira"]
            and len(self.config["jira"]["allowed_project_keys"]) > 0
        ):
            return (
                issue_key.split("-", 1)[0]
                in self.config["jira"]["allowed_project_keys"]
            )
        return True

    def print_issue(self, issue_key):
        issue = self.jira.get_issue(issue_key)

        # FIXME block copied
        # filter out if the status of the issue is an ignored one
        if issue["fields"]["status"]["name"] in self.config["jira"]["ignored_statuses"]:
            self.log(
                "Skipping {} as its status {} is ignored".format(
                    issue_key, issue["fields"]["status"]["name"]
                )
            )
            return

        # FIXME block copied
        # if the issue does not belong to the allowed JIRA projects, then skip it
        if not self.__belongs_to_allowed_project(issue_key):
            self.log(
                "Skipping " + issue_key + " - not traversing to blacklisted project3"
            )
            return

        summary = issue["fields"]["summary"]
        print(f"{issue_key}: {summary}")

        # check the links of the issue
        if "issuelinks" in issue["fields"]:
            for other_link in issue["fields"]["issuelinks"]:
                self.__handle_link(other_link)

    def __handle_link(self, link):
        # FIXME copied
        # don't handle the link if it is an ignored one
        if link["type"]["name"] in self.config["jira"]["ignored_link_type_names"]:
            return

        # FIXME copied
        # specify the dot direction of the relation based on the jira direction of the link
        if "outwardIssue" in link:
            direction = "outward"
        elif "inwardIssue" in link:
            direction = "inward"
        else:
            return

        # FIXME copied
        # fetch the issue again, as we need the full set of data (e.g. labels) for styling
        linked_issue = self.jira.get_issue(link[direction + "Issue"]["key"])
        linked_issue_key = linked_issue["key"]
        link_type = link["type"][direction].strip()

        # FIXME copied
        # if the issue does not belong to the allowed JIRA projects, then skip it
        if not self.__belongs_to_allowed_project(linked_issue_key):
            self.log(
                "Skipping linked issue "
                + linked_issue_key
                + " - not traversing to blacklisted project"
            )
            return

        # FIXME copied
        # skip the link if excluded via config
        if linked_issue_key in self.config["jira"]["issue_excludes"]:
            self.log("Skipping " + linked_issue_key + " - explicitly excluded")
            return

        # FIXME copied
        # skip ignored statuses of links
        if ("inwardIssue" in link) and (
            link["inwardIssue"]["fields"]["status"]["name"]
            in self.config["jira"]["links"]["ignored_statuses"]
        ):
            self.log(
                "Skipping "
                + linked_issue_key
                + " - linked key is ignored as its status is ignored"
            )
            return
        if ("outwardIssue" in link) and (
            link["outwardIssue"]["fields"]["status"]["name"]
            in self.config["jira"]["links"]["ignored_statuses"]
        ):
            self.log(
                "Skipping "
                + linked_issue_key
                + " - linked key is ignored as its status is ignored"
            )
            return

        # FIXME copied
        if direction not in self.config["jira"]["show_directions"]:
            # FIXME for the children case the linked_issue_key is needed from the caller of this method
            return
        else:
            summary = linked_issue["fields"]["summary"]
            estimation = self.__get_estimation(linked_issue["fields"]["description"])
            status = linked_issue["fields"]["status"]["name"]
            # FIXME configurable
            # print(f"  > {linked_issue_key:}: {estimation}")
            print(
                f"{linked_issue_key:}: {summary: <{110}} {estimation: <{10}} {status}"
            )
            # print(f"{linked_issue_key:};{summary};{estimation}")

    # FIXME make configurable
    def __get_estimation(self, description):
        regex = r"h3. Estimation(['-SLMX']{1,4})"
        m = re.search(
            regex,
            description.replace("\n", "").replace("\r", ""),
            re.MULTILINE,
        )
        if m is not None:
            return m.group(1)
        return "Unknown"


# FIXME would need a config to only include specific link type instead of blacklisting all unwanted
def main():
    config, options = ConfigAndOptions().get_config_and_options()

    jira = JiraSearch(config, options)

    # if a jql query was given, fetch all issues of it and add it to the issues list
    if options.jql_query is not None:
        options.issues.extend(jira.list_ids(options.jql_query))

    jt = JiraTraversal(config, options, jira)
    for issue_key in options.issues:
        jt.print_issue(issue_key)


if __name__ == "__main__":
    main()
