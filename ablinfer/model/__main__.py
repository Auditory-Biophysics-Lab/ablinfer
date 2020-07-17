import json
import sys

from .normalize import load_model

if len(sys.argv) not in (2, 3):
    sys.stderr.write("Usage: %s <input file> [output file]\nUpdates and normalizes models.\n" % sys.argv[0])
    sys.exit(1)

res = json.dumps(load_model(open(sys.argv[1], 'r'))[0], indent=4)
if len(sys.argv) == 3:
    open(sys.argv[2], 'w').write(res+'\n')
else:
    print(res)
