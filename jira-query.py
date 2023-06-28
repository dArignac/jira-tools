#!/usr/bin/env python
import os
import argparse
import json
import sys
import graphviz
import textwrap
import re

import requests
from functools import reduce
from datetime import datetime

# FIXME move to props
MAX_SUMMARY_LENGTH = 30


def log(*args):
    print(*args, file=sys.stderr)


class JiraSearch:
    """This factory will create the actual method used to fetch issues from JIRA. This is really just a closure that
    saves us having to pass a bunch of parameters all over the place all the time."""

    __base_url = None
    __issues = {}

    def __init__(self, url):
        self.__base_url = url
        self.url = url + "/rest/api/latest"
        self.fields = ",".join(
            [
                "key",
                "summary",
                "status",
                "description",
                "issuetype",
                "issuelinks",
                "subtasks",
                "labels",
            ]
        )

    def get(self, uri, params={}):
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(os.environ["JIRA_ACCESS_TOKEN"]),
        }
        url = self.url + uri
        return requests.get(url, params=params, headers=headers, verify=True)

    def get_issue(self, key):
        if key not in self.__issues:
            """Given an issue key (i.e. JRA-9) return the JSON representation of it. This is the only place where we deal
            with JIRA's REST API."""
            # log("Fetching " + key)
            # we need to expand subtasks and links since that's what we care about here.
            response = self.get("/issue/%s" % key, params={"fields": self.fields})
            response.raise_for_status()

            # FIXME could also persist to a file if a config says so
            # print("#" * 100)
            # print(response.text)
            # print("#" * 100)

            self.__issues[key] = response.json()

        return self.__issues[key]

    def query(self, query):
        log("Querying " + query)
        response = self.get("/search", params={"jql": query, "fields": self.fields})
        content = response.json()
        return content["issues"]

    def list_ids(self, query):
        log("Querying " + query)
        response = self.get(
            "/search", params={"jql": query, "fields": "key", "maxResults": 100}
        )
        return [issue["key"] for issue in response.json()["issues"]]

    def get_issue_uri(self, issue_key):
        return self.__base_url + "/browse/" + issue_key


# FIXME move to config file? at least the more complex ones
def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-f",
        "--file-name",
        dest="image_file_name",
        default="output",
        help="Filename without extension to write image to",
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        dest="no_image",
        default=False,
        help="Render graphviz code to stdout instead of generating an image.",
    )
    # FIXME review args from here
    parser.add_argument(
        "-xi",
        "--issue-exclude",
        dest="issue_excludes",
        action="append",
        default=[],
        help="Exclude issue keys - can be repeated for multiple issues",
    )
    # FIXME this was remove from the new code, we always show all directions
    parser.add_argument(
        "-s",
        "--show-directions",
        dest="show_directions",
        default=["inward", "outward"],
        help="which directions to show (inward, outward)",
    )
    parser.add_argument(
        "-d",
        "--directions",
        dest="directions",
        default=["inward", "outward"],
        help="which directions to walk (inward, outward)",
    )
    parser.add_argument(
        "--jql",
        dest="jql_query",
        default=None,
        help="JQL search for issues (e.g. 'project = JRADEV')",
    )
    parser.add_argument(
        "-ns",
        "--node-shape",
        dest="node_shape",
        default="box",
        help="which shape to use for nodes (circle, box, ellipse, etc)",
    )
    parser.add_argument(
        "-t",
        "--ignore-subtasks",
        action="store_true",
        default=False,
        help="Don" "t include sub-tasks issues",
    )
    parser.add_argument(
        "--keep-dot-file",
        dest="keep_dot_file",
        default=False,
        action="store_true",
        help="By default the dot file is removed, set this to true to keep it",
    )
    parser.add_argument(
        "issues", nargs="*", help="The issue key (e.g. JRADEV-1107, JRADEV-1391)"
    )
    parser.add_argument(
        "--config-file",
        dest="config_file",
        default="",
        help="Path to JSON config file",
    )
    return parser.parse_args()


def load_config(config_file):
    with open(config_file) as config_file:
        return json.loads(config_file.read())


class JiraTraversal:
    def __init__(self, config: dict, jira: JiraSearch):
        self.config = config
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
            log(
                "Skipping {} as its status {} is ignored".format(
                    issue_key, issue["fields"]["status"]["name"]
                )
            )
            return

        # FIXME block copied
        # if the issue does not belong to the allowed JIRA projects, then skip it
        if not self.__belongs_to_allowed_project(issue_key):
            log("Skipping " + issue_key + " - not traversing to blacklisted project3")
            return

        # print(issue)

        print(
            "{} - {}: {}".format(
                issue["fields"]["issuetype"]["name"],
                issue_key,
                issue["fields"]["summary"],
            )
        )

        # check the links of the issue
        if "issuelinks" in issue["fields"]:
            for other_link in issue["fields"]["issuelinks"]:
                self.__handle_link(other_link)

    def __handle_link(self, link):
        # FIXME copied
        # don't handle the link if it is an ignored one
        if link["type"]["name"] in self.config["jira"]["ignored_link_type_name"]:
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
            log(
                "Skipping linked issue "
                + linked_issue_key
                + " - not traversing to blacklisted project"
            )
            return

        # FIXME copied
        # skip the link if excluded via config
        if linked_issue_key in self.config["jira"]["issue_excludes"]:
            log("Skipping " + linked_issue_key + " - explicitly excluded")
            return

        # FIXME copied
        # skip ignored statuses of links
        if ("inwardIssue" in link) and (
            link["inwardIssue"]["fields"]["status"]["name"]
            in self.config["jira"]["links"]["ignored_type_statuses"]
        ):
            log(
                "Skipping "
                + linked_issue_key
                + " - linked key is ignored as its status is ignored"
            )
            return
        if ("outwardIssue" in link) and (
            link["outwardIssue"]["fields"]["status"]["name"]
            in self.config["jira"]["links"]["ignored_type_statuses"]
        ):
            log(
                "Skipping "
                + linked_issue_key
                + " - linked key is ignored as its status is ignored"
            )
            return

        # FIXME copied
        if link_type in self.config["jira"]["links"]["excludes"]:
            # FIXME for the children case the linked_issue_key is needed from the caller of this method
            return

        # FIXME copied
        if direction not in self.config["jira"]["show_directions"]:
            # FIXME for the children case the linked_issue_key is needed from the caller of this method
            return
        else:
            issue_type = linked_issue["fields"]["issuetype"]["name"]
            summary = linked_issue["fields"]["summary"]
            estimation = self.__get_estimation(linked_issue["fields"]["description"])
            print(
                f"  {link_type} -> {issue_type} - {linked_issue_key:}: {summary: <{110}} {estimation}"
            )

    def __get_estimation(self, description):
        regex = r"h3. Estimation(['SLMX']{1,3})"
        m = re.search(
            regex,
            description.replace("\n", "").replace("\r", ""),
            re.MULTILINE,
        )
        if m is not None:
            return m.group(1)
        return "Unknown"


def main():
    options = parse_args()

    # FIXME use json schema and have some docs
    config = load_config(options.config_file)

    jira = JiraSearch(config["jira"]["url"])

    # if a jql query was given, fetch all issues of it and add it to the issues list
    if options.jql_query is not None:
        options.issues.extend(jira.list_ids(options.jql_query))

    # map cli params into config
    config["jira"]["issue_excludes"] = options.issue_excludes
    config["jira"]["show_directions"] = options.show_directions

    # default configs
    if "ignored_statuses" not in config["jira"]:
        config["jira"]["ignored_statuses"] = []

    if "ignored_link_type_name" not in config["jira"]:
        config["jira"]["ignored_link_type_name"] = []

    # links config defaults
    if "links" not in config["jira"]:
        config["jira"]["links"] = {}
    if "ignored_type_statuses" not in config["jira"]["links"]:
        config["jira"]["links"]["ignored_type_statuses"] = []
    if "excludes" not in config["jira"]["links"]:
        config["jira"]["links"]["excludes"] = []

    jt = JiraTraversal(config, jira)
    for issue_key in options.issues:
        jt.print_issue(issue_key)


if __name__ == "__main__":
    main()
