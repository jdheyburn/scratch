"""musiclib — music library tooling.

`musiclib vinyl sync` takes a record from Audacity export to a verified beets
import. See the design doc for why each step is shaped the way it is.
"""

from importlib.metadata import version

__version__ = version("musiclib")
