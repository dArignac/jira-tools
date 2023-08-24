import os
import requests

from jira_tools.logging import Logging


class JiraSearch(Logging):
    """This factory will create the actual method used to fetch issues from JIRA. This is really just a closure that
    saves us having to pass a bunch of parameters all over the place all the time."""

    __base_url = None
    __issues = {}

    def __init__(self, config: dict, options: dict):
        self.config = config
        self.options = options
        self.url = self.config["jira"]["url"] + "/rest/api/latest"
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
            + self.config["jira"]["additional_fields"]
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
        self.log("Querying " + query)
        response = self.get("/search", params={"jql": query, "fields": self.fields})
        content = response.json()
        return content["issues"]

    def list_ids(self, query):
        self.log("Querying " + query)
        response = self.get(
            "/search", params={"jql": query, "fields": "key", "maxResults": 100}
        )
        return [issue["key"] for issue in response.json()["issues"]]

    def get_issue_uri(self, issue_key):
        return self.__base_url + "/browse/" + issue_key
