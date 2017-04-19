#!/bin/bash
cd "$1"
docker build . -t "localmodel$2"
docker run -p "$3":5000 -t "localmodel$2"
