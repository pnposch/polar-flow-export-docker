Polar Flow Exporter Docker
=========================

A tool for exporting training sessions from [Polar Flow](https://flow.polar.com).

## Updates
Moved Selenium to the docker
Adjusted Login for new Polar Auth (July 2025)
Bug-hunting

## Installation

```bash
$ git clone https://github.com/pnposch/polar-flow-export.git
$ docker compose up -d
```

## Usage

```bash
docker exec -it polar-flow-export python3 polar-flow-export.py <month> <year>
```

If <month> <year> is not provided on command line, config.json will be used.

The tool will save sessions into the output directory, using the default filename
provided by Polar.


