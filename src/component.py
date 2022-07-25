"""
Template Component main class.

"""
# import csv
import logging
from pathlib import Path
from typing import Literal

# from datetime import datetime
# import os

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

import zoho.initialization
import zoho.users

# configuration variables
KEY_REGION_CODE = "region_code"
KEY_CLIENT_ID = "client_id"
KEY_CLIENT_SECRET = "#client_secret"
KEY_GRANT_TOKEN = "#grant_token"
KEY_USER_EMAIL = "user_email"
KEY_LOAD_MODE = "load_mode"

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [
    KEY_REGION_CODE,
    KEY_CLIENT_ID,
    KEY_CLIENT_SECRET,
    KEY_GRANT_TOKEN,
    KEY_USER_EMAIL,
    KEY_LOAD_MODE,
]
REQUIRED_IMAGE_PARS = []

# State variables
KEY_TOKEN_STORE_CONTENT = "#token_store_content"

# Other constants
TMP_DATA_DIR_NAME = "tmp_data"
TOKEN_STORE_FILE_NAME = "token_store.csv"


class Component(ComponentBase):
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
        self.validate_image_parameters(REQUIRED_IMAGE_PARS)
        params: dict = self.configuration.parameters
        # Access parameters in data/config.json
        region_code: str = params[KEY_REGION_CODE]
        client_id: str = params[KEY_CLIENT_ID]
        client_secret: str = params[KEY_CLIENT_SECRET]
        grant_token: str = params[KEY_GRANT_TOKEN]
        user_email: str = params[KEY_USER_EMAIL]
        load_mode: Literal["full", "incremental"] = params[KEY_LOAD_MODE]

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

        zoho.initialization.initialize(
            region_code=region_code,
            client_id=client_id,
            client_secret=client_secret,
            grant_token=grant_token,
            user_email=user_email,
            tmp_dir_path=tmp_dir_path,
            file_store_path=self.token_store_path,
        )
        self.save_state()  # TODO?: Probably just save at the end - this is only any useful in dev

        zoho.users.get_users()
        # ####### EXAMPLE TO REMOVE
        # # Create output table (Tabledefinition - just metadata)
        # table = self.create_out_table_definition(
        #     "output.csv", incremental=True, primary_key=["timestamp"]
        # )

        # # get file path of the table (data/out/tables/Features.csv)
        # out_table_path = table.full_path
        # logging.info(out_table_path)

        # os.makedirs(self.tables_out_path, exist_ok=True)
        # # DO whatever and save into out_table_path
        # with open(table.full_path, mode="wt", encoding="utf-8", newline="") as out_file:
        #     writer = csv.DictWriter(out_file, fieldnames=["timestamp"])
        #     writer.writeheader()
        #     writer.writerow({"timestamp": datetime.now().isoformat()})

        # # Save table manifest (output.csv.manifest) from the tabledefinition
        # self.write_manifest(table)

        # ####### EXAMPLE TO REMOVE END
        self.save_state()

    def save_state(self):
        """
        Save state to data/out/state.json
        """
        token_store_content = zoho.initialization.get_filestore_file(
            self.token_store_path
        )
        self.state["#token_store_content"] = token_store_content
        self.write_state_file(self.state)


"""
        Main entrypoint
"""
if __name__ == "__main__":
    try:
        comp = Component()
        # this triggers the run method by default and is controlled by the configuration.action parameter
        comp.execute_action()
    except UserException as exc:
        logging.exception(exc)
        exit(1)
    except Exception as exc:
        logging.exception(exc)
        exit(2)
