from contextlib import contextmanager
import tensorflow as tf

class PressurizeModel(object):
    def __init__(self, resources, config=None, logger=None):
        self.resources = resources
        self.config = config

    @contextmanager
    def modelcontext(self):
        """
        Default context manager does nothing
        """
        yield

    def preprocess(self, data):
        return data

    def predict(self, data):
        raise NotImplementedError

class PressurizeTFModel(PressurizeModel):
    def tf_setup(self):
        raise NotImplementedError

    @contextmanager
    def modelcontext(self, device="/cpu:0"):
        """
        Tensorflow context manager creates a new graph and executes code
        in the context of a default graph and the given tensorflow device
        """
        graph = tf.Graph()
        with graph.as_default():
            with tf.device(device):
                self.tf_setup()
                yield
