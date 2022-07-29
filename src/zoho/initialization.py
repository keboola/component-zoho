from pathlib import Path
from typing import Literal

from zcrmsdk.src.com.zoho.crm.api.user_signature import UserSignature
from zcrmsdk.src.com.zoho.crm.api.dc import (
    EUDataCenter,
    USDataCenter,
    CNDataCenter,
    INDataCenter,
    AUDataCenter,
    JPDataCenter,
    DataCenter,
)
from zcrmsdk.src.com.zoho.api.authenticator.store import FileStore
from zcrmsdk.src.com.zoho.api.logger import Logger
from zcrmsdk.src.com.zoho.crm.api.initializer import Initializer
from zcrmsdk.src.com.zoho.api.authenticator.oauth_token import OAuthToken
from zcrmsdk.src.com.zoho.crm.api.sdk_config import SDKConfig


def code_to_dc(code: str) -> DataCenter:
    if code == "EU":
        return EUDataCenter.PRODUCTION()
    elif code == "US":
        return USDataCenter.PRODUCTION()
    elif code == "CN":
        return CNDataCenter.PRODUCTION()
    elif code == "IN":
        return INDataCenter.PRODUCTION()
    elif code == "AU":
        return AUDataCenter.PRODUCTION()
    elif code == "JP":
        return JPDataCenter.PRODUCTION()
    else:
        raise ValueError(
            "Invalid data center code, must be one of EU, US, CN, IN, AU, JP."
        )


def set_filestore_file(file_store_path: Path, content: str):
    file_store_path.write_text(content)


def get_filestore_file(file_store_path: Path):
    return file_store_path.read_text()


def initialize(
    region_code: Literal["EU", "US", "CN", "IN", "AU", "JP"],
    client_id: str,
    client_secret: str,
    grant_token: str,
    user_email: str,
    tmp_dir_path: Path,
    file_store_path: Path,
):

    """
    Create an instance of Logger Class that takes two parameters
    1 -> Level of the log messages to be logged.
         Can be configured by typing Logger.Levels "." and choose any level from the list displayed.
    2 -> Absolute file path, where messages need to be logged.
    """
    logger = Logger.get_instance(
        level=Logger.Levels.INFO,
        file_path=str(tmp_dir_path / "ZohoCRMSDK.log"),
    )

    # Create an UserSignature instance that takes user Email as parameter
    user = UserSignature(email=user_email)

    """
        Configure the environment
        which is of the pattern Domain.Environment
        Available Domains: USDataCenter, EUDataCenter, INDataCenter, CNDataCenter, AUDataCenter
        Available Environments: PRODUCTION(), DEVELOPER(), SANDBOX()
        """
    environment = code_to_dc(region_code)

    """
        Create a Token instance that takes the following parameters
        1 -> OAuth client id.
        2 -> OAuth client secret.
        3 -> Grant token.
        4 -> Refresh token.
        5 ->> OAuth redirect URL.
        6 ->> id
        """
    token = OAuthToken(
        client_id=client_id,
        client_secret=client_secret,
        grant_token=grant_token,
    )

    """
        Create an instance of TokenStore
        1 -> Absolute file path of the file to persist tokens
        """
    # Create file if it doesn't exist
    store = FileStore(file_path=str(file_store_path))

    """
        auto_refresh_fields (Default value is False)
            if True - all the modules' fields will be auto-refreshed in the background, every hour.
            if False - the fields will not be auto-refreshed in the background. The user can manually
                       delete the file(s) or refresh the fields using methods
                       from ModuleFieldsHandler(zcrmsdk/src/com/zoho/crm/api/util/module_fields_handler.py)

        pick_list_validation (Default value is True)
        A boolean field that validates user input for a pick list field and allows or
        disallows the addition of a new value to the list.
            if True - the SDK validates the input. If the value does not exist in the pick list,
                      the SDK throws an error.
            if False - the SDK does not validate the input and makes the API request
                       with the user’s input to the pick list

        connect_timeout (Default value is None)
            A  Float field to set connect timeout

        read_timeout (Default value is None)
            A  Float field to set read timeout
        """
    config = SDKConfig(
        auto_refresh_fields=True,
        pick_list_validation=False,
        connect_timeout=None,
        read_timeout=None,
    )

    """
        The path containing the absolute directory path (in the key resource_path)
        to store user-specific files containing information about fields in modules.
        """
    resource_path = str(tmp_dir_path)

    """
        Call the static initialize method of Initializer class that takes the following arguments
        1 -> UserSignature instance
        2 -> Environment instance
        3 -> Token instance
        4 -> TokenStore instance
        5 -> SDKConfig instance
        6 -> resource_path
        7 -> Logger instance. Default value is None
        8 -> RequestProxy instance. Default value is None
        """
    Initializer.initialize(
        user=user,
        environment=environment,
        token=token,
        store=store,
        sdk_config=config,
        resource_path=resource_path,
        logger=logger,
    )
