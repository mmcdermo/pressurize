"""
 model_server.py
 Runs a simple API granting access to all available models.
 Usage: python model_server.py

 This server uses a separate process to perform predictions, with a pipe
 from `multiprocessing` connecting the flask server thread to the prediction
 process. Access to the server side of the pipe is guarded by a Lock from multiprocessing.
"""

from flask import Flask, jsonify, request, abort, make_response
import json
from multiprocessing import Queue, Process, Pipe, Lock
import multiprocessing
import queue as Q
import random
import tensorflow as tf
import os.path
import os
import importlib

serverPipeLock = Lock()
pipes = {}
app = Flask(__name__)

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

class ModelServer(object):
    def __init__(self, pipe, model):
        self._pipe = pipe
        self._model = model

    def run(self):
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
                    self._pipe.send({"error": "Exception: "+str(e)})

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

def run_server(models, source_path=os.getcwd(), port='5000', debug=False, separate_process=False):
    """
    run_server takes a list of models from a pressurize.json config,
    starting a ModelServer in a separate process for each model.
    """
    for model in models:
        model_obj = import_model(model['path'], source_path)()
        pipes[model['name']] = Pipe()
        model_server = ModelServer(pipes[model['name']][1], model_obj)
        taskProcess = Process(target=model_server.run)
        taskProcess.start()
    if separate_process:
        serverProcess = Process(target=app.run, args=(('0.0.0.0', port, debug)))
        serverProcess.start()
        return serverProcess
    else:
        app.run(host='0.0.0.0', port=port, debug=debug)
