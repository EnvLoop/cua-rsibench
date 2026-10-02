"""Run controller and Desktop SDK tests in their actual compatible runtimes.

Historical operator witnesses require the original controller interpreter.
Desktop SDK tests require E2B Desktop 2.2 and Pillow 11.3. No provider key is
passed to either process; these are tests, not application qualifications.
"""
from pathlib import Path
import argparse,json,os,subprocess,sys,unittest

ROOT=Path(__file__).resolve().parents[1]
DESKTOP_MODULES=('test_native_desktop_post_enter_train_calibration_v1',
    'test_native_desktop_v066_day_rollover_continuation')

def flatten(suite):
    for value in suite:
        if isinstance(value,unittest.TestSuite):yield from flatten(value)
        else:yield value

def run_controller():
    cases=[case for case in flatten(unittest.defaultTestLoader.discover(str(ROOT/'tests')))
        if case.__class__.__module__.split('.')[0] not in DESKTOP_MODULES]
    result=unittest.TextTestRunner(verbosity=1).run(unittest.TestSuite(cases))
    return {'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skips':len(result.skipped),'passed':result.wasSuccessful()}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--controller-only',action='store_true')
    parser.add_argument('--desktop-python',type=Path)
    args=parser.parse_args()
    for name in list(os.environ):
        if name.endswith('API_KEY') or name in ('CUA_TINKER_PROXY_URL','CUA_PROXY_TOKEN'):os.environ.pop(name,None)
    if args.controller_only:
        value=run_controller();print(json.dumps({'controller':value},sort_keys=True));raise SystemExit(0 if value['passed'] else 1)
    if args.desktop_python is None or not args.desktop_python.is_file():parser.error('A compatible Desktop SDK interpreter is required')
    env={**os.environ,'PYTHONPATH':os.pathsep.join(str(p) for p in
        (ROOT,ROOT/'src',ROOT/'tests',ROOT/'enterprise_fallback/odoo18',ROOT/'sec_excel_factory')),
        'PYTHONDONTWRITEBYTECODE':'1'}
    controller=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--controller-only'],cwd=ROOT,env=env)
    # Resolving the interpreter symlink would discard the selected virtualenv.
    desktop=subprocess.run([str(args.desktop_python.absolute()),'-m','unittest',
        *('tests.'+name for name in DESKTOP_MODULES)],cwd=ROOT,env=env)
    print(json.dumps({'controller_exit_code':controller.returncode,'desktop_exit_code':desktop.returncode,
        'provider_credentials_supplied':False,'real_model_or_training_execution':False},sort_keys=True))
    raise SystemExit(0 if controller.returncode==desktop.returncode==0 else 1)

if __name__=='__main__':main()
