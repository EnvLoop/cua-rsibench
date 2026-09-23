"""Versioned bounds for real training; dataset rows may not be silently ignored."""
PROFILES={
    'pilot-v1':{'max_steps':16,'max_records':32,'batch_size':2,'sequence_tokens':16384,'scheduled_tokens':262144},
    'factory-v1':{'max_steps':128,'max_records':256,'batch_size':2,'sequence_tokens':16384,'scheduled_tokens':262144},
}


def schedule(record_count,steps,profile='pilot-v1'):
    if profile not in PROFILES:raise ValueError('unknown training profile')
    config=PROFILES[profile]
    if type(steps) is not int or not 1<=steps<=config['max_steps']:raise ValueError('optimizer steps outside profile')
    if type(record_count) is not int or not 1<=record_count<=config['max_records']:raise ValueError('record count outside profile')
    indices=[[(step*config['batch_size']+i)%record_count for i in range(config['batch_size'])] for step in range(steps)]
    covered={i for batch in indices for i in batch}
    if profile=='factory-v1' and len(covered)!=record_count:
        raise ValueError(f'training schedule would omit {record_count-len(covered)} submitted records; increase exposure or revise data')
    return config,indices
