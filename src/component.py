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
import jsonschema

import zoho.initialization
import zoho.users
import zoho.bulk_read

# Configuration variables
KEY_REGION_CODE = "region_code"
KEY_CLIENT_ID = "client_id"
KEY_CLIENT_SECRET = "#client_secret"
KEY_GRANT_TOKEN = "#grant_token"
KEY_USER_EMAIL = "user_email"
KEY_LOAD_MODE = "load_mode"
KEY_MODULE_RECORDS_DOWNLOAD_CONFIGS = "module_records_download_configs"

# Module records download configs keys
KEY_OUTPUT_TABLE_NAME = "output_table_name"
KEY_MODULE_NAME = "module_name"
KEY_FIELD_NAMES = "field_names"
KEY_FILTERING_CRITERION = "filtering_criterion"

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [
    KEY_REGION_CODE,
    KEY_CLIENT_ID,
    KEY_CLIENT_SECRET,
    KEY_GRANT_TOKEN,
    KEY_USER_EMAIL,
    KEY_LOAD_MODE,
    KEY_MODULE_RECORDS_DOWNLOAD_CONFIGS,
]
REQUIRED_IMAGE_PARS = []

# State variables
KEY_TOKEN_STORE_CONTENT = "#token_store_content"

# Other constants
TMP_DATA_DIR_NAME = "tmp_data"
TOKEN_STORE_FILE_NAME = "token_store.csv"
ID_COLUMN_NAME = "Id"


class ZohoCRMExtractor(ComponentBase):
    """
    Extends base class for general Python components. Initializes the CommonInterface
    and performs configuration validation.

    For easier debugging the data folder is picked up by default from `../data` path,
    relative to working directory.

    If `debug` parameter is present in the `config.json`, the default logger is set to verbose DEBUG mode.
    """

    # def __init__(self):
    #     super().__init__()

    def run(self):
        """
        Main execution code
        """

        # check for missing configuration parameters
        self.validate_configuration_parameters(REQUIRED_PARAMETERS)
        try:
            jsonschema.validate(self.configuration.parameters, self.get_schema())
        except jsonschema.ValidationError as e:
            raise UserException(
                f"Configuration validation error: {e.message}."
                f" Please make sure provided configuration is valid."
            ) from e
        self.validate_image_parameters(REQUIRED_IMAGE_PARS)
        params: dict = self.configuration.parameters
        # Access parameters in data/config.json
        region_code: str = params[KEY_REGION_CODE]
        client_id: str = params[KEY_CLIENT_ID]
        client_secret: str = params[KEY_CLIENT_SECRET]
        grant_token: str = params[KEY_GRANT_TOKEN]
        user_email: str = params[KEY_USER_EMAIL]
        load_mode: Literal["full", "incremental"] = params[KEY_LOAD_MODE]
        module_records_download_configs: List[dict] = params[
            KEY_MODULE_RECORDS_DOWNLOAD_CONFIGS
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
                region_code=region_code,
                client_id=client_id,
                client_secret=client_secret,
                grant_token=grant_token,
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

        for config in module_records_download_configs:
            self.process_module_records_download_config(config)

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
        output_table_name: str = config[KEY_OUTPUT_TABLE_NAME]
        module_name: str = config[KEY_MODULE_NAME]
        field_names: Optional[List[str]] = config.get(KEY_FIELD_NAMES)
        filtering_criterion: Optional[dict] = config.get(KEY_FILTERING_CRITERION)

        table_def = self.create_out_table_definition(
            name=f"{output_table_name}.csv",
            incremental=self.incremental,
            primary_key=[ID_COLUMN_NAME],
            is_sliced=True,
        )
        os.makedirs(table_def.full_path, exist_ok=True)
        try:
            bulk_read_job = zoho.bulk_read.BulkReadJobBatch(
                module_api_name=module_name,
                destination_folder=table_def.full_path,
                file_name=table_def.name,
                field_names=field_names,
                filtering_criterion=filtering_criterion,
            )
            bulk_read_job.download_all_pages()
            table_def.columns = bulk_read_job.field_names
            self.write_manifest(table_def)
        except Exception as e:
            raise UserException(
                "Failed to download data from Zoho API.\nReason:\n" + str(e)
            ) from e
        finally:
            self.save_state()


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
