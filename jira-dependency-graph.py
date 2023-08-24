#!/usr/bin/env python
import argparse
import json
import os
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


class DotGenerator(Logging):
    # FIXME not sure if really needed, old code is disabled where that applies
    seen_issue_keys = []
    graph = []
    added_issue_keys = []

    def __init__(self, config: dict, options: dict, jira: JiraSearch):
        self.config = config
        self.options = options
        self.jira = jira
        self.issues_list = self.options.issues

    def __create_image(self, graph_data, image_file_name, node_shape, keep_dot_file):
        legend = ""
        if "legend" in self.config["layout"]:
            legend = 'label=<{}>;fontname="{}";\n'.format(
                self.config["layout"]["legend"].format(
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                ),
                self.config["layout"]["defaults"]["fontName"],
            )
        digraph = "digraph{{\n{}".format(legend)

        digraph += "node [shape=" + node_shape + "];\n%s\n}" % ";\n".join(graph_data)

        g = graphviz.Source(digraph)
        g.format = "png"
        g.render(filename=image_file_name, cleanup=not keep_dot_file)

        return image_file_name

    def __generate(self) -> list:
        for issue_key in self.issues_list:
            self.__create_dot_for_jira_issue(issue_key)
        return self.graph

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

    def __create_dot_for_jira_issue(self, issue_key) -> list:
        # fetch issue details from JIRA, add to seen list
        issue = self.jira.get_issue(issue_key)

        # FIXME where do we need that?
        self.seen_issue_keys.append(issue_key)

        # FIXME we currently not use this
        children = []

        # filter out if the status of the issue is an ignored one
        if issue["fields"]["status"]["name"] in self.config["jira"]["ignored_statuses"]:
            self.log(
                "Skipping {} as its status {} is ignored".format(
                    issue_key, issue["fields"]["status"]["name"]
                )
            )
            return

        # if the issue does not belong to the allowed JIRA projects, then skip it
        if not self.__belongs_to_allowed_project(issue_key):
            self.log(
                "Skipping " + issue_key + " - not traversing to blacklisted project3"
            )
            return

        # add the dot node for the issue
        self.graph.append(
            self.__create_node_for_issue(
                issue_key,
                issue["fields"],
                is_link=False,
            )
        )
        self.added_issue_keys.append(issue_key)

        # FIXME do we need that?
        # if not ignore_subtasks:
        #     if fields["issuetype"]["name"] == "Epic" and not ignore_epic:
        #         issues = jira.query('"Epic Link" = "%s"' % issue_key)
        #         for subtask in issues:
        #             subtask_key = get_key(subtask)
        #             self.log(subtask_key + " => references epic => " + issue_key)
        #             node = "{}->{}[color=orange]".format(
        #                 create_node_text(issue_key, fields),
        #                 create_node_text(subtask_key, subtask["fields"]),
        #             )
        #             graph.append(node)
        #             children.append(subtask_key)
        #     if "subtasks" in fields and not ignore_subtasks:
        #         for subtask in fields["subtasks"]:
        #             subtask_key = get_key(subtask)
        #             self.log(issue_key + " => has subtask => " + subtask_key)
        #             node = '{}->{}[color=blue][label="subtask"]'.format(
        #                 create_node_text(issue_key, fields),
        #                 create_node_text(subtask_key, subtask["fields"]),
        #             )
        #             graph.append(node)
        #             children.append(subtask_key)

        # check the links of the issue and add them to the graph as well
        if "issuelinks" in issue["fields"]:
            for other_link in issue["fields"]["issuelinks"]:
                self.__handle_issue_link(issue_key, issue["fields"], other_link)

                # FIXME only needed if we walk the children later, see below - the return from __handle_issue_link was removed!
                # if link_issue_key is not None:
                #     # self.log("Appending " + link_issue_key)
                #     children.append(link_issue_key)

        # FIXME disable for now, would again query everything for every linked issue, is the only one using seen_issue_keys
        # now construct graph data for all subtasks and links of this issue
        # for child in (x for x in children if x not in seen):
        #     walk(child, graph)

        return []

    def __handle_issue_link(self, issue_key, issue_fields, link):
        # don't handle the link if it is an ignored one
        # self.log(link["type"]["name"])
        if link["type"]["name"] in self.config["jira"]["ignored_link_type_names"]:
            return

        # FIXME move to config
        # exclude blocks relations which are of type "Blocks" and outward. In contrast the "Blocked by" is also type "Blocks" but inward
        if ("inwardIssue" in link) and link["type"]["name"] in ["Blocks"]:
            return

        # specify the dot direction of the relation based on the jira direction of the link
        if "outwardIssue" in link:
            direction = "outward"
        elif "inwardIssue" in link:
            direction = "inward"
        else:
            return

        # fetch the issue again, as we need the full set of data (e.g. labels) for styling
        linked_issue = self.jira.get_issue(link[direction + "Issue"]["key"])
        linked_issue_key = linked_issue["key"]
        link_type = link["type"][direction].strip()

        # if the issue does not belong to the allowed JIRA projects, then skip it
        if not self.__belongs_to_allowed_project(linked_issue_key):
            self.log(
                "Skipping linked issue "
                + linked_issue_key
                + " - not traversing to blacklisted project"
            )
            return

        # skip the link if excluded via config
        if linked_issue_key in self.config["jira"]["issue_excludes"]:
            self.log("Skipping " + linked_issue_key + " - explicitly excluded")
            return

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

        # arrow = " => " if direction == "outward" else " <= "
        # self.log(issue_key + arrow + link_type + arrow + linked_issue_key)

        extra = ',fontname="{}"'.format(self.config["layout"]["defaults"]["fontName"])
        # FIXME to be configured
        if link_type == "blocks":
            extra += ",color=red"

        if direction not in self.config["jira"]["show_directions"]:
            # FIXME for the children case the linked_issue_key is needed from the caller of this method
            return
        else:
            # add the styled node without edge first, but only if it is not already there.
            # this happens if the issue is contained in the original query and re-appears now in a link
            if linked_issue_key not in self.added_issue_keys:
                self.graph.append(
                    self.__create_node_for_issue(
                        linked_issue_key,
                        linked_issue["fields"],
                        False,
                    )
                )
                self.added_issue_keys.append(linked_issue_key)

            # create the edge between the linked issue and the original one
            node = '{}->{}[label="{}"{}]'.format(
                # FIXME we already have that node created, have we?
                self.__create_node_for_issue(
                    issue_key,
                    issue_fields,
                    True,
                ),
                self.__create_node_for_issue(
                    linked_issue_key,
                    linked_issue["fields"],
                    True,
                ),
                link_type,
                extra,
            )
            self.graph.append(node)

    def __create_node_for_issue(self, issue_key, issue_fields, is_link):
        summary = issue_fields["summary"]

        if self.config["layout"]["defaults"]["wordWrap"]:
            if len(summary) > MAX_SUMMARY_LENGTH:
                # split the summary into multiple lines adding a \n to each line
                summary = textwrap.fill(summary, MAX_SUMMARY_LENGTH)
        else:
            # truncate long labels with "...", but only if the three dots are replacing more than two characters
            # -- otherwise the truncated label would be taking more space than the original.
            if len(summary) > MAX_SUMMARY_LENGTH + 2:
                summary = summary[:MAX_SUMMARY_LENGTH] + "..."
        summary = summary.replace('"', '\\"')

        if is_link:
            return '"{}\\n{}"'.format(issue_key, summary)

        return '"{}\\n{}" {}'.format(
            issue_key,
            summary,
            self.__get_styles_for_node(issue_key, issue_fields),
        )

    def __get_styles_for_node(self, issue_key, issue_fields):
        default_layout = self.__get_default_layout()
        layout = default_layout  # for all issue that match no rule

        if "overrides" in self.config:
            for rule_index in sorted(self.config["overrides"].keys()):
                if self.__does_issue_match_rule(
                    self.config["overrides"][rule_index], issue_key, issue_fields
                ):
                    layout = (
                        default_layout | self.config["overrides"][rule_index]["layout"]
                    )

        return '[fillcolor="{}",style="{}",fontname="{}"]'.format(
            layout["fillColor"],
            layout["boxStyle"],
            layout["fontName"],
        )

    def __does_issue_match_rule(self, rule, issue_key, issue_fields):
        match_count_expected = len(rule["matchRules"])
        match_count = 0
        for match_rule in rule["matchRules"]:
            if match_rule["type"] == "has_label":
                if match_rule["value"] in issue_fields["labels"]:
                    match_count += 1
            elif match_rule["type"] == "key_in":
                if issue_key in match_rule["value"]:
                    match_count += 1
            elif match_rule["type"] == "status_in":
                # self.log(issue_key + " - " + issue_fields["status"]["name"])
                if issue_fields["status"]["name"] in match_rule["value"]:
                    match_count += 1
            elif match_rule["type"] == "field_value":
                field_name = match_rule["value"]["field"]
                field_value = match_rule["value"]["value"]
                field_type = match_rule["value"]["field_type"]

                if field_name in issue_fields and issue_fields[field_name] is not None:
                    if field_type == "list":
                        # the field is a list, therefore get the values only
                        field_values = list(
                            map(lambda v: v["name"], issue_fields[field_name])
                        )
                        if field_value in field_values:
                            match_count += 1

        return match_count_expected == match_count

    def __get_default_layout(self):
        return dict(
            fillColor=self.config["layout"]["defaults"]["fillColor"],
            boxStyle=self.config["layout"]["defaults"]["boxStyle"],
            fontName=self.config["layout"]["defaults"]["fontName"],
        )

    def generate_graph(self, image_file_name, print_only=False, keep_dot_file=False):
        g = self.__generate()

        # FIXME this should be done based on JIRA data only, not on the formatted dot data
        # graph = filter_duplicates(graph)

        if print_only:
            print(
                "digraph{\nnode [shape="
                + self.config["layout"]["defaults"]["nodeShape"]
                + "];\n\n%s\n}" % ";\n".join(g)
            )
        else:
            self.__create_image(
                g,
                image_file_name,
                self.config["layout"]["defaults"]["nodeShape"],
                keep_dot_file,
            )


# FIXME be able to filter out linked issues based on JIRA fields or project
# FIXME be able to define multiple label rules for styling the boxes etc. with full set of customization (box color, border color, border thickness, fonts, font color etc.) with fallback to defaults
def main():
    config, options = ConfigAndOptions().get_config_and_options()

    jira = JiraSearch(config, options)

    # if a jql query was given, fetch all issues of it and add it to the issues list
    if options.jql_query is not None:
        options.issues.extend(jira.list_ids(options.jql_query))

    DotGenerator(config, options, jira).generate_graph(
        options.image_file_name, print_only=options.no_image
    )


if __name__ == "__main__":
    main()
