"""Compatibility entrypoint for durable-command transport recovery."""
import runpy,sys
from pathlib import Path
sys.argv.extend(['--environment','journal'])
runpy.run_path(str(Path(__file__).with_name('run_cloud_chain.py')),run_name='__main__')
