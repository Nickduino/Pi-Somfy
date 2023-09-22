#!/bin/bash

cd /home/Pi-SomfyCode/
cp /home/Pi-SomfyCode/shutters.service /etc/systemd/system/shutters.service

systemctl daemon-reload
systemctl enable shutters
systemctl start shutters
