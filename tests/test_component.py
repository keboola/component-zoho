"""
Created on 12. 11. 2018

@author: esner
"""
import json
import os
import tempfile
import unittest

import mock
from freezegun import freeze_time

from component import ZohoCRMExtractor


class TestComponent(unittest.TestCase):

    # set global time to 2010-10-10 - affects functions like datetime.now()
    @freeze_time("2010-10-10")
    # set KBC_DATADIR env to non-existing dir
    @mock.patch.dict(os.environ, {"KBC_DATADIR": "./non-existing-dir"})
    def test_run_no_cfg_fails(self):
        with self.assertRaises(ValueError):
            comp = ZohoCRMExtractor()
            comp.run()


class TestOutputTableName(unittest.TestCase):
    """Regression tests for output table name resolution in `_init_params`.

    Guards against the bug where a user-supplied `destination.output_table_name`
    was parsed but never assigned, so the extractor wrote everything to a table
    literally named `None`.
    """

    def _build_component(self, parameters: dict) -> ZohoCRMExtractor:
        """Instantiate the extractor against a throwaway datadir whose config.json
        carries the given parameters plus dummy OAuth credentials, so that
        `_init_params` runs end-to-end without any network setup."""
        datadir = tempfile.mkdtemp()
        os.makedirs(os.path.join(datadir, "in"), exist_ok=True)
        config = {
            "parameters": parameters,
            "authorization": {
                "oauth_api": {
                    "credentials": {
                        "appKey": "app-key",
                        "#appSecret": "app-secret",
                        "#data": json.dumps({"refresh_token": "refresh-token"}),
                    }
                }
            },
        }
        with open(os.path.join(datadir, "config.json"), "w", encoding="utf-8") as f:
            json.dump(config, f)

        with mock.patch.dict(os.environ, {"KBC_DATADIR": datadir}):
            return ZohoCRMExtractor()

    @staticmethod
    def _base_parameters() -> dict:
        return {
            "module_records_download_config": {"module_name": "Leads"},
            "sync_options": {"sync_mode": "full_sync"},
            "account": {"user_email": "user@example.com", "zoho_datacenter": "com"},
        }

    def test_custom_output_table_name_is_used(self):
        params = self._base_parameters()
        params["destination"] = {"output_table_name": "custom_leads", "load_mode": "full"}

        comp = self._build_component(params)
        comp._init_params()

        self.assertEqual("custom_leads", comp.output_table_name)

    def test_output_table_name_defaults_to_module_name(self):
        params = self._base_parameters()
        # no destination.output_table_name provided

        comp = self._build_component(params)
        comp._init_params()

        self.assertEqual("Leads", comp.output_table_name)


if __name__ == "__main__":
    # import sys;sys.argv = ['', 'Test.testName']
    unittest.main()
