# Copyright 2016 Morgan McDermott

import unittest
import json
import os.path
import json
import time
import requests
import random
import pressurize.model.model_server as server

import boto3
import botocore

class TestModelServer(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        session = boto3.Session()
        client = session.client('s3')
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
        session = boto3.Session()
        client = session.client('s3')

        try:
            client.create_bucket(Bucket=bucket_name)
        except botocore.exceptions.ClientError as e:
            print("Bucket already exists %s" % e)

        test_model_dir = os.path.join("/".join(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        client.upload_file(os.path.join(test_model_dir, "parameters.txt"), bucket_name, "TestModel/parameters.txt")

    def test_run_server(self):
        test_model_dir = os.path.join("/".join(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        config = {}
        with open(os.path.join(test_model_dir, "pressurize.json")) as f:
            config = json.load(f)

        # Configure downloadable resources
        bucket_name = "testpressurize%s" % random.randint(0, 1000000000)
        resource_path = "s3://%s/TestModel/parameters.txt" % bucket_name
        config["models"][0]["required_resources"]["parameters"] = resource_path
        self.upload_test_parameters(bucket_name)

        process = server.run_server(config,
                          source_path=os.path.join(test_model_dir),
                          port='6043',
                          separate_process=True)
        print("About to sleep")
        time.sleep(1)
        print("Done sleeping")
        value = random.randint(0, 100000)

        # Perform prediction request
        url = "http://localhost:6043/api/TestModel/predict/"
        r = requests.post(url, json={"data": {"number": value}})
        self.assertEqual(200, r.status_code)
        j = r.json()

        # Result should be our randomly generated number + 1
        self.assertEqual(j['result']['number'], value + 1)

        # Result should also contain the parameter string "123"
        self.assertEqual(j['result']['parameters'].strip(), "123")

        # Terminate server process
        process.terminate()
        process.join()
        time.sleep(0.1)
        print(process.is_alive())
