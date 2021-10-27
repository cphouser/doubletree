#!/usr/bin/env python3
import os
import yaml

CONFIG_PATH = "../data/doubletree.conf"

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH) as f:
        Config = yaml.safe_load(f)
