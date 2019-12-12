#!/bin/bash -e
# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 CERN.
#
# inspirehep is free software; you can redistribute it and/or modify it under
# the terms of the MIT License; see LICENSE file for more details.

IMAGE="inspirehep/hep"
DOCKER_CONTEXT='backend'
TAG="$(git describe --always)"

retry() {
    "${@}" || "${@}" || exit 2
}

login() {
  echo "Logging into Docker Hub"
  retry docker login \
      "--username=${DOCKERHUB_USER}" \
      "--password=${DOCKERHUB_PASSWORD}"
}

buildPush() {
  echo "Building docker image"
  retry docker build \
    --build-arg VERSION="${TAG}" \
    -t "${IMAGE}:${TAG}" \
    -t "${IMAGE}" \
    "${DOCKER_CONTEXT}"

  echo "Pushing image to ${IMAGE}:${TAG}"
  retry docker push "${IMAGE}:${TAG}"
  retry docker push "${IMAGE}"
}

logout() {
  echo "Logging out""${@}"
  retry docker logout
}

deployQA() {
  if [ -z "${TRAVIS_TAG}" ]; then
    curl -X POST \
      -F token=${DEPLOY_QA_TOKEN} \
      -F ref=master \
      -F variables[IMAGE_NAME]=inspirehep/hep \
      -F variables[NEW_TAG]=${TAG} \
      https://gitlab.cern.ch/api/v4/projects/62928/trigger/pipeline
  fi
}

main() {
  login
  buildPush
  logout
  deployQA
}
main
