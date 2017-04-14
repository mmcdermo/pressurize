from contextlib import contextmanager

class PressurizeModel(object):
    def __init__(self, resources):
        self.resources = resources

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
    @contextmanager
    def modelcontext(self, device="/cpu:0"):
        """
        Tensorflow context manager creates a new graph and executes code
        in the context of a default graph and the given tensorflow device
        """
        graph = tf.Graph()
        with graph.as_default():
            with tf.device(device):
                yield
