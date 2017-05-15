import os
import os.path
import json
import pressurize.model.model_server as server

def main():
    model_dir = os.path.join(*__file__.split("/")[:-1])
    config = {}
    with open(os.path.join(model_dir, "pressurize.json")) as f:
        config = json.load(f)
    process = server.run_server(config['models'],
                                source_path=os.path.join(model_dir),
                                port='5000')

if __name__ == '__main__':
    main()
