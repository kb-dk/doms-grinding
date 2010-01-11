#!/bin/bash
. setGrinderEnv.sh
echo $CLASSPATH
java -cp $CLASSPATH net.grinder.Console
