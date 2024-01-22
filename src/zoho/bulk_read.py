import csv
from dataclasses import dataclass
import os
from time import sleep
import zipfile
import logging
from typing import List, Literal, Optional, Union

import dateparser

from zcrmsdk.src.com.zoho.crm.api.bulk_read import (
    BulkReadOperations,
    RequestWrapper,
    ResponseWrapper,
    # CallBack,
    Query,
    Criteria,
    ActionWrapper,
    SuccessResponse,
    APIException,
    JobDetail,
    FileBodyWrapper
)

from zcrmsdk.src.com.zoho.crm.api.util import Choice
from zcrmsdk.src.com.zoho.crm.api.util import APIResponse

# Module records download configs simple filtering criteria keys
KEY_FIELD_NAME = "field_name"
KEY_COMPARATOR = "comparator"
KEY_VALUE = "value"
KEY_PARSE_VALUE_AS_DATETIME = "parse_value_as_datetime"

# Module records download configs simple filtering criteria keys
KEY_GROUP = "group"
KEY_GROUP_OPERATOR = "group_operator"

# Other constants
POLLING_PERIOD_SECONDS = 8


def print_criteria(criteria: Criteria):  # TODO: change to str generating function
    if criteria.get_api_name() is not None:
        # Get the API Name of the Criteria
        logging.debug("BulkRead Criteria API Name: " + criteria.get_api_name())

    if criteria.get_comparator() is not None:
        # Get the Comparator of the Criteria
        logging.debug(
            "BulkRead Criteria Comparator: " + criteria.get_comparator().get_value()
        )

    if criteria.get_value() is not None:
        # Get the Value of the Criteria
        logging.debug("BulkRead Criteria Value: " + str(criteria.get_value()))

    # Get the List of Criteria instance of each Criteria
    criteria_group = criteria.get_group()

    if criteria_group is not None:
        for each_criteria in criteria_group:
            print_criteria(each_criteria)

    if criteria.get_group_operator() is not None:
        # Get the Group Operator of the Criteria
        logging.debug(
            "BulkRead Criteria Group Operator: "
            + criteria.get_group_operator().get_value()
        )


def handle_api_exception(api_exception: APIException):
    # Get the Status
    logging.debug("Status: " + api_exception.get_status().get_value())

    # Get the Code
    logging.debug("Code: " + api_exception.get_code().get_value())

    logging.debug("Details")

    # Get the details dict
    details = api_exception.get_details()

    details_string = ""
    for key, value in details.items():
        msg = " " + key + ": " + str(value)
        details_string = details_string + "\n" + msg
    logging.debug(details_string)

    # Get the Message
    logging.debug("Message: " + api_exception.get_message().get_value())

    # Raise an exception
    raise RuntimeError(
        f"API did not accept the request to get details of a bulk read job.\n"
        f"Status: {api_exception.get_status().get_value()}\n"
        f"Code: {api_exception.get_code().get_value()}\n"
        f"Message: {api_exception.get_message().get_value()}\n"
        f"Details: {details_string}"
    )


@dataclass(slots=True, frozen=True)
class BulkReadJobFilteringCriterion:
    field_name: str
    comparator: Literal[
        "equal",
        "not_equal",
        "in",
        "not_in",
        "between",
        "not_between",
        "greater_than",
        "greater_equal",
        "less_than",
        "less_equal",
    ]
    value: Union[str, List[str]]

    @classmethod
    def from_dict(cls, dict: dict):
        def parse(value):
            return dateparser.parse(value).isoformat(timespec="seconds")

        if dict.get(KEY_PARSE_VALUE_AS_DATETIME):
            value: Union[str, List[str]] = (
                parse(dict[KEY_VALUE])
                if isinstance(dict[KEY_VALUE], str)
                else [parse(v) for v in dict[KEY_VALUE]]
            )
        else:
            value: Union[str, List[str]] = dict[KEY_VALUE]

        return cls(
            field_name=dict[KEY_FIELD_NAME],
            comparator=dict[KEY_COMPARATOR],
            value=value,
        )


@dataclass(slots=True, frozen=True)
class BulkReadJobFilteringCriteriaGroup:
    group: List[BulkReadJobFilteringCriterion]
    group_operator: Literal["and", "or"]

    @classmethod
    def from_dict(cls, dict: dict):
        return cls(
            group=[
                BulkReadJobFilteringCriterion.from_dict(criterion)
                for criterion in dict[KEY_GROUP]
            ],
            group_operator=dict[KEY_GROUP_OPERATOR],
        )


def create_query_criteria_object(
    filtering_criteria: Union[
        BulkReadJobFilteringCriterion, BulkReadJobFilteringCriteriaGroup
    ]
) -> Criteria:
    if isinstance(filtering_criteria, BulkReadJobFilteringCriterion):
        # Get instance of Criteria Class
        criteria = Criteria()

        # To set API name of a field
        criteria.set_api_name(filtering_criteria.field_name)

        # To set comparator(eg: equal, greater_than)
        criteria.set_comparator(Choice(filtering_criteria.comparator))

        value: Union[str, List[str]] = filtering_criteria.value

        # To set the value to be compared
        criteria.set_value(value)

        return criteria
    elif isinstance(filtering_criteria, BulkReadJobFilteringCriteriaGroup):
        # Get instance of Criteria Class
        criteria = Criteria()

        # To set the group operator(i.e.: and, or)
        criteria.set_group_operator(Choice(filtering_criteria.group_operator))

        # To set the list of Criteria instances
        criteria.set_group(
            [
                create_query_criteria_object(filtering_criterion)
                for filtering_criterion in filtering_criteria.group
            ]
        )

        return criteria
    else:
        raise ValueError(
            "Argument filtering_criteria must be an instance of"
            " BulkReadJobFilteringCriterion or BulkReadJobFilteringCriteriaGroup."
        )


@dataclass(slots=True)
class BulkReadJobBatch:
    module_api_name: str
    destination_folder: str
    file_name: str
    field_names: Optional[List[str]] = None
    filtering_criteria: Optional[
        Union[BulkReadJobFilteringCriterion, BulkReadJobFilteringCriteriaGroup]
    ] = None
    _current_page: int = 1
    _current_job_id: Optional[int] = None
    _current_job_state: Optional[
        Literal["ADDED", "QUEUED", "IN PROGRESS", "COMPLETED"]
    ] = None
    _more_pages: bool = True

    def download_all_pages(self):  # TODO: Add support for parallel downloads of pages
        while self._more_pages:
            self.create()
            logging.info(f"Created a bulk read job for page {self._current_page}.")
            self.get_details()
            while self._current_job_state != "COMPLETED":  # TODO: Add a timeout
                logging.info(
                    f"Page {self._current_page} not ready yet. Its current job state: {self._current_job_state}."
                    f" Waiting {POLLING_PERIOD_SECONDS} seconds for API server to prepare it."
                )
                sleep(POLLING_PERIOD_SECONDS)
                self.get_details()
            logging.info(f"Page {self._current_page} ready. Downloading.")
            self.download_result()
            self._current_page += 1

    def create(self):
        # Get instance of BulkReadOperations Class
        bulk_read_operations = BulkReadOperations()

        # Get instance of RequestWrapper Class that will contain the request body
        request = RequestWrapper()

        # Get instance of Query Class
        query = Query()

        # Specifies the API Name of the module to be read.
        query.set_module(self.module_api_name)

        # Specifies the API Name of the fields to be fetched
        if self.field_names:
            query.set_fields(self.field_names)

        # To set page value, By default value is 1.
        query.set_page(self._current_page)

        if self.filtering_criteria:
            criteria = create_query_criteria_object(self.filtering_criteria)
            # To filter the records to be exported
            query.set_criteria(criteria)

        # Set the query object
        request.set_query(query)

        # Specify the value for this key as "ics" to export all records in the Events module as an ICS file.
        request.set_file_type(Choice("csv"))

        # Call create_bulk_read_job method that takes RequestWrapper instance as parameter
        response: APIResponse = bulk_read_operations.create_bulk_read_job(request)

        if response is None:
            raise RuntimeError(
                "Got no response from API when attempting to create a bulk read job."
            )

        # Get the status code from response
        logging.debug("Status Code: " + str(response.get_status_code()))

        # Get object from response
        response_object = response.get_object()

        if response_object is None:
            raise RuntimeError(
                "Got no or empty response object from API when attempting to create a bulk read job."
            )

        # Check if expected ActionWrapper instance is received.
        if isinstance(response_object, ActionWrapper):
            action_response_list = response_object.get_data()
            for action_response in action_response_list:
                # Check if the request is successful
                if isinstance(action_response, SuccessResponse):
                    # Get the Status
                    logging.debug("Status: " + action_response.get_status().get_value())

                    # Get the Code
                    logging.debug("Code: " + action_response.get_code().get_value())

                    logging.debug("Details")

                    # Get the details dict
                    details = action_response.get_details()

                    for key, value in details.items():
                        logging.debug(key + " : " + str(value))

                    self._current_job_id = details["id"]

                    # Get the Message
                    logging.debug(
                        "Message: " + action_response.get_message().get_value()
                    )

                # Check if the request returned an exception
                elif isinstance(action_response, APIException):
                    # Get the Status
                    logging.debug("Status: " + action_response.get_status().get_value())

                    # Get the Code
                    logging.debug("Code: " + action_response.get_code().get_value())

                    logging.debug("Details")

                    # Get the details dict
                    details = action_response.get_details()

                    for key, value in details.items():
                        logging.debug(key + " : " + str(value))

                    # Get the Message
                    logging.debug(
                        "Message: " + action_response.get_message().get_value()
                    )

        # Check if the request returned an exception
        elif isinstance(response_object, APIException):
            handle_api_exception(response_object)

    def get_details(self):
        # Get instance of BulkReadOperations Class
        bulk_read_operations = BulkReadOperations()

        # Call get_bulk_read_job_details method that takes jobId as parameter
        response: APIResponse = bulk_read_operations.get_bulk_read_job_details(
            self._current_job_id
        )
        if response is None:
            raise RuntimeError(
                "Got no response from API when attempting to get details of a bulk read job."
            )

        # Get the status code from response
        logging.debug("Status Code: " + str(response.get_status_code()))

        # Get object from response
        response_object = response.get_object()

        if response_object is None:
            raise RuntimeError(
                "Got no or empty response object from API when attempting to get details of a bulk read job."
            )

        # Check if expected ResponseWrapper instance is received
        if isinstance(response_object, ResponseWrapper):

            # Get the list of JobDetail instances
            job_details_list: List[JobDetail] = response_object.get_data()

            for job_detail in job_details_list:
                # Get the Job ID of each jobDetail
                logging.debug("Bulk read Job ID: " + str(job_detail.get_id()))

                # Get the Operation of each jobDetail
                logging.debug("Bulk read Operation: " + job_detail.get_operation())

                # Get the State of each jobDetail
                logging.debug("Bulk read State: " + job_detail.get_state().get_value())
                self._current_job_state = job_detail.get_state().get_value()

                # Get the Result instance of each jobDetail
                result = job_detail.get_result()

                if result is not None:
                    # Get the Page of the Result
                    logging.debug("Bulkread Result Page: " + str(result.get_page()))

                    # Get the Count of the Result
                    logging.debug("Bulkread Result Count: " + str(result.get_count()))

                    # Get the Download URL of the Result
                    logging.debug(
                        "Bulkread Result Download URL: " + result.get_download_url()
                    )

                    # Get the Per_Page of the Result
                    logging.debug(
                        "Bulkread Result Per_Page: " + str(result.get_per_page())
                    )

                    # Get the MoreRecords of the Result
                    logging.debug(
                        "Bulkread Result MoreRecords: " + str(result.get_more_records())
                    )
                    self._more_pages = result.get_more_records()

                # Get the Query instance of each jobDetail
                query = job_detail.get_query()

                if query is not None:
                    # Get the Module Name of the Query
                    logging.debug("Bulk read Query Module: " + query.get_module())

                    # Get the Page of the Query
                    logging.debug("Bulk read Query Page: " + str(query.get_page()))

                    # Get the cvid of the Query
                    logging.debug("Bulk read Query cvid: " + str(query.get_cvid()))

                    # Get the fields List of the Query
                    fields = query.get_fields()

                    if fields is not None:
                        logging.debug("Bulk read fields")
                        for field in fields:
                            logging.debug(field)

                    # Get the Criteria instance of the Query
                    criteria = query.get_criteria()

                    if criteria is not None:
                        print_criteria(criteria)

                    # Get the CreatedBy User instance of each jobDetail
                    created_by = job_detail.get_created_by()

                    # Check if created_by is not None
                    if created_by is not None:
                        # Get the Name of the created_by User
                        logging.debug(
                            "Bulkread Created By - Name: " + created_by.get_name()
                        )

                        # Get the ID of the created_by User
                        logging.debug(
                            "Bulkread Created By - ID: " + str(created_by.get_id())
                        )

                    # Get the CreatedTime of each jobDetail
                    logging.debug(
                        "Bulkread CreatedTime: " + str(job_detail.get_created_time())
                    )

                    # Get the FileType of each jobDetail
                    logging.debug("Bulkread File Type: " + job_detail.get_file_type())

        # Check if the request returned an exception
        elif isinstance(response_object, APIException):
            handle_api_exception(response_object)

    def download_result(self):
        # Get instance of BulkReadOperations Class
        bulk_read_operations = BulkReadOperations()

        # Call download_result method that takes job_id as parameter
        response: APIResponse = bulk_read_operations.download_result(
            self._current_job_id
        )

        if response is None:
            raise RuntimeError(
                "Got no response from API when attempting to download a bulk read job result."
            )

        # Get the status code from response
        logging.debug("Status Code: " + str(response.get_status_code()))

        # Get object from response
        response_object = response.get_object()

        if response_object is None:
            raise RuntimeError(
                "Got no or empty response object from API when attempting to get details of a bulk read job."
            )

        # Check if expected FileBodyWrapper instance is received.
        if isinstance(response_object, FileBodyWrapper):

            # Get StreamWrapper instance from the returned FileBodyWrapper instance
            stream_wrapper = response_object.get_file()

            # Construct the file name by joining the destinationFolder and the name from StreamWrapper instance
            zip_file_name = os.path.join(
                self.destination_folder, stream_wrapper.get_name()
            )

            # Open the destination file where the file needs to be written in 'wb' mode
            with open(zip_file_name, "wb") as f:
                # Get the stream from StreamWrapper instance
                for chunk in stream_wrapper.get_stream():
                    f.write(chunk)

            with zipfile.ZipFile(zip_file_name, "r") as zip_ref:
                zip_ref.extractall(self.destination_folder)
                csv_file_name = os.path.join(
                    self.destination_folder, zip_ref.filelist[0].filename
                )
            os.remove(zip_file_name)

            # Update field names according to the CSV file and remove header
            temp_csv_file_name = csv_file_name + "_temp"
            with open(csv_file_name, "r") as csv_file, open(
                temp_csv_file_name, "w"
            ) as csv_file_temp:
                csv_reader = csv.reader(csv_file)
                field_names = next(csv_reader)
                csv_writer = csv.writer(csv_file_temp)
                for row in csv_reader:
                    csv_writer.writerow(row)
            self.field_names = field_names
            os.remove(csv_file_name)
            os.rename(temp_csv_file_name, csv_file_name)

        # Check if the request returned an exception
        elif isinstance(response_object, APIException):
            handle_api_exception(response_object)
