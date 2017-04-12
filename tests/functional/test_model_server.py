# Copyright 2016 Morgan McDermott

import unittest
import json
import os.path
import json
import time
import requests
import random
import pressurize.model.model_server as server

class TestModelServer(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_run_server(self):
        test_model_dir = os.path.join("/".join(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        config = {}
        with open(os.path.join(test_model_dir, "pressurize.json")) as f:
            config = json.load(f)
        process = server.run_server(config['models'],
                          source_path=os.path.join(test_model_dir, "models"),
                          port='6043',
                          separate_process=True)
        print("About to sleep")
        time.sleep(1)
        print("Done sleeping")
        value = random.randint(0, 100000)
        url = "http://localhost:6043/api/TestModel/predict/"
        #url =  "http://pressurizetest-TestModel.us-west-2.elasticbeanstalk.com/api/TestModel/predict/"
        r = requests.post(url, json={"data": {"number": value}})
        self.assertEqual(200, r.status_code)
        j = r.json()
        self.assertEqual(j['result']['number'], value + 1)
        process.terminate()
        process.join()
        time.sleep(0.1)
        print(process.is_alive())
