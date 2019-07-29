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
    session = boto3.Session(region_name=config['aws_region'])
    client = session.client('s3')

    resources = {}
    for resource_name in model['required_resources']:
        s3_path = model['required_resources'][resource_name]
        print("Downloading resource %s from %s" % (resource_name, s3_path))
        if not isinstance(s3_path, str):
            continue
        parts = s3_path.split("/")
        if len(parts) < 4:
            raise RuntimeError("Invalid s3 resource in config: " + resource_name)
        if parts[0] != "s3:":
            resources[resource_name] = s3_path
            continue

        bucket = parts[2] # s3://{bucket}
        key = "/".join(parts[3:]) # s3://{bucket}/{key/with/slashes}

        # Ensure local folder exists
        local_folder = model_resource_path
        if len(parts) != 4:
            local_folder = os.path.join(local_folder, *parts[3:-1])
        if not os.path.exists(local_folder):
            os.makedirs(local_folder)

        local_path = os.path.join(model_resource_path, *parts[3:])
        try:
            client.download_file(bucket, key, local_path)
        except botocore.exceptions.ClientError as e:
            raise RuntimeError("Failed to download resource '%s' @ %s: %s" % \
                               (resource_name, s3_path, str(e)))
        resources[resource_name] = local_path
    return resources
