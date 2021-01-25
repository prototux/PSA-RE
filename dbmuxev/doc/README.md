# DBMUXEv format specs v0.1

## Intro

The DBMUXE format is a format aiming at defining formats for multiples types of embedded networks commonly found in cars. It was created because other formats (including DBCan from vector) didn't fit our needs (describing multiple generations of designs each including multiple networks)

It's primarily used to describe the architectures from PSA (Peugeot/Citroen/DS), hence the name, DBMUXEv is a reference to "DBMUX", the internal software they use to describe their multiplexed networks, and 'ev' is often used at PSA to describe an evolution to something.

## Terminology

* **architecture**: a name for a set of design templates (eg. AEE2004)
* **variant**: the architecture variant (derivative)
* **network**: a network is a set of buses (sharing nodes)
* **bus**: a physical link between nodes (can be CAN, LIN, etc)
* **node**: a controller/ECU connected to one or more bus(es)
* **protocol**: the protocol used to send data on a bus
* **message**: a frame sent on a bus (eg. a can frame)
* **signal**: a data point sent in a message (eg. the bits)


## Directory structure

```
.
├── architectures.yml (the file describing the architectures)
├── cars
│   ├── {id}.yml (the file linking the car to the architecture(s)
├── nodes
│   ├── {architecture}.{variant}.yml
├── buses
│   ├── {architecture}.{variant}
│   │   ├── {network}.{bus}
│   │   │   ├── {message}.yml (a file describing a frame)
├── diag
│   ├── {architecture}.{variant}
│   │   ├── {node}
│   │   │   ├── dids
│   │   │   │   ├── {did}.yml
│   │   │   ├── dtcs.yml
│   │   │   ├── resets.yml
│   │   │   ├── routines
│   │   │   │   ├── {routine}.yml
```

## Rules

* If a message is identical between multiple architectures (and versions of architectures), describe it in the most relevant version of the first architecture implementing it, then create symlink to it
* The dot `.` is used as a separator when needed
* The examples only set english (en) and french (fr) languages, but any language can be added with it's corresponding ISO code (2 letters)

## TODO

* Define an include format for multiple messages based on the same template
* Define these protocols
* * LIN
* * KWP2k
* * K-lines
* * PSA2k
* Add UDS ioctl (do we need them?)
* Probably refine nodes.yml
