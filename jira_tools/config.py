import argparse
import json


class ConfigAndOptions:
    def __load_config(self, config_file):
        with open(config_file) as config_file:
            return json.loads(config_file.read())

    # FIXME move to config file? at least the more complex ones
    def __parse_args(self):
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
        parser.add_argument(
            "--debug",
            action="store_true",
            dest="debug",
            default=False,
            help="if to output additional log messages.",
        )
        # FIXME review args from here
        # FIXME move to config file
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

    def get_config_and_options(self):
        """Returns the configuration and cli options."""
        options = self.__parse_args()

        # FIXME use json schema and have some docs
        config = self.__load_config(options.config_file)

        # map cli params into config
        config["jira"]["issue_excludes"] = options.issue_excludes
        config["jira"]["show_directions"] = options.show_directions

        # default configs
        if "ignored_statuses" not in config["jira"]:
            config["jira"]["ignored_statuses"] = []

        if "ignored_link_type_names" not in config["jira"]:
            config["jira"]["ignored_link_type_names"] = []

        # links config defaults
        if "links" not in config["jira"]:
            config["jira"]["links"] = {}
        if "ignored_statuses" not in config["jira"]["links"]:
            config["jira"]["links"]["ignored_statuses"] = []

        # layout config defaults
        layout_defaults = {
            "boxStyle": "filled",
            "fillColor": "white",
            "fontName": "Arial",
            "nodeShape": "box",
            "wordWrap": True,
        }

        if "layout" not in config:
            config["layout"] = {"defaults": layout_defaults}
        else:
            if "defaults" not in config["layout"]:
                config["layout"]["defaults"] = layout_defaults

            config["layout"]["defaults"] = {
                "boxStyle": "filled",
                "fillColor": "white",
                "fontName": "Arial",
                "nodeShape": "box",
                "wordWrap": True,
            } | config["layout"]["defaults"]

        return (config, options)
