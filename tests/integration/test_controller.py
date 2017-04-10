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

    def test_controller(self):
        controller = Controller(self.config)
        controller.run()

        resources = ResourceManager(controller)
        cluster = resources.createResourceCluster()

    def test_deploy_api(self):
        controller = Controller(self.config)
        controller.create_resources()

    def test_deploy_models(self):
        controller = Controller(self.config)
        controller.create_resources()
        raise NotImplementedError

    def test_create_elastic_beanstalk_package(self):
        fn = create_elastic_beanstalk_package()
        zf = zipfile.ZipFile(fn)
        self.assertTrue(len(zf.infolist()) > 10)
        zf.close()

    def test_deploy_integration(self):
        controller = Controller(self.config)

        # Create cluster if needed
        perssurize.create_resources()

        # Deploy API
        controller.deploy_api()

        # Deploy Models
        controller.deploy_models()
