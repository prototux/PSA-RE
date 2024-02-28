#!/bin/sh

if [ -d "src/submodules/rapidyaml" ]
then
    echo "Submodule \"rapidyaml\" already exist. Continuing installation."
else
    echo "Missing submodule \"rapidyaml\". Downloading now..."
    git submodule add https://github.com/biojppm/rapidyaml.git src/submodules/rapidyaml
    git submodule update --init --recursive
fi

#cfg=${1:-Release}
#cmake -S ./src -B ./build/$cfg
#cmake --build ./build/$cfg

cmd=${1:--help}

if [ $cmd = "--rebuild" ]
then
    cmake -S ./src -B ./build
    cmake --build ./build --clean-first
elif [ $cmd = "--build" ]
then
    cmake -S ./src -B ./build
    cmake --build ./build
else
    echo "No argument means you need HELP"
    echo "ARGUMENT          FUNCTION"
    echo "--build         = normal build"
    echo "--rebuild       = rebuild"
    echo "everything else = this help dialog"
fi
