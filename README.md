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

## Status (may not be current)

* 131 total IDs
* 33 fully documented
* 28 in progress
* 70 not documented

## Beware/Warning

This project is (of course!) non-official, an thus, informations here may be incorrect (even if we take lots of precautions to avoid this),
any modification you may do to your car is your sole responsibility!  
This project uses a mix of english and french, be prepared to use a translation tool if you don't speak both languages (and the jargon in both!),
the reason for this is that we tend to work in english, but are native french, and PSA works using french internally, so we adapt to their jargon.

## Contribute

The easiest way to contribute is probably to join the discord and go to the psa-can-re chan, alternatively, you can send me an email at jason [at] prototux.net

## Thanks

* Wouter Bokslag for his awesome work on the [reverse engineering of the immobilizer](https://fahrplan.events.ccc.de/congress/2019/Fahrplan/events/11020.html)
* Alexandre Blin for his [tools](https://github.com/alexandreblin?tab=repositories), work on his 207 and for being a huge inspiration for this
* Peter Pinter for his huge work on his own [FullCAN to VAN bridge](https://github.com/morcibacsi?tab=repositories)
* Karaelyn and Kailokyra for their advices, especially on embedded dev
* All the people who leaked parts of PSA's designs all over the internet :)