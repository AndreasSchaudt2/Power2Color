#!/bin/bash

#stop the service
sudo systemctl stop power2color.service

#reload the daemon to reflect the changes
sudo systemctl daemon-reload

#restart the service
sudo systemctl restart power2color.service

#output the status of the service to the terminal to quickly check if it is running
sudo systemctl status power2color.service