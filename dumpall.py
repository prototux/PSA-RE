#!/usr/bin/env python3

from pprint import pprint
from dbmuxev import dbmuxev

db = dbmuxev()
db.load_all()

print('==> Architectures, nodes and frames')
pprint(db.archs)

print('==> Cars')
pprint(db.cars)


