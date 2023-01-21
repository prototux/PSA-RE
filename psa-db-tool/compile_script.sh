#!/bin/sh

if [ -d "src/submodules/rapidyaml" ]
then
    echo "Submodule \"rapidyaml\" already exist. Continuing installation."
else
    echo "Missing submodule \"rapidyaml\". Downloading now..."
    git submodule add https://github.com/biojppm/rapidyaml.git src/submodules/rapidyaml
    git submodule update --init --recursive
fi

#g++ DB_converter_console.cpp -o ../DB_converter_console -Wall
#g++ -Wall -L/usr/local/lib -I/usr/local/include -std=c++11 PSA_DB_CONV.cpp -o ../PSA_DB_CONV -lyaml-cpp
#g++ -Wall -std=c++11 src/parsePsaYaml.cpp -o build/parsePsaYaml

cfg=${1:-Release}

cmake -S ./src -B ./build/$cfg

cmake --build ./build/$cfg
