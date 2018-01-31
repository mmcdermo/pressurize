"""
 model_server.py
 Runs a simple API granting access to all available models.
 Usage: python model_server.py

 This server uses a separate process to perform predictions, with a pipe
 from `multiprocessing` connecting the flask server thread to the prediction
 process. Access to the server side of the pipe is guarded by a Lock from multiprocessing.
"""


from multiprocessing import Queue, Process, Pipe, Lock, log_to_stderr
import logging
import logging.handlers

import multiprocessing
import queue as Q
import random
import os.path
import json
import os
import importlib
import pkgutil

from flask import Flask, jsonify, request, abort, make_response
from flask_cors import CORS, cross_origin
import tensorflow as tf
import boto3
import botocore


class ModelServer(object):
    def __init__(self, config, source_path, resource_path, model_conf, pipe):
        self._pipe = pipe
        self._resources = ModelServer.acquire_resources(config, model_conf, resource_path)
        self._model_class = ModelServer.import_model(model_conf['path'], source_path)
        self._logger = self.setup_logging()
        self._model = self._model_class(self._resources, config=model_conf, logger=self._logger)

    def setup_logging(self):
        handler = logging.handlers.WatchedFileHandler(
            os.environ.get("PRESSURIZE_LOGFILE", "/var/log/pressurize.log"))
        formatter = logging.Formatter(logging.BASIC_FORMAT)
        handler.setFormatter(formatter)
        logger = logging.getLogger()
        logger.setLevel(os.environ.get("LOGLEVEL", "INFO"))
        logger.addHandler(handler)
        return logger

    def run(self):
        #logger = multiprocessing.log_to_stderr()
        self._logger.info('About to enter model processing loop')
        try:
            with self._model.modelcontext():
                while True:
                    item = self._pipe.recv()
                    if not hasattr(self._model, item['method']):
                        self._pipe.send({"error": "Model does not have method %s" % item['method']})
                    try:
                        preprocessed = self._model.preprocess(item["data"])
                        result = getattr(self._model, item['method'])(preprocessed)
                        self._pipe.send({"result": result})
                    except Exception as e:
                        self._pipe.send({"error": "Exception: " + str(e)})
                        self._logger.exception("Encountered error during invocation of method %s: %s" %
                                     (item['method'], str(e)))
        except Exception as e:
            self._logger.exception("Unexpected error encountered during model setup or request processing.")

    @staticmethod
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

    @staticmethod
    def acquire_resources(config, model, model_resource_path):
        session = boto3.Session(region_name=config['aws_region'])
        client = session.client('s3')

        resources = {}
        for resource_name in model['required_resources']:
            s3_path = model['required_resources'][resource_name]
            print("Downloading resource %s from %s" % (resource_name, s3_path))
            if not isinstance(s3_path, basestring):
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

serverPipeLock = Lock()
pipes = {}
app = Flask(__name__)
CORS(app)

@app.route('/api/<string:model>/<string:method>/', methods=['POST'])
def executeModelMethod(model, method):
    data = request.get_json()
    if data is None:
        print("Data not provided")
        return make_response(jsonify({'error': 'Data not provided'}), 400)

    if model not in pipes:
        print("Error: Model does not exist")
        return make_response(jsonify({'error': 'Model does not exist'}), 404)

    # Send our task over the pipe and wait for a result.
    resId = str(random.random())
    serverPipeLock.acquire()
    serverPipe = pipes[model][0]
    serverPipe.send({
        "model": model,
        "method": method,
        "data": data,
        "resId": resId
    })
    res = serverPipe.recv()
    serverPipeLock.release()

    if "error" in res:
        return make_response(jsonify({'error': res['error']}), 400)
    return jsonify(res)

def run_server(config, source_path=os.getcwd(), resource_path=os.getcwd(),
               port='5000', debug=False, separate_process=False):
    """
    run_server takes a list of models from a pressurize.json config,
    starting a ModelServer in a separate process for each model.
    """
    for model in config['models']:
        model_resource_path = os.path.join(resource_path, "resources", model['name'])
        pipes[model['name']] = Pipe()
        model_server = ModelServer(config, source_path, model_resource_path,
                                   model, pipes[model['name']][1])

        taskProcess = Process(target=model_server.run)
        taskProcess.start()
    if separate_process:
        serverProcess = Process(target=app.run, args=(('0.0.0.0', port, debug)))
        serverProcess.start()
        return serverProcess
    else:
        app.run(host='0.0.0.0', port=int(port), debug=debug)
