# Copyright 2016 Morgan McDermott & Blake Allen
"""

The Controller class coordinates the creation of API and Model
elastic beanstalk environments

"""
import os
import os.path
from zipfile import ZipFile

import json
import time
import datetime
from threading import Thread

import pressurize.ResourceManager as ResourceManager
import pressurize.AWSManager as AWSManager


class Controller(object):
    def __init__(self, config):
        self._defaults = {
        }
        self.validate_config(config)
        self.config = config
        self.local_queues = {}

        for key in config:
            setattr(self, key, config[key])

        for key in self._defaults:
            if key not in config:
                setattr(self, key, self._defaults[key])

        self._aws_manager = AWSManager.AWSManager()

        # Deploy cluster on initialization
        self._resource_manager = ResourceManager.ResourceManager(self)
        self._cluster = self._resource_manager.createResourceCluster()

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
        required_keys = ['deployment_name', 'aws_region', 'path', 'models']
        for key in required_keys:
            if key not in config:
                raise Exception('Config must have key %s' % key)


    def deploy_model(self):


    def deploy_model_server(self, model):

class MyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return int(time.mktime(obj.timetuple()))
        return json.JSONEncoder.default(self, obj)
