"""Explicit original Office account/native lease; no fictional E2B charge."""
from hashlib import sha256
import json
from . import full_study_selection_environment_v1 as old
from .full_study_matrix_v1 import CELLS
SCHEMA='cua-full-study-selection-environment-v2'
BY_CELL={**old.BY_CELL,'powerpoint-web':'storage_application','excel-web':'storage_application'}
NATIVE_BY_CELL={'powerpoint-web':'owned_local_browser_cloud_account','excel-web':'owned_local_browser_cloud_account',
    'desktop-native':'owned_e2b_native_desktop','odoo-community':'owned_self_hosted_original_application',
    'gitlab':'owned_self_hosted_original_application','magento-admin':'owned_self_hosted_original_application'}
if set(BY_CELL)!=set(CELLS):raise RuntimeError('six_cell_environment_scope_changed')


def category(cell_id):
    if cell_id not in BY_CELL:raise ValueError('unknown_full_study_cell')
    return BY_CELL[cell_id]


def paid_categories_valid(cell_id,categories):
    required=category(cell_id)
    return type(categories) is set and {'tinker',required}<=categories and (required=='e2b' or 'e2b' not in categories)


def binding_sha256():
    return sha256((json.dumps({'schema':SCHEMA,'by_cell':BY_CELL,'native_by_cell':NATIVE_BY_CELL,'native_account_lease_seconds':1200},sort_keys=True,separators=(',',':'))+'\n').encode()).hexdigest()
