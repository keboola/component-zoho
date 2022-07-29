Zoho CRM Extractor
=============

Zoho CRM extractor using bulk read operations of v2 API.

**Table of contents:**

[TOC]

Functionality notes
===================
Extracts data about Zoho CRM modules using the [Bulk Read APIs](https://www.zoho.com/crm/developer/docs/api/v2/bulk-read/overview.html).

Prerequisites
=============
You must log into the the Zoho API console of your regional Zoho data center and register a new Self Client to obtain the needed credentials. You must then generate a grant token there with scope of at least `ZohoCRM.modules.READ,ZohoCRM.bulk.READ`. See [the offical documentation](https://www.zoho.com/crm/developer/docs/api/v2/auth-request.html#self-client) for details.


Supported endpoints
===================
- `crm/bulk/v2/read`
- `crm/bulk/v2/read/{job_id}`
- `crm/bulk/v2/read/{job_id}/result`

If you need more endpoints, please submit your request to
[ideas.keboola.com](https://ideas.keboola.com/)

Configuration
=============
 - Zoho account region code (region_code) - [REQ] Region code of your Zoho CRM data center.
 - Account's client ID (client_id) - [REQ] Client ID of the Self Client you registered using the Zoho API console.
 - Account's client secret (#client_secret) - [REQ] Client secret of the Self Client you registered using the Zoho API console.
 - Account's grant token (#grant_token) - [REQ] Grant token you generated for the Self Client you registered using the Zoho API console.
 - Account's user email (user_email) - [REQ] User email you used to generate the Self Client.
 - Load mode (load_mode) - [REQ] Keboola Connection table load mode.
 - Module records download configurations (module_records_download_configs) - [REQ] List of configurations for the records download job batches.
    - Output table name (output_table_name) [REQ] - The name of the table that should be created or updated in Keboola Connection storage.
    - Module name (module_name) [REQ] - The API name of the Zoho CRM module you want to extract records from.
    - Field names (field_names) [OPT] - API names of the module records' fields you want to extract. Can be left empty or omitted to download all available fields.
    - Filtering criteria (filtering_criteria) [OPT] - Filtering criteria enable you to filter the downloaded records using their fields' values. There is either a single filtering criterion or a filtering criteria group. Can be left empty or omitted to not apply any filtering.
        - Case of single filtering criterion:
            - Field name (field_name) [REQ] - The API name of the field you want to filter by.
            - Operator (operator) [REQ] - The operator you want to use to filter the field.
            - Value (value) [REQ] - The value you want to use to filter the field. Datetimes must always contain time zone information.
            - Parse value as datetime (parse_value_as_datetime) [OPT] - If set to `true`, the value will be parsed as datetime using the [dateparser library](https://dateparser.readthedocs.io/en/latest/). Datetimes must always contain time zone information.
        - Case of filtering criteria group:
            - Group (group) [REQ] - List of simple filering criteria (see above).
            - Group operator (group_operator) [REQ] - The operator you want to use to combine the filtering criteria - either `and` or `or`.


Sample Configuration
=============
```json
{
    "parameters": {
        "region_code": "EU",
        "client_id": "1000.SECRET_VALUE",
        "#client_secret": "SECRET_VALUE",
        "#grant_token": "SECRET_VALUE",
        "user_email": "john.smith@example.com",
        "load_mode": "incremental",
        "module_records_download_configs": [
            {
                "output_table_name": "Leads1",
                "module_name": "Leads"
            },
            {
                "output_table_name": "Leads2",
                "module_name": "Leads",
                "field_names": [
                    "Owner",
                    "Company",
                    "First_Name",
                    "Last_Name",
                    "Full_Name",
                    "Designation"
                ]
            },
            {
                "output_table_name": "Leads3",
                "module_name": "Leads",
                "filtering_criteria": {
                    "field_name": "Created_Time",
                    "comparator": "not_between",
                    "value": [
                        "2022-07-26T15:15:34+02:00",
                        "2022-07-26T16:58:45+02:00"
                    ]
                }
            },
            {
                "output_table_name": "Leads4",
                "module_name": "Leads",
                "filtering_criteria": {
                    "field_name": "Created_Time",
                    "comparator": "between",
                    "value": [
                        "2022-07-26T15:15:34+02:00",
                        "2022-07-26T16:58:45+02:00"
                    ]
                }
            },
            {
                "output_table_name": "Leads5",
                "module_name": "Leads",
                "filtering_criteria": {
                    "group": [
                        {
                            "field_name": "Created_Time",
                            "comparator": "greater_equal",
                            "value": "2022-07-26T15:15:34+02:00"
                        },
                        {
                            "field_name": "Created_Time",
                            "comparator": "less_equal",
                            "value": "2022-07-26T16:58:45+02:00"
                        }
                    ],
                    "group_operator": "or"
                }
            },
            {
                "output_table_name": "Leads6",
                "module_name": "Leads",
                "filtering_criteria": {
                    "group": [
                        {
                            "field_name": "First_Name",
                            "comparator": "equal",
                            "value": "Jan"
                        },
                        {
                            "field_name": "Last_Name",
                            "comparator": "equal",
                            "value": "Starý"
                        }
                    ],
                    "group_operator": "or"
                }
            },
            {
                "output_table_name": "Leads7",
                "module_name": "Leads",
                "filtering_criteria": {
                    "field_name": "Created_Time",
                    "comparator": "less_equal",
                    "value": "3 days ago CEST",
                    "parse_value_as_datetime": true
                }
            },
            {
                "output_table_name": "Leads8",
                "module_name": "Leads",
                "filtering_criteria": {
                    "field_name": "Created_Time",
                    "comparator": "between",
                    "value": [
                        "3 days ago CEST",
                        "2 days ago PST"
                    ],
                    "parse_value_as_datetime": true
                }
            }
        ]
    }
}
```

Output
======
All output tables contain the `Id` column containing the record's unique ID. It is always used as the output tables primary key in Keboola Connection storage. Other fields depend on the module you are extracting records from and field names specified in the configuration.

Development
-----------

If required, change local data folder (the `CUSTOM_FOLDER` placeholder) path to your custom path in
the `docker-compose.yml` file:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    volumes:
      - ./:/code
      - ./CUSTOM_FOLDER:/data
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Clone this repository, init the workspace and run the component with following command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose build
docker-compose run --rm dev
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Run the test suite and lint check using this command:

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
docker-compose run --rm test
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integration
===========

For information about deployment and integration with KBC, please refer to the
[deployment section of developers documentation](https://developers.keboola.com/extend/component/deployment/)