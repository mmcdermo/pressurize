from pressurize.model import PressurizeModel

class TestModel(PressurizeModel):
    def preprocess(self, request):
        request["data"]["number"] += 1
        return request

    def predict(self, request):
        param_contents = -1
        with open(self.resources["parameters"], 'r') as f:
            print("Reading parameters from %s" % self.resources["parameters"])
            param_contents = f.read()
        return {
            "status": "success",
            "number": request["data"]["number"],
            "parameters": param_contents
        }
