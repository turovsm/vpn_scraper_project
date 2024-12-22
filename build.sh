#!/bin/bash

if [ ! -d "/app/static/flags" ]; then
    echo "Flags directory not found, cloning repository..."
    git clone https://github.com/hampusborgos/country-flags.git ./tmp/country-flags
    mv ./tmp/country-flags/svg ./app/static/flags  
    rm -rf ./tmp
else
    echo "Flags directory already exists. Skipping cloning."
fi

echo "Stopping any running containers..."
docker-compose down

echo "Building and starting containers..."
docker-compose up --build -d

if [ $? -eq 0 ]; then
    echo "Containers built and started successfully!"
    echo "Flask app is running at http://localhost:5000"
else
    echo "Failed to build and start containers. Check the logs for details."
    exit 1
fi
