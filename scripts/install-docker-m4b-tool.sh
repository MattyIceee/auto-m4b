#!/bin/bash
# pull the image if it is not available
if [ ! "$(docker images -q sandreas/m4b-tool:latest 2>/dev/null)" ]; then
    docker pull sandreas/m4b-tool:latest
fi

git_root=$(git rev-parse --show-toplevel)

# change to the root of the git repository
cd $git_root
echo -e "Pulling the latest changes from the m4b-tool repository into $git_root/m4b-tool...\n"

# if m4b-tool dir does not exist, then clone the repository
if [ ! -d "m4b-tool" ]; then
    git clone https://github.com/sandreas/m4b-tool.git
    cd m4b-tool
else # if it does exist, then pull the latest changes
    cd m4b-tool
    git pull
fi

# Look in the Dockerfile for the following line, and raise an error if found: "ADD ./Dockerfile ./dist/m4b-tool.phar* /tmp/"
if [ -n "$(grep -E 'ADD\s+\./Dockerfile\s+\./dist/m4b-tool\.phar\*\s+/tmp/' Dockerfile)" ]; then
    echo -e "\nWildcard syntax is not supported by the buildx builder anymore, but m4b-tool's Dockerfile still uses it.\nManually edit ./m4b-tool/Dockerfile and change:\n\nADD ./Dockerfile ./dist/m4b-tool.phar* /tmp/\n\n...to:\n\nADD ./Dockerfile /tmp/\n\nIf you're using a custom .phar file, you'll need to add a line to ADD it explicitly."
    exit 1
fi

# with:
# ADD ./Dockerfile /tmp/
# ADD ./dist/m4b-tool.phar* /tmp/

# build docker image - this will take a while
docker build . -t m4b-tool

# use the specific pre-release from 2022-07-16
docker build . --build-arg M4B_TOOL_DOWNLOAD_LINK=https://github.com/sandreas/m4b-tool/files/10728378/m4b-tool.tar.gz -t m4b-tool

cd ..

echo -e "\nSuggest adding the following to your .bashrc or .zshrc file:"
echo -e "alias m4b-tool='docker run -it --rm -u $(id -u):$(id -g) -v \"$(pwd)\":/mnt sandreas/m4b-tool:latest'"

echo -e "\nThen test:\nm4b-tool --version"
