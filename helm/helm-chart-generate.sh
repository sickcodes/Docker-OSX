#!/usr/bin/env bash
# Author: sick.codes
# License: GPLv3+
# Repo: https://github.com/sickcodes/Docker-OSX/
# cd ../helm

rm -f docker-osx-*.tgz
helm package .
helm repo index . --url https://sickcodes.github.io/Docker-OSX/helm/
