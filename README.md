# jira-tools

This is some tooling to visualize and query JIRA. **Note that this is still work in progress.**

The graph dependency generation is based on [pawelrychlik/jira-dependency-graph](https://github.com/pawelrychlik/jira-dependency-graph), but I changed it according to my requirements.

## Prerequisites

* local graphviz installation for rendering the graph image
* Python 3.9+

## Usage

### Local setup

Fulfill the prerequisites above.

Clone repo and create a virtualenv:

```bash
$ git clone https://github.com/dicahe/jira-dependency-graph.git
$ virtualenv .env && source .env/bin/activate
$ cd jira-dependency-graph
$ pip install -r requirements.txt
```

### Authentication

To communicate with JIRA an access token with **read** permissions is required. The token has to be provided in the environment variable `JIRA_ACCESS_TOKEN`.

### Workflow

The primary query is either the JIRA ticket or the JQL you are giving. For the JQL case, all found tickets will be visualized, you can filter them through the configuration.

The term **link** is used for any ticket that is in relation to a ticket of the primary query.

### Configuration file

Each call requires a JSON config file, given with the `--config-file` option in the CLI call. Check the [`config_example.json`](./config_example.json) for a sample file.

The config is clustered into `jira`, `layout` and `rules`:

```
{
    "jira": {
        ...
    },
    "layout": {
        ...
    },
    "rules": {
        ...
    }
}
```

`layout` and `rules` are optional, the minimum required config is:

```
{
    "jira": {
        "url": "https://yourjira.com"
    }
}
```

#### `jira`
Handles JIRA specific configuration.

```
"jira": {
    "allowed_project_keys": [],
    "ignored_link_type_names": [
        "Blocks"
    ],
    "ignored_statuses": [
        "Closed"
    ],
    "links": {
        "ignored_statuses": [
            "Done"
        ]
    },
    "url": "https://yourjira.com"
}
```

* `additional_fields`:
  * list of JIRA fields to additionally query
  * this is only necessary if you use fields in the `field_value` matching rule of the overrides (see below) and if this fields are not included in the default JIRA query (which fetches the fields `key`, `summary`, `status`, `description`, `issuetype`, `issuelinks`,`subtasks`, `labels`)
* `allowed_project_keys`
  * list of allowed JIRA project keys
  * any found issue (either in JQL query or in linked issue of the given issue or JQL) that does not match the list is ignored
  * if empty, then all JIRA projects are allowed
* `ignored_link_type_names`
  * in the links of an issue, links matching the **name** of the type of link are ignored
* `ignored_statuses`
  * if any found issue, that is not a link, matches the list of ignored statuses, then the issue is ignored
* `links` - handling of the links of an issue (links are found in the result list based on the given ticket or JQL)
  * `ignored_statuses`
    * links whose status match any of the given statuses are ignored
* `url` to JIRA instance
  * **mandatory**

#### `layout`

Defines the basic layout of the drawn issues. Can be overwritten by the `rules` section.

```
"layout": {
    "defaults": {
        "boxStyle": "filled,dashed",
        "fillColor": "white",
        "fontName": "Arial",
        "wordWrap": true
    },
    "legend": "Updated: {0} UTC"
},
```

* `defaults` default layout - applies if not overwritten by the `rules`
  * `boxStyle` (`string`) style of the drawn boxes, `dot` notation, also see [`style docs of dot`](https://graphviz.org/docs/attrs/style/)
  * `fillColor` (`string`) fill color of the box, find possible color values [here](https://graphviz.org/doc/info/colors.html)
  * `fontName` (`string`) name of the font, according to `dot`, see [here](https://graphviz.org/docs/attrs/fontname/)
  * `nodeShape` (`string`) which shape to use for the nodes (`circle`, `box`, `ellipse`, etc.) - default: `box`
  * `wordWrap` (`boolean`) if to break the summary of an issue over multiple lines (`true`) or if to cut off after 30 characters ( `false`)
* `legend` a legend that is rendered under the graph
  * you can use the placeholder `{0}` to insert the generation time of the graph, e.g. `Updated: {0} UTC`

#### `overrides`

Rules can override the layout of an issue (default is `layout`.`defaults`). They are based on `matchRules`, where all single rules have to match to apply the override.

Each rule needs to have a numeric key in the `overrides` object, as they are iterated in order. Rules are evaluated and applied in order (starting with `0`), means that later rules can overwrite previous ones.

```
"overrides": {
    "0": {
        "matchRules": [
            {
                "type": "label",
                "value": "demo-label"
            }
        ],
        "layout": {
            "boxStyle": "filled,dashed",
            "fillColor": "orange"
        }
    },
    "1": {
        "matchRules": [
            {
                "type": "label",
                "value": "another-label"
            }
        ],
        "layout": {
            "boxStyle": "dashed",
            "fillColor": "yellow"
        }
    }
}
```

Rule definition:

* `matchRules` (`list`) list of specific rules, that need to be matched to have the overall rule to match
  * a rule is an `object` with
    * `type` defines the type of match, possible values
      * `has_label`
        * checks if the issue has a label as given in `value`
      * `key_in`
        * checks if the issue's key matches any of the issue keys given in `value` (`list` of `string`)
      * `status_in`
        * check if the status matches the given status value list in `value` (`list` of `string`)
      * `field_value`
        * checks if a particular field has a value
        * the implementation separates between the different types of values, as there can be single or multiple values for a field
        * the `value` has to be an object with the following keys
          * `field` - name of the field to compare
          * `value` - the value to match
          * `field_type` - what kind the field is, currently only supported is `list` for a field that can have a list of values
* `layout` (`object`) to define the layout which will be used instead of the default layout
  * same keys as in `layout`.`defaults` can be defined

### CLI commands

Query a single ticket:

```bash
$ python jira-dependency-graph.py --jira=<JIRA_URL> --config-file config_example.json --file output.png issue-key 
```

Query a JQL query:

```bash
$ python jira-dependency-graph.py --jira=<JIRA_URL> --config-file config_example.json --jql 'project = DEMO-123 and labels = test-label' --file output.png
```

#### CLI Parameters

* `--file-name` - file name to write the generated image to, **without file extension**
  * default: `output` (will result in `output.png` file)
* `--no-image` - instead of generating the graph image, outputs the dot source code for the graph
