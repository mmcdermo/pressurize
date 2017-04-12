from pressurize.model import PressurizeModel

class TestModel(PressurizeModel):
    def setup(self):
        super().__init__()

    def preprocess(self, request):
        request["data"]["number"] += 1
        return request

    def predict(self, request):
        return {"status": "success",
                "number": request["data"]["number"]}
