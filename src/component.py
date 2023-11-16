"""
Zoho CRM Extractor component main module.

"""
import logging
from pathlib import Path
from typing import List, Literal, Optional
import os
import json

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

import zoho.initialization
import zoho.bulk_read

# Configuration variables
KEY_GROUP_ACCOUNT = "account"
KEY_USER_EMAIL = "user_email"
KEY_LOAD_MODE = "load_mode"
KEY_MODULE_RECORDS_DOWNLOAD_CONFIG = "module_records_download_config"

# Module records download configs keys
KEY_OUTPUT_TABLE_NAME = "output_table_name"
KEY_MODULE_NAME = "module_name"
KEY_FIELD_NAMES = "field_names"
KEY_FILTERING_CRITERIA = "filtering_criteria"

REQUIRED_PARAMETERS = [
    KEY_MODULE_RECORDS_DOWNLOAD_CONFIG,
]

# State variables
KEY_TOKEN_STORE_CONTENT = "#token_store_content"

# Other constants
REGION_CODE = "EU"
TMP_DATA_DIR_NAME = "tmp_data"
TOKEN_STORE_FILE_NAME = "token_store.csv"
ID_COLUMN_NAME = "Id"


class ZohoCRMExtractor(ComponentBase):

    def __init__(self):
        super().__init__()
        self.incremental = None
        self.token_store_path = None
        self.state = None

    def run(self):

        self.validate_configuration_parameters(REQUIRED_PARAMETERS)
        params: dict = self.configuration.parameters

        oauth_credentials = self.configuration.oauth_credentials.data
        if not oauth_credentials:
            raise UserException("oAuth credentials are not available. Please authorize the extractor.")

        credentials = (self.configuration.config_data.get("authorization", {}).get("oauth_api", {})
                       .get("credentials", {}))
        credentials_data = json.loads(credentials.get("#data"))
        refresh_token = credentials_data.get("refresh_token")
        client_id = credentials.get("appKey")
        client_secret = credentials.get("#appSecret")

        user_email: str = params.get(KEY_GROUP_ACCOUNT, {}).get(KEY_USER_EMAIL)
        load_mode: Literal["full", "incremental"] = params[KEY_LOAD_MODE]
        module_records_download_config: dict = params[
            KEY_MODULE_RECORDS_DOWNLOAD_CONFIG
        ]

        self.incremental: bool = load_mode == "incremental"

        # Create directory for temporary data (Zoho SDK logging and token store)
        data_dir_path = Path(self.data_folder_path)
        tmp_dir_path = data_dir_path / TMP_DATA_DIR_NAME
        tmp_dir_path.mkdir(parents=True, exist_ok=True)
        self.token_store_path = tmp_dir_path / TOKEN_STORE_FILE_NAME

        # get last state data/in/state.json from previous run
        self.state = self.get_state_file()
        token_store_content: str = self.state.get(KEY_TOKEN_STORE_CONTENT, "")
        zoho.initialization.set_filestore_file(
            self.token_store_path, token_store_content
        )

        try:
            zoho.initialization.initialize(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                region_code=REGION_CODE,
                user_email=user_email,
                tmp_dir_path=tmp_dir_path,
                file_store_path=self.token_store_path,
            )
        except Exception as e:
            raise UserException(
                "Zoho Python SDK initialization failed.\nReason:\n" + str(e)
            ) from e
        finally:
            self.save_state()  # TODO?: Probably just save at the end - this is only any useful in dev

        self.process_module_records_download_config(module_records_download_config)

    def save_state(self):
        """
        Save state to data/out/state.json
        """
        token_store_content = zoho.initialization.get_filestore_file(
            self.token_store_path
        )
        self.state["#token_store_content"] = token_store_content
        self.write_state_file(self.state)

    def get_schema(self):
        """
        Returns JSON schema for the component configuration.
        """
        schema_path = (
                Path(__file__).parent.parent / "component_config" / "configSchema.json"
        )
        with open(schema_path, "r") as schema_file:
            schema = json.load(schema_file)
        return schema

    def process_module_records_download_config(self, config: dict):
        """
        Processes module records download config:
        asks Zoho API to prepare the data for download and then downloads the data as sliced CSV.
        Also creates appropriate manifest files.
        """
        output_table_name: str = config[KEY_OUTPUT_TABLE_NAME]
        module_name: str = config[KEY_MODULE_NAME]
        field_names: Optional[List[str]] = config.get(KEY_FIELD_NAMES)
        filtering_criteria_dict: Optional[dict] = config.get(KEY_FILTERING_CRITERIA)

        if filtering_criteria_dict:
            if filtering_criteria_dict.get(zoho.bulk_read.KEY_COMPARATOR):
                filtering_criteria = (
                    zoho.bulk_read.BulkReadJobFilteringCriterion.from_dict(
                        filtering_criteria_dict
                    )
                )
            elif filtering_criteria_dict.get(zoho.bulk_read.KEY_GROUP):
                filtering_criteria = (
                    zoho.bulk_read.BulkReadJobFilteringCriteriaGroup.from_dict(
                        filtering_criteria_dict
                    )
                )
            else:
                filtering_criteria = None
        else:
            filtering_criteria = None

        table_def = self.create_out_table_definition(
            name=f"{output_table_name}.csv",
            incremental=self.incremental,
            primary_key=[ID_COLUMN_NAME],
            is_sliced=True,
        )

        os.makedirs(table_def.full_path, exist_ok=True)
        logging.info(
            f"Attempting to download data for output table {output_table_name}."
        )

        print(module_name, field_names, filtering_criteria)

        try:
            bulk_read_job = zoho.bulk_read.BulkReadJobBatch(
                module_api_name=module_name,
                destination_folder=table_def.full_path,
                file_name=table_def.name,
                field_names=field_names,
                filtering_criteria=filtering_criteria,
            )
            bulk_read_job.download_all_pages()
        except Exception as e:
            raise UserException(
                "Failed to download data from Zoho API.\nReason:\n" + str(e)
            ) from e
        finally:
            self.save_state()

        table_def.columns = bulk_read_job.field_names
        self.write_manifest(table_def)


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = ZohoCRMExtractor()
        # this triggers the run method by default and is controlled by the configuration.action parameter
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
