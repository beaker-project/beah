#!/bin/bash

# eventually it will change and rhts-reboot will use beah-reboot...

rhts-reboot
echo "Reboot requested. For now this is ignored. Run 'rhts-reboot' manually, please."

# FIXME: Use env to decide if reboot or just block...

while true; do
  while true; do
    sleep 600
  done

  echo "It's bad... You were not supposed to see this message."
  sleep 10
done

echo "And it's going to be worse now..."
echo "You were warned!"
exit 1
