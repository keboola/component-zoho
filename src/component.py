"""
Template Component main class.

"""
# import csv
import logging
from pathlib import Path

# from datetime import datetime
# import os

from keboola.component.base import ComponentBase
from keboola.component.exceptions import UserException

from zoho.authorization import initialize, set_filestore_file, get_filestore_file
from zoho.users import get_users

# configuration variables
KEY_API_TOKEN = "#api_token"
KEY_PRINT_HELLO = "print_hello"

# list of mandatory parameters => if some is missing,
# component will fail with readable message on initialization.
REQUIRED_PARAMETERS = [KEY_PRINT_HELLO]
REQUIRED_IMAGE_PARS = []


class Component(ComponentBase):
    """
    Extends base class for general Python components. Initializes the CommonInterface
    and performs configuration validation.

    For easier debugging the data folder is picked up by default from `../data` path,
    relative to working directory.

    If `debug` parameter is present in the `config.json`, the default logger is set to verbose DEBUG mode.
    """

    def __init__(self):
        super().__init__()

    def run(self):
        """
        Main execution code
        """

        # check for missing configuration parameters
        self.validate_configuration_parameters(REQUIRED_PARAMETERS)
        self.validate_image_parameters(REQUIRED_IMAGE_PARS)
        # params = self.configuration.parameters
        # Access parameters in data/config.json
        # if params.get(KEY_PRINT_HELLO):
        #     logging.info(params[KEY_PRINT_HELLO])

        # get last state data/in/state.json from previous run
        data_dir_path = Path(self.data_folder_path)
        tmp_dir_path = data_dir_path / "tmp_data"
        tmp_dir_path.mkdir(parents=True, exist_ok=True)
        self.token_store_path = tmp_dir_path / "token_store.csv"
        self.state = self.get_state_file()
        token_store_content = self.state.get("#token_store_content", "")
        set_filestore_file(self.token_store_path, token_store_content)

        initialize(tmp_dir_path=tmp_dir_path, file_store_path=self.token_store_path)
        self.save_state()
        get_users()
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
        token_store_content = get_filestore_file(self.token_store_path)
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
