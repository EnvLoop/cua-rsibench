"""Exact current native table position for LibreOffice virtual cell instances.

LibreOffice 7.3 creates a fresh accessible object for a non-active cell on
each query. This joins those instances by native Table position, not by a
cell label, pixels alone, or process ID. Original physical leaf checks run.
"""
import re
if __package__:
    from .native_editor_capability_v42 import BUILD
    from .native_hit_identity_diagnostic_v33 import identity as native_identity
else:
    from native_editor_capability_v42 import BUILD
    from native_hit_identity_diagnostic_v33 import identity as native_identity


def require(ok, message):
    if not ok:
        raise ValueError(message)


def checked_virtual_cell(reader, Atspi, node, window, *, pid, viewport,
                         ancestry, build, identity=native_identity):
    require(build == BUILD, 'Unsupported virtual-cell application build')
    require(type(pid) is int and pid > 0, 'Native virtual-cell process unknown')
    def checked_identity(value):
        result = identity(value)
        require(result.get('available') is True and type(result.get('identity_sha256')) is str
                and re.fullmatch(r'[0-9a-f]{64}', result['identity_sha256']) is not None,
                'Native virtual-cell identity unknown')
        return result
    owned = checked_identity(window)

    def descriptor(cell):
        require(cell.get_role_name() == 'table cell', 'Unsupported virtual-cell role')
        chain = ancestry(cell, window)
        require(chain and checked_identity(chain[0])['identity_sha256'] == checked_identity(cell)['identity_sha256']
                and checked_identity(chain[-1])['identity_sha256'] == owned['identity_sha256'],
                'Virtual cell has another native ownership root')
        require(all(n.get_process_id() == pid and checked_identity(n).get('available') is True
                    for n in chain), 'Virtual-cell native ownership differs')
        for ancestor in chain:
            states = reader.state_flags(Atspi, ancestor)
            require(all(states.get(k) is True for k in ('VISIBLE', 'SHOWING', 'ENABLED'))
                    and states.get('STALE') is False and states.get('DEFUNCT') is False,
                    'Virtual-cell native ancestor unsafe')
            require(states.get('SENSITIVE') is True or ancestor.get_role_name() in
                    ('table cell', 'table', 'document spreadsheet'),
                    'Unsupported insensitive native ancestor')
        flags = reader.state_flags(Atspi, cell)
        require(all(flags.get(k) is True for k in ('VISIBLE', 'SHOWING', 'ENABLED', 'EDITABLE'))
                and all(flags.get(k) is False for k in ('SENSITIVE', 'STALE', 'DEFUNCT', 'MANAGES_DESCENDANTS')),
                'Virtual-cell native state unsafe/unsupported')
        count = cell.get_child_count()
        require(type(count) is int and count == 0,
                'Virtual cell is not a native zero-child leaf')
        parents = [n for n in chain[1:] if n.get_role_name() == 'table']
        require(len(parents) == 1, 'Native virtual-cell Table missing/ambiguous')
        table = parents[0]
        table_flags = reader.state_flags(Atspi, table)
        require(all(table_flags.get(k) is True for k in ('VISIBLE', 'SHOWING', 'ENABLED', 'EDITABLE', 'FOCUSED'))
                and table_flags.get('STALE') is False and table_flags.get('DEFUNCT') is False,
                'Current focused native Table unsafe')
        interface = table.get_table_iface()
        require(interface is not None, 'Native Table position interface unavailable')
        rows, columns = interface.get_n_rows(), interface.get_n_columns()
        require(type(rows) is int and type(columns) is int and
                0 < rows <= 1048576 and 0 < columns <= 1024,
                'Native Table dimensions unsupported')
        index = cell.get_index_in_parent()
        require(type(index) is int and 0 <= index < rows * columns,
                'Native virtual-cell index unknown/outside Table')
        row, column = interface.get_row_at_index(index), interface.get_column_at_index(index)
        roundtrip = interface.get_index_at(row, column)
        require(type(row) is int and type(column) is int and type(roundtrip) is int and
                0 <= row < rows and 0 <= column < columns and roundtrip == index,
                'Native Table position does not round trip')
        return {'table_identity_sha256': checked_identity(table)['identity_sha256'],
                'native_index': index, 'row': row, 'column': column}, flags

    first, first_flags = descriptor(node)
    bounds = reader.geometry(Atspi, node, viewport)
    require(bounds is not None, 'Native virtual cell outside actual viewport')
    point = [bounds[0] + bounds[2] // 2, bounds[1] + bounds[3] // 2]
    hit, depth = reader.physical_hit(Atspi, window, point, pid=pid,
                                    viewport=viewport, ancestry=ancestry)
    require(type(depth) is int and 2 <= depth <= 32, 'Original native physical leaf depth unknown')
    second, second_flags = descriptor(hit)
    hit_bounds = reader.geometry(Atspi, hit, viewport)
    require(first == second, 'Current physical leaf has another native Table position')
    require(bounds == hit_bounds, 'Current native virtual-cell geometry changed')
    return {'schema': 'owned-current-native-virtual-cell-identity-v44',
            'virtual_descriptor': first, 'node_identity': identity(node),
            'physical_leaf_identity': identity(hit), 'physical_hit_depth': depth,
            'native_bus_object_ids_equal': identity(node)['identity_sha256'] == identity(hit)['identity_sha256'],
            'native_table_position_equality_checked': True,
            'original_strict_physical_leaf_checks_used': True,
            'raw_native_flags_preserved': True, 'node_raw_flags': first_flags,
            'physical_leaf_raw_flags': second_flags,
            'cell_name_or_value_used': False, 'same_pid_or_bounds_shortcut_used': False}
