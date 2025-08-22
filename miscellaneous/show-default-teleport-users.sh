#!/bin/bash

# Simple script to show aops_default_user labels for all teleport hosts
tsh ls --format=json | jq -r '.[] | "\(.spec.hostname)\n  aops_default_user: \(.spec.cmd_labels."aops_default_user".result // "not set")"'
