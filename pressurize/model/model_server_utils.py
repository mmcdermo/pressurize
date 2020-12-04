import logging
import logging.handlers

import random
import os.path
import json
import os
import importlib
import pkgutil

import boto3
import botocore


def import_model(path, source_path):
    """
    Imports a PressurizeModel given a pressurize.json model config path
    e.g.) given the path "TestModel.TestModel", imports:
          import TestModel from TestModel.TestModel
    """
    filepath = os.path.join(*path.split('.')) + '.py'
    fullpath = os.path.join(source_path, filepath)
    spec = importlib.util.spec_from_file_location(path, fullpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, path.split(".")[-1])

def acquire_resources(config, model, model_resource_path):
    resources = {}
    for resource_name in model['required_resources']:
        s3_path = model['required_resources'][resource_name]
        print("Downloading resource %s from %s" % (resource_name, s3_path))
        if not isinstance(s3_path, str):
            continue
        parts = s3_path.split("//")
        region = parts[1]

        if len(parts) < 3:
            raise RuntimeError("Invalid s3 resource in config: " + resource_name)

        session = boto3.Session(region_name=region)
        client = session.client('s3')

        if parts[0] != "s3:":
            resources[resource_name] = s3_path
            continue

        bucket = parts[2] # s3://{bucket}
        key = parts[3]

        print("PARTS", parts)
        print("BUCKET", bucket)
        print("KEY", key)
        #key = "/".join(parts[3:]) # s3://{bucket}/{key/with/slashes}

        # Ensure local folder exists
        local_folder = model_resource_path #os.path.join(model_resource_path, *parts[3:-1])

        print("local_folder", local_folder)
        if not os.path.exists(local_folder):
            print("Makedirs")
            os.makedirs(local_folder)

        local_path = os.path.join(model_resource_path, key.replace("/", "_"))
        print("local_path", local_path)
        try:
            client.download_file(bucket, key, local_path)
        except botocore.exceptions.ClientError as e:
            raise RuntimeError("Failed to download resource '%s' @ %s: %s" % \
                  (resource_name, s3_path, "bucket" + bucket + "key" + key + str(e)))
        resources[resource_name] = local_path
    print("Resources Acquired")
    return resources
