#!/bin/bash
. setGrinderEnv.sh
echo $CLASSPATH
java -cp $CLASSPATH -Dgrinder.logDirectory="$GRINDERPATH/logs/$(date +%y%m%d)" net.grinder.Grinder $GRINDERPROPERTIES
