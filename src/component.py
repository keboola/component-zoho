'''
Template Component main class.

'''

import logging
import logging_gelf.handlers
import logging_gelf.formatters
import sys
import os

from datetime import datetime, timedelta
import pytz
import json
import requests
import pandas as pd
import time  # noqa
from pandas.io.json import json_normalize

from kbc.env_handler import KBCEnvHandler
from kbc.result import KBCTableDef  # noqa
from kbc.result import ResultWriter  # noqa


# configuration variables
KEY_REGION = 'region'
KEY_REFRESH_TOKEN = '#refresh_token'
KEY_CLIENT_ID = 'client_id',
KEY_CLIENT_SECRET = '#client_secret'
KEY_LOAD_MODE = 'load_mode'

MANDATORY_PARS = [
    KEY_REGION,
    KEY_REFRESH_TOKEN,
    KEY_CLIENT_ID,
    KEY_CLIENT_SECRET,
    KEY_LOAD_MODE
]
MANDATORY_IMAGE_PARS = []

# Default Table Output Destination
DEFAULT_TABLE_SOURCE = "/data/in/tables/"
DEFAULT_TABLE_DESTINATION = "/data/out/tables/"
DEFAULT_FILE_DESTINATION = "/data/out/files/"
DEFAULT_FILE_SOURCE = "/data/in/files/"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)-8s : [line:%(lineno)3s] %(message)s',
    datefmt="%Y-%m-%d %H:%M:%S")

if 'KBC_LOGGER_ADDR' in os.environ and 'KBC_LOGGER_PORT' in os.environ:

    logger = logging.getLogger()
    logging_gelf_handler = logging_gelf.handlers.GELFTCPSocketHandler(
        host=os.getenv('KBC_LOGGER_ADDR'), port=int(os.getenv('KBC_LOGGER_PORT')))
    logging_gelf_handler.setFormatter(
        logging_gelf.formatters.GELFFormatter(null_character=True))
    logger.addHandler(logging_gelf_handler)

    # remove default logging to stdout
    logger.removeHandler(logger.handlers[0])

APP_VERSION = '0.0.1'


class Component(KBCEnvHandler):

    def __init__(self, debug=False):
        KBCEnvHandler.__init__(self, MANDATORY_PARS)
        """
        # override debug from config
        if self.cfg_params.get('debug'):
            debug = True
        else:
            debug = False

        self.set_default_logger('DEBUG' if debug else 'INFO')
        """
        logging.info('Running version %s', APP_VERSION)
        logging.info('Loading configuration...')

        try:
            self.validate_config()
            self.validate_image_parameters(MANDATORY_IMAGE_PARS)
        except ValueError as e:
            logging.error(e)
            exit(1)

    def exchangeToken(self):
        '''
        Function to exchange refresh token iwth a tempory access token
        '''

        parameters = {
            'refresh_toke': self.refresh_token,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'grant_type': 'refresh_token'
        }

        res = requests.post(
            '{}/oauth/v2/token'.format(self.region), params=parameters)
        res_json = res.json()

        return res_json['access_token']

    def column_validation(self, token, module, final_df):
        '''
        Function to validate if all the necessary columns exist in table.
        '''
        bearer_token = 'Zoho-oauthtoken ' + token
        parameters = {'module': module}
        headers = {'Authorization': bearer_token}

        req = requests.get(
            'https://www.zohoapis.eu/crm/v2/settings/fields', params=parameters, headers=headers)
        req_response = req.json()
        column_df = pd.DataFrame(json_normalize(req_response['fields']))

        checking_columns = column_df.loc[column_df['data_type']
                                         == 'lookup']['api_name']

        for i in checking_columns:
            if i in final_df.columns:
                if str(i) + '.id' not in final_df.columns:
                    final_df[str(i) + '_id'] = ''
                    final_df[str(i) + '_name'] = ''
            else:
                final_df[str(i)] = ''
                if str(i) + '.id' not in final_df.columns:
                    final_df[str(i) + '_id'] = ''
                    final_df[str(i) + '_name'] = ''

        if 'Recurring_Activity' in final_df.columns:
            if 'Recurring_Activity.RRULE' not in final_df.columns:
                final_df['Recurring_Activity_RRULE'] = ''
        else:
            final_df['Recurring_Activity'] = ''

        if 'Remind_At' in final_df.columns:
            if 'Remind_At.ALARM' not in final_df.columns:
                final_df['Remind_At_ALARM'] = ''
        else:
            final_df['Remind_At'] = ''

        return final_df

    def getRecords(self, token, module):
        '''
        Function on Data Extraction from Zoho's CRM
        '''

        lon_time = self.ex_time
        output_df = pd.DataFrame()
        pages = 1
        base_header = {
            'Authorization': 'Zoho-oauthtoken {}'.format(token)
        }

        while True:
            parameters = {'page': pages}
            if self.load_mode == 'incremental':
                base_header['If-Modified_Since'] = lon_time
            res = requests.get('{0}/crm/v2/{1}'.format(self.region,
                                                       module), params=parameters, headers=base_header)
            if res.status_code != 304:
                res_data = res.json()

                if res_data['info']['more_records'] == True:
                    final_df = final_df.append(
                        json_normalize(res_data['data']))
                else:
                    final_df = final_df.append(
                        json_normalize(res_data['data']))
                    final_df = self.column_validation(token, module, final_df)
                    return final_df

            else:
                tmp_header = {
                    'Authorization': 'Zoho-oauthtoken {}'.format(token)
                }
                res = requests.get('{0}/crm/v2/{1}'.format(self.region,
                                                           module), params=parameters, headers=tmp_header)
                res_data = res.json()
                final_df = final_df.append(
                    json_normalize(req_response['data']))
                final_df = final_df.iloc[0:0]
                final_df = self.column_validation(token, module, final_df)

            pages += 1

    def getRelatedRecords(self, KEY, module, ids, related_record):
        '''
        Functions on data extraction from ZOho's CRM relatedRecords endpoints
        '''

        bearer_token = 'Zoho-oauthtoken {}'.format(KEY)
        headers = {'Authorization': bearer_token}

        req = requests.get('{0}/crm/v2/{1}/{2}/{3}'.format(self.region,
                                                           module, ids, related_record), headers=headers)
        # Check if request contains any data
        if req.status_code != 204:

            if related_record == 'Contact_Roles':

                final_df = pd.DataFrame(columns=['Contact_id', 'Deal_id'])
                req_response = req.json()

                final_df['Contact_id'] = final_df['Contact_id'].append(
                    json_normalize(req_response['data'])['id'])
                final_df['Deal_id'] = ids

            elif related_record == 'Stage_History':

                final_df = pd.DataFrame()
                req_response = req.json()

                final_df = final_df.append(
                    json_normalize(req_response['data']))
                final_df['Deal_id'] = ids

            elif related_record == 'Contacts':

                final_df = pd.DataFrame(columns=['Contact_id', 'Campaign_id'])
                req_response = req.json()

                final_df['Contact_id'] = final_df['Contact_id'].append(
                    json_normalize(req_response['data'])['id'])
                final_df['Campaign_id'] = ids

            else:

                final_df = pd.DataFrame(columns=['Lead_id', 'Campaign_id'])
                req_response = req.json()

                final_df['Lead_id'] = final_df['Lead_id'].append(
                    json_normalize(req_response['data'])['id'])
                final_df['Campaign_id'] = ids
        else:

            final_df = pd.DataFrame()
            logging.info('No data contained!')

        # Check if API Rate Limit has been reached
        if req.headers['X-RATELIMIT-REMAINING'] == '0':
            logging.info('Rate Limit has been reached!! Wait for one minute.')
            time.sleep(60)

        return final_df

    def output_file(df, filename):
        '''
        Outputting files
        '''

        df.to_csv(DEFAULT_TABLE_DESTINATION +
                  '{}.csv'.format(filename), index=False)

    def run(self):
        '''
        Main execution code
        '''

        params = self.cfg_params  # noqa
        self.region = params.get(KEY_REGION)
        self.client_id = params.get(KEY_CLIENT_ID)
        self.client_secret = params.get(KEY_CLIENT_SECRET)
        self.refresh_token = params.get(KEY_REFRESH_TOKEN)
        self.load_mode = params.get(KEY_LOAD_MODE)

        endpoints = [
            'accounts',
            'contacts',
            'leads',
            'deals',
            'vendors',
            'campaigns',
            'calls',
            'events',
            'tasks'
        ]

        # Get Current Hour
        tz = pytz.timezone('Europe/London')
        london_now = datetime.now(tz) - timedelta(hours=2)
        self.ex_time = london_now.isoformat()

        if self.load_mode != 'full':
            logging.info('Extracting data from: ' + str(self.ex_time))

        logging.info(
            'Exchanging current refresh token with a temporary access token')
        KEY = self.exchangeToken(
            self.refresh_token, self.client_id, self.client_secret)

        # EXTRA DF to EXTRACT
        Deals_Contact_List = pd.DataFrame(columns=['Contact_id', 'Deal_id'])
        Deals_Stage_History = pd.DataFrame(columns=[
            'duration_days',
            'Amount',
            'Close_Date',
            'Expected_Revenue',
            'Last_Modified_Time',
            'Stage',
            'id',
            'modified_by_id',
            'modified_by_name',
            'probability',
            'Deal_id'])
        Campaigns_Contact_List = pd.DataFrame(
            columns=['Contact_id', 'Campaign_id'])
        Campaigns_Lead_List = pd.DataFrame(columns=['Lead_id', 'Campaign_id'])

        # Request to all the endpoints
        for endpoint in endpoints:
            logging.info('Extracting data on Zoho CRM {}'.format(endpoint))
            data_df = self.getRecords(KEY, endpoint)
            if data_df.empty:
                logging.info('No changes in {}'.format(endpoint))
            else:
                logging.info('{} data extracted'.format(endpoint))

            # DEALING WITH EXTRA ENDPOINTS
            if endpoint == 'campaigns' and not data_df.empty:
                for ids in data_df['id']:
                    # Extraction of Contacts that belong to a Deal.
                    temp_records_deals_contact = self.getRelatedRecords(
                        KEY, 'Deals', ids, 'Contact_Roles')
                    Deals_Contact_List = Deals_Contact_List.append(
                        temp_records_deals_contact, ignore_index=True)

                    # Extraction of Deals' Stage History
                    temp_records_stage_history = self.getRelatedRecords(
                        KEY, 'Deals', ids, 'Stage_History')
                    Deals_Stage_History = Deals_Stage_History.append(
                        temp_records_stage_history, ignore_index=True)

            if endpoint == 'deals' and not data_df.empty:
                for ids in data_df['id']:
                    # Extraction of Contacts that belong to a Campaign.
                    temp_records_campaigns_contacts = self.getRelatedRecords(
                        KEY, 'Campaigns', ids, 'Contacts')
                    Campaigns_Contact_List = Campaigns_Contact_List.append(
                        temp_records_campaigns_contacts, ignore_index=True)

                    # Extraction of Leads that belong to a Campaign.
                    temp_records_campaigns_leads = self.getRelatedRecords(
                        KEY, 'Campaigns', ids, 'Leads')
                    Campaigns_Lead_List = Campaigns_Lead_List.append(
                        temp_records_campaigns_leads, ignore_index=True)

        # SPECIAL ENDPOINTS
        Deals_Contact_List.to_csv(
            '/data/out/tables/deals_contact_list.csv', index=False)
        Deals_Stage_History.to_csv(
            '/data/out/tables/deals_stage_history.csv', index=False)
        Campaigns_Contact_List.to_csv(
            '/data/out/tables/campaigns_contact_list.csv', index=False)
        Campaigns_Lead_List.to_csv(
            '/data/out/tables/campaigns_lead_list.csv', index=False)

        logging.info("Extraction finished")


"""
        Main entrypoint
"""
if __name__ == "__main__":
    if len(sys.argv) > 1:
        debug = sys.argv[1]
    else:
        debug = True
    comp = Component(debug)
    comp.run()
