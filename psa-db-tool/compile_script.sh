#!/bin/sh

if [ -d "src/submodules/rapidyaml" ]
then
    echo "Submodule \"rapidyaml\" already exist. Continuing installation."
else
    echo "Missing submodule \"rapidyaml\". Downloading now..."
    git submodule add https://github.com/biojppm/rapidyaml.git src/submodules/rapidyaml
    git submodule update --init --recursive
fi

cfg=${1:-Release}

cmake -S ./src -B ./build/$cfg

cmake --build ./build/$cfg
