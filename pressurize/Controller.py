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
from zipfile import ZipFile
from threading import Thread

import botocore

from redleader.managers import ElasticBeanstalkManager

import pressurize.ResourceManager as ResourceManager
import pressurize.AWSManager as AWSManager


class Controller(object):
    def __init__(self, config):
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

        self._aws_manager = AWSManager.AWSManager()

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
        for key in required_keys:
            if key not in config:
                raise Exception('Config must have key %s' % key)

    def recursively_add_files_to_zip(self, source_path, zipfile, base=""):
        for filename in os.listdir(source_path):
            if os.path.isdir(os.path.join(source_path, filename)):
                self.recursively_add_files_to_zip(os.path.join(source_path, filename),
                                             zipfile, os.path.join(base, filename))
            else:
                os.chmod(os.path.join(source_path, filename), 776)
                zipfile.write(os.path.join(source_path, filename),
                              os.path.join(base, filename))

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

    def deploy_api(self):
        """
        Deploys an elastic beanstalk environment for the pressurize API
        """
        packagefile = self.create_api_package()
        print("Created API elastic beanstalk package ", packagefile)
        bucket_name = self._resource_manager.elastic_beanstalk_bucket()
        manager = ElasticBeanstalkManager(self._aws_manager)
        manager.upload_package(bucket_name, os.path.join(os.getcwd(), packagefile), packagefile)
        cluster = self._resource_manager.create_api_cluster(packagefile)
        try:
            cluster.blocking_deploy()
        except botocore.exceptions.ClientError as e:
            if "exists" in "%s" % e:
                print("Cluster already exists. Updating")
                cluster.blocking_update()
            else:
                raise e

    def deploy_model(self, source_path, model_name, blocking=True):
        """
        Deploys an elastic beanstalk environment for the given model
        """
        packagefile = self.create_model_package(source_path, model_name)
        print("Created model elastic beanstalk package ", source_path, packagefile)
        bucket_name = self._resource_manager.elastic_beanstalk_bucket()
        manager = ElasticBeanstalkManager(self._aws_manager)
        manager.upload_package(bucket_name, os.path.join(os.getcwd(), packagefile), packagefile)
        cluster = self._resource_manager.create_model_cluster(packagefile, model_name)
        try:
            if blocking:
                cluster.blocking_deploy()
            else:
                cluster.deploy()
        except botocore.exceptions.ClientError as e:
            if "exists" in "%s" % e:
                print("Cluster already exists. Updating")
                if blocking:
                    cluster.blocking_update()
                else:
                    cluster.update()
            else:
                raise e

    def deploy_models(self):
        source_path = "/" + os.path.join(*(__file__.split("/")[:-2] + ["test_data", "test_model_server"]))
        for model in self.models:
            print("Deploying model %s" % model)
            self.deploy_model(source_paths, model, blocking=False)

    def destroy_api_cluster(self):
        """
        Destroys the elastic beanstalk environment for the given model
        """
        filename = "deploy_api.zip"
        cluster = self._resource_manager.create_api_cluster(filename)
        cluster.blocking_delete()

    def destroy_model_cluster(self, model_name):
        """
        Destroys the elastic beanstalk environment for the given model
        """
        filename = "deploy_model_%s.zip"
        cluster = self._resource_manager.create_api_cluster(filename)
        cluster.blocking_delete()


class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(time.mktime(obj.timetuple()))
        return json.JSONEncoder.default(self, obj)
