Zoho CRM Extractor
=============

Zoho CRM extractor using bulk read operations of v2 API.

**Table of contents:**

[TOC]

Functionality notes
===================
Extracts data about Zoho CRM modules using the [Bulk Read APIs](https://www.zoho.com/crm/developer/docs/api/v2/bulk-read/overview.html).

Supported endpoints
===================
- `crm/bulk/v2/read`
- `crm/bulk/v2/read/{job_id}`
- `crm/bulk/v2/read/{job_id}/result`

If you need more endpoints, please submit your request to
[ideas.keboola.com](https://ideas.keboola.com/)

Configuration
=============

 - Account's user email (user_email) - [REQ] User email you used to generate the Self Client.
 - Module records download configuration (module_records_download_config) - [REQ] job configuration
    - Module name (module_name) [REQ] - The API name of the Zoho CRM module you want to extract records from.
    - Field names (field_names) [OPT] - API names of the module records' fields you want to extract. Can be left empty or omitted to download all available fields.
 - Sync Options (sync_options) [REQ] - There are three modes available: Full Sync, Incremental Sync and Advanced, where you can set up custom filtering.
   - Filtering criteria (filtering_criteria) [OPT] - Filtering criteria enable you to filter the downloaded records using their fields' values. There is either a single filtering criterion or a filtering criteria group. Can be left empty or omitted to not apply any filtering.
       - Case of single filtering criterion:
           - Field name (field_name) [REQ] - The API name of the field you want to filter by.
           - Operator (operator) [REQ] - The operator you want to use to filter the field.
           - Value (value) [REQ] - The value you want to use to filter the field. Datetimes must always contain time zone information.
       - Case of filtering criteria group:
           - Group (group) [REQ] - List of simple filering criteria (see above).
           - Group operator (group_operator) [REQ] - The operator you want to use to combine the filtering criteria - either `and` or `or`.
 - Destination settings [REQ] - Is used to set Keboola Storage behaviour
     - Output table name (output_table_name) [OPT] - The name of the table that should be created or updated in Keboola Connection storage. Defaults to Module name.
     - Load mode (load_mode) [REQ] - If Full load is used, the destination table will be overwritten every run. If incremental load is used, data will be upserted into the destination table.

Sample Configurations
=============

Simple configuration
```json
{
  "parameters": {    
    "account": {
      "user_email": "component.factory@keboola.com"
    },
    "module_records_download_config": {
      "module_name": "Deals",
      "field_names": []
    },
    "sync_options": {
      "sync_mode": "full_sync",
      "filtering_criteria": {}
    },
    "destination": {
      "load_mode": "full",
      "output_table_name": "Leads"
    }
  }
}
```
Defined field names and filtering criteria
```json
{
  "parameters": {
    "account": {
      "user_email": "component.factory@keboola.com"
    },
    "module_records_download_config": {
      "module_name": "Leads",
      "field_names": []
    },
    "sync_options": {
      "sync_mode": "advanced",
      "filtering_criteria": {
        "field_name": "Created_Time",
        "comparator": "between",
        "value": [
          "2022-07-26T15:15:34+02:00",
          "2022-07-26T16:58:45+02:00"
        ]
      }
    },
    "destination": {
      "load_mode": "full",
      "output_table_name": "Leads"
    }
  }
}
```
Fitering Groups
```json
{
  "parameters": {
    "account": {
      "user_email": "component.factory@keboola.com"
    },
    "module_records_download_config": {
      "module_name": "Leads",
      "field_names": []
    },
    "sync_options": {
      "sync_mode": "advanced",
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
            "value": "Stary"
          }
        ],
        "group_operator": "or"
      }
    },
    "destination": {
      "load_mode": "full",
      "output_table_name": "LeadsTest"
    }
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