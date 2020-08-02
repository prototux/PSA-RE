# CANBus

## What is this repo about

This project is about reverse engineering the AEE2004 ("full can") architecture of PSA (Peugeot/Citroen/DS) cars.
It's the continuation of my previous work @ https://github.com/prototux/PSA-CANbus-reverse-engineering

## What if i have a car using VAN?

See the great work of [Peter Pinter](https://github.com/morcibacsi?tab=repositories)

## What if i have a car using AEE2010?

Some parts here seems valid for AEE2010, some aren't, not having a car using AEE2010 i don't know how much AEE2010 is similar to AEE2004

## Howto use this repo

General documentation is in [the wiki](https://git.prototux.net/reverse-engineering/psa/canbus/-/wikis/home)  
Informations about specific frames are [in issues](https://git.prototux.net/reverse-engineering/psa/canbus/-/issues)  
The discord where we talk about this is [here](https://discord.gg/uPykZ5W)  
The repo itself contains mostly PoC code

## Ideas/Todo

* Do a ultra-low-power module for power management using PSA's COMMANDES_BSI frame
* Create a C "libpsa" and python bindings to easily integrate PSA's canbus into projects
* Create a RADIO and EMF replacement with more modern options
* Isolate the servo controllers from the front panel of CLIM to be able to move AC controls elsewhere
* Reverse engineering the BSI as it's the main component of both AEE2004 and AEE2010
* Create well-integrated optional modules such as ACC and DSG