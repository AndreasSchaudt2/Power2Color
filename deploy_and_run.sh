#!/bin/bash

# Define variables
REMOTE_USER=andi
REMOTE_HOST=power2colorpizero
REMOTE_DIR=/home/andi/Power2Color
LOCAL_DIR="C:/Users/Andre/OneDrive/Documents/Code/Power2Color/Power2Color"


# Push all files to the Raspberry Pi
scp -r $LOCAL_DIR/ $REMOTE_USER@$REMOTE_HOST:$REMOTE_DIR

# Run the script on the Raspberry Pi
#ssh $REMOTE_USER@$REMOTE_HOST " cd $REMOTE_DIR/Power2Color/ && ./run_power2color.sh" | tee 