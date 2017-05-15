# Copyright 2017 Morgan McDermott

import unittest
import json
import os.path
import json
import time
import requests
import random
import math
from pressurize.Controller import Controller

class TestDeployComponents(unittest.TestCase):
    def setUp(self):
        self.config = {
            "deployment_name": "pressurize_test",
            "aws_region": "us-west-2",
            "api_instance_type": "t2.small",
            "models": [
	        {
                    "path": "TestModel.TestModel",
                    "required_ecu": 2,
                    "required_memory": 8,
	            "name": "TestModel",
	            "methods": ["predict"],
	            "required_resources": [
		        "s3://testbucket/TestModel/parameters.zip"
	            ]
	        }
            ]
        }

    def tearDown(self):
        pass

    def test_instance_type(self):
        controller = Controller(self.config)
        for x in range(100):
            mem = random.randint(1, 20)
            ecu = random.randint(1, 15)
            instance_type = controller._resource_manager.determine_instance_type(ecu, mem)
            self.assertTrue(instance_type['memory'] > mem)
            self.assertTrue(instance_type['ecu'] > ecu)
            self.assertTrue(instance_type['ecu'] - ecu < 20)
            self.assertTrue(instance_type['memory'] - mem < 30)

    def create_model_cluster(self):
        controller = Controller(self.config)
        try:
            cluster = controller._resource_manager.create_model_cluster("somefile.zip", "ModelDNE")
            raise RuntimeError("Should fail to create model cluster for non existent model")
        except Exception as e:
            pass

        cluster = controller._resource_manager.create_model_cluster("somefile.zip", "TestModel")

    def create_api_cluster(self):
        controller = Controller(self.config)
        cluster = controller._resource_manager.create_api_cluster("somefile.zip")
