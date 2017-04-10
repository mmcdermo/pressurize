from pressurize.model import PressurizeModel

class TestModel(PressurizeModel):
    def setup(self):
        super().__init__()

    def preprocess(self, data):
        data["number"] += 1
        return data

    def predict(self, data):
        return {"status": "success",
                "number": data["number"]}
