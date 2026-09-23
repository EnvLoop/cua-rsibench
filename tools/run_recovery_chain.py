"""Compatibility entrypoint for transport-only read retries."""
import runpy,sys
from pathlib import Path
sys.argv.extend(['--environment','read-retry'])
runpy.run_path(str(Path(__file__).with_name('run_cloud_chain.py')),run_name='__main__')
