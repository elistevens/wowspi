#!/bin/bash

sleep 5

out=`ps -aux | head -1`
echo "$out"
out=`ps -aux | fgrep ython | fgrep .py | sed -e "s#/Library.*/Python#python#g" | sed -e "s/100[.]0/100./g"`
echo "$out"

while [ "$out" != "" ]
do
    echo "$out"
    sleep 30
    out=`ps -aux | fgrep ython | fgrep .py | sed -e "s#/Library.*/Python#python#g" | sed -e "s/100[.]0/100./g"`
done
