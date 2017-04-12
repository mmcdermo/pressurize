# Copyright 2016 Morgan McDermott & Blake Allen

import unittest
import json
import time
import os.path
import random
import zipfile
import os
from pressurize.Controller import Controller
from pressurize.ResourceManager import ResourceManager

class TestController(unittest.TestCase):
    def setUp(self):
        self.config = {
            "deployment_name": "pressurize_test",
            "aws_region": "us-west-2",
            "models": [
	        {
                    "path": "TestModel.TestModel",
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

    def test_create_elastic_beanstalk_package(self):
        controller = Controller(self.config)
        source_path = "/" + os.path.join(*(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        fn = controller.create_model_package(source_path, "TestModel")
        zf = zipfile.ZipFile(fn)
        self.assertTrue(len(zf.infolist()) > 10)
        zf.close()

    def test_deploy_model_env(self):
        controller = Controller(self.config)
        source_path = "/" + os.path.join(*(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        #controller.destroy_model_cluster("TestModel")
        controller.deploy_model(source_path, "TestModel")

    def test_deploy_integration(self):
        return
        controller = Controller(self.config)

        # Create cluster if needed
        perssurize.create_resources()

        # Deploy API
        controller.deploy_api()

        # Deploy Models
        controller.deploy_models()
