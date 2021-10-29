#!/usr/bin/sh

rapper -o turtle xcat.rdfs > xcat.ttl
. ~/venvs/schema_render/bin/activate
../../src/schema_render/render_schema.py xcat.ttl --base-ns xcat
