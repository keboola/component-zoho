"""
Zoho CRM Extractor component main module.

"""
import logging
from pathlib import Path
from typing import List, Optional
import os
import json

from keboola.component.base import ComponentBase, sync_action
from keboola.component.exceptions import UserException
from keboola.component.sync_actions import SelectElement

import zoho.initialization
import zoho.bulk_read

from zcrmsdk.src.com.zoho.crm.api.modules import ModulesOperations
from zcrmsdk.src.com.zoho.crm.api.fields import FieldsOperations
from zcrmsdk.src.com.zoho.crm.api import ParameterMap


# Configuration variables
KEY_GROUP_ACCOUNT = "account"
KEY_USER_EMAIL = "user_email"
KEY_GROUP_DESTINATION = "destination"
KEY_LOAD_MODE = "load_mode"
KEY_MODULE_RECORDS_DOWNLOAD_CONFIG = "module_records_download_config"

KEY_OUTPUT_TABLE_NAME = "output_table_name"
KEY_MODULE_NAME = "module_name"
KEY_FIELD_NAMES = "field_names"
KEY_FILTERING_CRITERIA = "filtering_criteria"

REQUIRED_PARAMETERS = [
    KEY_MODULE_RECORDS_DOWNLOAD_CONFIG,
]

# Other constants
REGION_CODE = "EU"
TMP_DATA_DIR_NAME = "tmp_data"
TOKEN_STORE_FILE_NAME = "token_store.csv"
ID_COLUMN_NAME = "Id"


class ZohoCRMExtractor(ComponentBase):

    def __init__(self):
        super().__init__()
        self.output_table_name = None
        self.incremental = None
        self.token_store_path = None

    def run(self):
        self.validate_configuration_parameters(REQUIRED_PARAMETERS)

        self._init_params()
        self._init_client()

        self.process_module_records_download_config(self.module_records_download_config)

    def process_module_records_download_config(self, config: dict):
        """
        Processes module records download config:
        asks Zoho API to prepare the data for download and then downloads the data as sliced CSV.
        Also creates appropriate manifest files.
        """
        module_name: str = config[KEY_MODULE_NAME]
        field_names: Optional[List[str]] = config.get(KEY_FIELD_NAMES)
        filtering_criteria_dict: Optional[dict] = config.get(KEY_FILTERING_CRITERIA)

        self.validate_filtering_criteria(filtering_criteria_dict)

        filtering_criteria = None
        if filtering_criteria_dict:
            key_comparator = filtering_criteria_dict.get(zoho.bulk_read.KEY_COMPARATOR)
            key_group = filtering_criteria_dict.get(zoho.bulk_read.KEY_GROUP)

            if key_comparator:
                filtering_criteria = zoho.bulk_read.BulkReadJobFilteringCriterion.from_dict(filtering_criteria_dict)
            elif key_group:
                filtering_criteria = zoho.bulk_read.BulkReadJobFilteringCriteriaGroup.from_dict(filtering_criteria_dict)

        table_def = self.create_out_table_definition(
            name=f"{self.output_table_name}.csv",
            incremental=self.incremental,
            primary_key=[ID_COLUMN_NAME],
            is_sliced=True,
        )

        os.makedirs(table_def.full_path, exist_ok=True)
        logging.info(f"Attempting to download data for output table {self.output_table_name}.")

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
            raise UserException("Failed to download data from Zoho API.\nReason:\n" + str(e)) from e

        table_def.columns = bulk_read_job.field_names
        self.write_manifest(table_def)

    @staticmethod
    def validate_filtering_criteria(criteria: dict):
        # TODO: implement proper validation
        allowed_keys = ["group", "field_name", "comparator", "value", "group_operator"]
        for key in criteria:
            if key not in allowed_keys:
                raise UserException(f"{key} is not a valid filter key.")

    @staticmethod
    def get_fields(module_api_name: str) -> list:
        fields_operations = FieldsOperations(module_api_name)
        param_instance = ParameterMap()

        r = fields_operations.get_fields(param_instance)

        if r.get_status_code() == 200:
            data = r.get_object()

            module_names = []
            for module in data._ResponseWrapper__fields:
                module_names.append(module._Field__api_name)
        else:
            raise UserException("Cannot fetch the list of available Modules.")

        return module_names

    @staticmethod
    def get_modules() -> list:
        modules_operations = ModulesOperations()

        r = modules_operations.get_modules()

        if r.get_status_code() == 200:
            data = r.get_object()

            module_names = []
            for module in data._ResponseWrapper__modules:
                module_names.append(module._Module__api_name)
        else:
            raise UserException("Cannot fetch the list of available Modules.")

        return module_names

    def _init_client(self):
        self.token_store_path = self.tmp_dir_path / TOKEN_STORE_FILE_NAME
        zoho.initialization.set_filestore_file(self.token_store_path, "")
        try:
            zoho.initialization.initialize(
                client_id=self.client_id,
                client_secret=self.client_secret,
                refresh_token=self.refresh_token,
                region_code=REGION_CODE,
                user_email=self.user_email,
                tmp_dir_path=self.tmp_dir_path,
                file_store_path=self.token_store_path,
            )
        except Exception as e:
            raise UserException("Zoho Python SDK initialization failed.\nReason:\n" + str(e)) from e

    def _init_params(self):
        params: dict = self.configuration.parameters

        self.output_table_name = params.get(KEY_GROUP_DESTINATION).get(KEY_OUTPUT_TABLE_NAME)

        oauth_credentials = self.configuration.oauth_credentials.data
        if not oauth_credentials:
            raise UserException("oAuth credentials are not available. Please authorize the extractor.")

        credentials = (self.configuration.config_data.get("authorization", {}).get("oauth_api", {})
                       .get("credentials", {}))
        credentials_data = json.loads(credentials.get("#data"))
        self.refresh_token = credentials_data.get("refresh_token")
        self.client_id = credentials.get("appKey")
        self.client_secret = credentials.get("#appSecret")

        self.user_email: str = params.get(KEY_GROUP_ACCOUNT, {}).get(KEY_USER_EMAIL)
        if not self.user_email:
            raise UserException("Parameter user_email is mandatory.")

        load_mode: str = params.get(KEY_GROUP_DESTINATION, {}).get(KEY_LOAD_MODE, "full_load")
        self.incremental: bool = load_mode == "incremental"

        self.module_records_download_config: dict = params[KEY_MODULE_RECORDS_DOWNLOAD_CONFIG]

        # Create directory for temporary data (Zoho SDK logging and token store)
        data_dir_path = Path(self.data_folder_path)
        self.tmp_dir_path = data_dir_path / TMP_DATA_DIR_NAME
        self.tmp_dir_path.mkdir(parents=True, exist_ok=True)

    @sync_action("listModules")
    def list_modules(self) -> List[SelectElement]:
        self._init_params()
        self._init_client()

        modules = self.get_modules()
        return [SelectElement(label=module, value=module) for module in modules]

    @sync_action("listFields")
    def list_fields(self) -> List[SelectElement]:
        self._init_params()
        self._init_client()

        module_name = self.module_records_download_config[KEY_MODULE_NAME]
        if not module_name:
            raise UserException("To list available fields, module_name parameter must be set.")

        modules = self.get_fields(module_name)
        return [SelectElement(label=module, value=module) for module in modules]


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
