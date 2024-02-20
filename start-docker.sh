#!/bin/bash

# Define the project name
PROJECT_NAME="auto-m4b"

# Get a list of volumes associated with the project
VOLUMES=$(docker volume ls --filter "name=${PROJECT_NAME}_" --quiet)

# Check if there are volumes associated with the project
if [ -n "$VOLUMES" ]; then
  # Loop through each volume
  for VOLUME in $VOLUMES; do
    # Check if the volume is attached to a container
    CONTAINERS=$(docker ps --quiet --filter "volume=${VOLUME}")
    if [ -z "$CONTAINERS" ]; then
      # Delete the volume if it's not attached to any containers
      echo "Volume '${VOLUME}' associated with the project '${PROJECT_NAME}' is unattached and will be removed."
      docker volume rm $VOLUME
    # else
    #   echo "Volume '${VOLUME}' associated with the project '${PROJECT_NAME}' is attached to containers and won't be removed."
    fi
  done
fi

docker compose -f docker-compose.yml up -d --build
