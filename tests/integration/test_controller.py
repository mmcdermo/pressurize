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

import boto3
import botocore

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
	            "required_resources": {
		        "parameters": "s3://testbucket/TestModel/parameters.txt"
	            }
	        }
            ]
        }

    def tearDown(self):
        session = boto3.Session(profile_name="testing")
        client = session.client('s3')
        return #
        self.cleanup_buckets(client, "pressurizetest")

    @staticmethod
    def cleanup_buckets(client, search_string):
        for bucket in client.list_buckets()['Buckets']:
            if search_string in bucket['Name']:
                print("Deleting test bucket: %s" % bucket['Name'])
                listed = client.list_objects_v2(Bucket=bucket['Name'])
                if 'Contents' in listed:
                    objs = listed['Contents']
                    response = client.delete_objects(
                        Bucket=bucket['Name'],
                        Delete={'Objects': [{"Key": x["Key"]} for x in objs]})
                client.delete_bucket(Bucket=bucket['Name'])

    def upload_test_parameters(self, bucket_name):
        session = boto3.Session(profile_name="testing")
        client = session.client('s3')

        try:
            client.create_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            print("Bucket already exists %s" % e)

        test_model_dir = os.path.join("/".join(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        client.upload_file(os.path.join(test_model_dir, "parameters.txt"), bucket_name, "TestModel/parameters.txt")

    def test_create_model_elastic_beanstalk_package(self):
        controller = Controller(self.config)
        source_path = "/" + os.path.join(*(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        fn = controller.create_model_package(source_path, "TestModel")
        zf = zipfile.ZipFile(fn)
        self.assertTrue(len(zf.infolist()) > 10)
        zf.close()

    def test_create_api_elastic_beanstalk_package(self):
        controller = Controller(self.config)
        fn = controller.create_api_package()
        zf = zipfile.ZipFile(fn)
        self.assertTrue(len(zf.infolist()) > 5)
        zf.close()

    def test_deploy_model_env(self):
        bucket_name = "pressurizetest%s" % random.randint(0, 1000000)
        resource_path = "s3://%s/TestModel/parameters.txt" % bucket_name
        self.config["models"][0]["required_resources"]["parameters"] = resource_path
        self.upload_test_parameters(bucket_name)

        controller = Controller(self.config)
        source_path = "/" + os.path.join(*(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))

        controller.deploy_model(source_path, "TestModel")

    def test_deploy_api_env(self):
        controller = Controller(self.config)
        controller.deploy_api()

    def test_run_local(self):
        conf = self.config
        conf["models"][0]["required_resources"] = {}
        print(json.dumps(conf, indent=4))
        controller = Controller(conf)
        source_path = "/" + os.path.join(*__file__.split("/")[:-2] + ["test_data", "test_model_server"])
        controller.run_local("TestModel", source_path=source_path, port='6789')

    def test_deploy_integration(self):
        return
        controller = Controller(self.config)

        # Create cluster if needed
        pressurize.create_resources()

        # Deploy API
        controller.deploy_api()

        # Deploy Models
        controller.deploy_models()
