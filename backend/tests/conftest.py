import os
import tempfile

# Local test isolation, never touch user data.
os.environ["PLANEXUS_DATA_DIR"] = tempfile.mkdtemp(prefix="planexus-test-")
