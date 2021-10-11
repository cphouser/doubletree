#!/usr/bin/env python3
import yaml
import os

from conf_file import CONFIG_PATH

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-path', '-p', nargs='+', default=[],
                        help='base path(s) for files indexed in the rdf db')
    args = parser.parse_args()

    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f)
    else:
        config = {}

    base_paths = config.get("base_paths", [])
    base_paths.extend([path for path in args.base_path])

    if not base_paths:
        base_paths.append("/example/path/root-to-data/")
    config["base_paths"] = base_paths

    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f)
