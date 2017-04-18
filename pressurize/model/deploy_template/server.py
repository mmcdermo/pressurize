import os
import os.path
import json
import pressurize.model.model_server as server

def main(port='5000'):
    model_dir = "/" + os.path.join(*__file__.split("/")[:-1])
    config = {}
    with open(os.path.join(model_dir, "pressurize.json")) as f:
        config = json.load(f)
    print("Running model server on port %s" % port)
    process = server.run_server(config,
                                source_path=os.path.join(model_dir),
                                port=port)

if __name__ == '__main__':
    main()
