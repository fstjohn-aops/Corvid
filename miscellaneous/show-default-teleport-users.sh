#!/bin/bash

# Simple script to show AoPS-Default-User labels for all teleport hosts
tsh ls --format=json | jq -r '.[] | "\(.spec.hostname)\n  AoPS-Default-User: \(.spec.cmd_labels."AoPS-Default-User".result // "not set")"'
