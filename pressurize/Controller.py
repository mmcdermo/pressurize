# Copyright 2016 Morgan McDermott & Blake Allen
"""

The Controller class coordinates the creation of API and Model
elastic beanstalk environments

"""
import os
import os.path
import json
import time
import datetime
import hashlib
import string
from zipfile import ZipFile
from threading import Thread
import importlib.util
import shutil
import random
import botocore
import subprocess

from redleader.managers import ElasticBeanstalkManager

import pressurize.ResourceManager as ResourceManager
import pressurize.AWSManager as AWSManager


class Controller(object):
    def __init__(self, config, aws_profile=None):
        self._defaults = {
        }
        self.validate_config(config)
        self.config = config
        self.local_queues = {}

        # Create map of models for efficient lookup
        self.models = {}
        for model in self.config['models']:
            self.models[model['name']] = model

        for key in self._defaults:
            if key not in config:
                setattr(self, key, self._defaults[key])

        self._aws_profile = aws_profile
        self._aws_manager = AWSManager.AWSManager(aws_profile=aws_profile)
        self._resource_manager = ResourceManager.ResourceManager(self)

    def create_resources(self, force_update=False):
        try:
            if force_update:
                self._cluster.blocking_delete(verbose=True)
            self._cluster.blocking_deploy(verbose=True)
        except Exception as e:
            if "AlreadyExists" not in "%s" % e:
                raise e
            else:
                print("Stack already exists %s" % e)

    def validate_config(self, config):
        required_keys = ['deployment_name', 'aws_region', 'models']
        accepted_keys = required_keys + ['api_min_size', 'api_max_size',
                                         'api_instance_type', 'custom_parameters']
        for key in required_keys:
            if key not in config:
                raise Exception('Config must have key %s' % key)
        for key in config:
            if key not in accepted_keys:
                raise Exception('Invalid key %s in top level config' % key)
        for model in config['models']:
            self.validate_model(model)

    def validate_model(self, model):
        required_keys = ['name', 'path', 'methods']
        for key in required_keys:
            if key not in model:
                raise Exception('Model %s config must have key %s' %
                                (model.get('name', 'unnamed'), key))
        accepted_keys = required_keys + ['min_size', 'max_size', 'instance_type',
                                         'required_memory', 'required_ecu',
                                         'required_resources', 'storage_gb',
                                         'custom_parameters'
        ]
        for key in model:
            if key not in accepted_keys:
                raise Exception('Invalid key %s in model %s config' %
                                (key, model['name']))


    def recursively_add_files_to_zip(self, source_path, zipfile, base=""):
        for filename in os.listdir(source_path):
            f = os.path.join(source_path, filename)
            if os.path.islink(f):
                continue
            if filename[0] == "." or ".zip" in filename:
                continue
            elif os.path.isdir(f):
                self.recursively_add_files_to_zip(f, zipfile,
                                                  os.path.join(base, filename))
            else:
                zipfile.write(f, os.path.join(base, filename))

    def custom_config(self, model_name):
        """
        Returns a copy of the current config, excluding all models
        except the given one. Used for deployment to individual model servers.
        """
        new_config = {}
        for k in self.config:
            new_config[k] = self.config[k]
        new_config['models'] = list(filter(lambda x: x['name'] == model_name, new_config['models']))
        return new_config

    def create_api_package(self):
        """
        Creates a zip package deployable to elastic beanstalk for the pressurize API
        """
        template_dir = "/" + os.path.join(*(__file__.split("/")[:-1] + ["api"]))
        filename = "deploy_api.zip"
        target = os.path.join(os.getcwd(), filename)
        try:
            os.remove(target)
        except FileNotFoundError:
            pass

        with ZipFile(target, 'w') as zipfile:
            self.recursively_add_files_to_zip(template_dir, zipfile)

            # Write the custom config for this particular model server
            tmpfile = '/tmp/custom_api_config.json'
            with open(tmpfile, 'w') as f:
                json.dump(self.config, f)
            zipfile.write(tmpfile, 'pressurize.json')
        return filename

    def create_model_package(self, source_path, model_name):
        """
        Creates a zip package deployable to elastic beanstalk for the given model
        """
        template_dir = "/" + os.path.join(*(__file__.split("/")[:-1] + ["model", "deploy_template"]))
        filename = "deploy_model_%s.zip" % model_name
        target = os.path.join(os.getcwd(), filename)
        try:
            os.remove(target)
        except FileNotFoundError:
            pass

        with ZipFile(target, 'w') as zipfile:
            self.recursively_add_files_to_zip(template_dir, zipfile)
            self.recursively_add_files_to_zip(source_path, zipfile)

            # Write the custom config for this particular model server
            custom_config = self.custom_config(model_name)
            tmpfile = '/tmp/custom_config.json'
            with open(tmpfile, 'w') as f:
                json.dump(custom_config, f)
            zipfile.write(tmpfile, 'pressurize.json')
        return filename

    def run_local(self, model_name, source_path=None, port='5000', docker=True):
        source_path = source_path or os.getcwd()

        local_path = os.path.join("/tmp/", "pressurize_local_"+model_name+str(random.randint(0, 10000)))
        print("Local Run: Creating temp deployment ", local_path)

        template_dir = "/" + os.path.join(*(__file__.split("/")[:-1] + ["model", "deploy_template"]))
        copytree(template_dir, local_path)
        copytree(source_path, local_path)
        os.chmod(os.path.join(local_path, "pressurize.json"), 777)
        os.remove(os.path.join(local_path, "pressurize.json"))

        custom_config = self.custom_config(model_name)
        with open(os.path.join(local_path, "pressurize.json"), 'w') as f:
            json.dump(custom_config, f)

        # Load as module if docker is false
        if docker == False:
            print("Loading model as module")
            spec = importlib.util.spec_from_file_location("server", os.path.join(local_path, "server.py"))
            server = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(server)
            server.main(port=port)
            return

        # Copy AWS Credentials
        print("Loading model in docker container")
        print("Expanded user", os.path.expanduser("~"))
        shutil.copy2(os.path.join(os.path.expanduser("~"), ".aws/credentials"),
                     os.path.join(local_path, "credentials"))

        # Run the docker build script
        cmd = " ".join(["/".join(__file__.split("/")[:-1] + ["model", "run_local.sh"]),
                                       local_path,
                                       model_name.lower(),
                                       str(port)])
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                  stderr=subprocess.STDOUT, shell=True)
        for line in p.stdout:
            print(line.decode('utf-8').replace("\n", ""))

    def deploy_api(self, dry_run=False):
        """
        Deploys an elastic beanstalk environment for the pressurize API
        """
        packagefile = self.create_api_package()
        print("Created API elastic beanstalk package ", packagefile)
        bucket_name = self._resource_manager.elastic_beanstalk_bucket()
        manager = ElasticBeanstalkManager(self._aws_manager)
        manager.upload_package(bucket_name, os.path.join(os.getcwd(), packagefile), packagefile)
        cluster = self._resource_manager.create_api_cluster(packagefile)
        if dry_run:
            return cluster.cloud_formation_template()
        try:
            cluster.blocking_deploy(verbose=True)
        except botocore.exceptions.ClientError as e:
            if "exists" in "%s" % e:
                print("Cluster already exists. Updating")
                cluster.blocking_update(verbose=True)
            else:
                raise e

    def deploy_model(self, source_path, model_name, blocking=True, dry_run=False):
        """
        Deploys an elastic beanstalk environment for the given model
        """
        packagefile = self.create_model_package(source_path, model_name)
        print("Created model elastic beanstalk package ", source_path, packagefile)
        bucket_name = self._resource_manager.elastic_beanstalk_bucket()
        manager = ElasticBeanstalkManager(self._aws_manager)
        manager.upload_package(bucket_name, os.path.join(os.getcwd(), packagefile), packagefile)
        cluster = self._resource_manager.create_model_cluster(packagefile, model_name)
        if dry_run:
            return cluster.cloud_formation_template()
        try:
            if blocking:
                cluster.blocking_deploy()
            else:
                cluster.deploy()
        except botocore.exceptions.ClientError as e:
            if "exists" in "%s" % e:
                print("Cluster already exists. Updating")
                if blocking:
                    cluster.blocking_update(verbose=True)
                else:
                    cluster.update()
            else:
                raise e

    def deploy_models(self, source_path=None, dry_run=False):
        if source_path is None:
            source_path = os.getcwd()
        res = []
        for model in self.models:
            print("Deploying model %s" % model)
            res.append(self.deploy_model(source_path, model, blocking=False, dry_run=dry_run))
        return res

    def destroy_api_cluster(self):
        """
        Destroys the elastic beanstalk environment for the given model
        """
        print("Destroying API cluster...")
        filename = "deploy_api.zip"
        cluster = self._resource_manager.create_api_cluster(filename)
        cluster.blocking_delete(verbose=True)
        print("Destroyed API cluster")

    def create_token(self, token_lifetime_in_hours):
        chars = (string.ascii_letters + string.digits + '!@#$%^&*()')[:64]
        token_key = "".join([chars[os.urandom(1)[0] % len(chars)] for x in range(32)])
        secret = "".join([chars[os.urandom(1)[0] % len(chars)] for x in range(32)])

        ddb = self._aws_manager.get_client('dynamodb')
        expires = int(time.time() + token_lifetime_in_hours * 60 * 60)
        res = ddb.put_item(
            TableName=self._resource_manager.prefix_name("auth"),
            Item={
                "token_key": {"S": token_key},
                "secret": {"S": secret},
                "expires": {"N": str(expires)}
            }
        )
        return {
            "token_key": token_key,
            "secret": secret,
            "expires": expires
        }

    def destroy_model_cluster(self, model_name):
        """
        Destroys the elastic beanstalk environment for the given model
        """
        filename = "deploy_model_%s.zip" % model_name
        cluster = self._resource_manager.create_model_cluster(filename, model_name)
        cluster.blocking_delete(verbose=True)
        print("Destroyed cluster for model " % model_name)

class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(time.mktime(obj.timetuple()))
        return json.JSONEncoder.default(self, obj)

def copytree(src, dst, symlinks=False, ignore=None):
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        #if os.path.isdir("/" + "/".join(d.split("/")[:-1])):
        #    shutil.copy2(s, d)
        #    os.chmod(d, 644)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            try:
                os.makedirs("/" + "/".join(d.split("/")[:-1]))
            except FileExistsError:
                pass
            if os.path.exists(d):
                os.chmod(d, 644)
            shutil.copy2(s, d)
