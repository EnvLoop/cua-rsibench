"""Export separate-cohort figures only from complete audited study evidence."""
import argparse
from pathlib import Path
from build_factory_report import ROOT, load_publication, final_rows, has_recovery, write_bundle

BLUE = '#3154a5'
TEAL = '#087f73'
ORANGE = '#b2632a'
GRAY = '#637080'


def save(figure, directory, name):
    import matplotlib.pyplot as plt
    for extension in ('png', 'svg', 'pdf'):
        path = directory / f'{name}.{extension}'
        figure.savefig(path, dpi=220, bbox_inches='tight', facecolor='white')
        if extension == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(figure)


def pipeline(directory):
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    figure, axis = plt.subplots(figsize=(7, 3.0))
    axis.set(xlim=(-.2, 10.2), ylim=(-.3, 3.5))
    axis.axis('off')
    labels = [('Researcher code', 'Python generator\n+ data policy'),
              ('Native task states', 'Approved source facts\n+ task recipes'),
              ('GUI experience', 'gpt-5.6-sol teacher\n+ saved-state check'),
              ('Training data', 'Filter / representation\n/ order / mixture'),
              ('Tinker SFT', 'Qwen3.5-4B LoRA\n32 optimizer updates'),
              ('E2B + Harbor', 'Checkpoint proxy\n+ native browser trials'),
              ('Selection', 'Strict gain\n+ no task regression'),
              ('Sealed final tests', 'Freeze checkpoint\nFresh environments')]
    coordinates = [(0, 2.3), (2.6, 2.3), (5.2, 2.3), (7.8, 2.3),
                   (7.8, .65), (5.2, .65), (2.6, .65), (0, .65)]
    for (title, body), (x, y) in zip(labels, coordinates):
        axis.add_patch(FancyBboxPatch((x, y), 2.2, .85, boxstyle='round,pad=.04', lw=.8, edgecolor=BLUE, facecolor='#f0f4fb'))
        axis.text(x + 1.1, y + .62, title, ha='center', fontsize=8, weight='bold')
        axis.text(x + 1.1, y + .28, body, ha='center', va='center', fontsize=7.2, color=GRAY)
    for index in range(7):
        x, y = coordinates[index]
        xx, yy = coordinates[index + 1]
        start = (x + 2.25, y + .43) if index < 3 else ((x + 1.1, y - .05) if index == 3 else (x - .05, y + .43))
        end = (xx - .05, yy + .43) if index < 3 else ((xx + 1.1, yy + .90) if index == 3 else (xx + 2.25, yy + .43))
        axis.add_patch(FancyArrowPatch(start, end, arrowstyle='-|>', mutation_scale=10, lw=1.1, color=BLUE))
    axis.add_patch(FancyArrowPatch((3.7, 1.55), (1.1, 2.22), connectionstyle='arc3,rad=-.1', arrowstyle='-|>', mutation_scale=11, color=TEAL, linestyle='--'))
    axis.text(3.2, 1.87, 'Permitted feedback', fontsize=8, color=TEAL)
    axis.text(5, .1, 'The researcher cannot access credentials, hidden answers, or final-test feedback.', ha='center', fontsize=8, color=GRAY)
    save(figure, directory, 'factory-pipeline')


def trajectories(cohort, directory):
    import matplotlib.pyplot as plt
    data = cohort['data']
    campaigns = data['campaigns']
    figure, axes = plt.subplots(1, len(campaigns), figsize=(7, 3.1), layout='constrained', sharey=True, squeeze=False)
    for axis, campaign in zip(axes[0], campaigns):
        rounds = [attempt['round'] for attempt in campaign['attempts']]
        values = [attempt['evaluation']['score'] if attempt['evaluation']['status'] == 'scored' else None for attempt in campaign['attempts']]
        axis.plot([0] + rounds, [campaign['baseline']['score'] * 100] + [value * 100 if value is not None else float('nan') for value in values], '-o', color=BLUE, ms=5, label='Candidate')
        axis.step([0] + rounds, [campaign['baseline']['score'] * 100] + [attempt['best_after'] * 100 for attempt in campaign['attempts']], where='post', linestyle='--', color=TEAL, label='Incumbent')
        missing = [number for number, value in zip(rounds, values) if value is None]
        axis.scatter(missing, [-18] * len(missing), marker='x', color=ORANGE, s=45)
        axis.axhline(-7, lw=.6, color='#bec7d1')
        axis.set_ylim(-28, 108)
        axis.set_yticks([-18, 0, 100 / 3, 200 / 3, 100], ['Unscored', '0', '33.3', '66.7', '100'])
        axis.set_xticks([0] + rounds)
        axis.set_xlabel('Research round (0 = base)')
        axis.set_title(campaign['researcher'])
        axis.grid(axis='y', alpha=.15)
    axes[0][0].set_ylabel('Selection success (%)')
    axes[0][-1].legend(fontsize=7, loc='upper left')
    figure.suptitle(cohort['label'] + ' / fixed selection tasks', fontsize=10)
    save(figure, directory, f'factory-{cohort["id"]}-trajectories')


def budget(cohort, directory):
    import matplotlib.pyplot as plt
    campaigns = cohort['data']['campaigns']
    figure, axes = plt.subplots(1, len(campaigns), figsize=(7, 2.9), layout='constrained', sharey=True, squeeze=False)
    for axis, campaign in zip(axes[0], campaigns):
        x = [0] + [attempt['cumulative_training_tokens'] / 1000 for attempt in campaign['attempts']]
        y = [campaign['baseline']['score'] * 100] + [attempt['best_after'] * 100 for attempt in campaign['attempts']]
        axis.step(x, y, where='post', color=TEAL)
        axis.scatter(x, y, s=22, color=TEAL)
        axis.set(title=campaign['researcher'], ylim=(-4, 105), xlabel='Scheduled training tokens (thousands)')
        axis.grid(axis='y', alpha=.15)
    axes[0][0].set_ylabel('Retained selection success (%)')
    figure.suptitle(cohort['label'] + ' / resource accounting', fontsize=10)
    save(figure, directory, f'factory-{cohort["id"]}-budget')


def final_matrix(cohort, directory, recovered=False):
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap
    data = cohort['data']
    roles = final_rows(data, recovered=recovered)
    tasks = sorted(roles[0]['runs'][0]['evaluation']['expected_tasks'])
    columns = [(role, index, run) for role in roles for index, run in enumerate(role['runs'], 1)]
    matrix = []
    for task in tasks:
        values = []
        for _, _, run in columns:
            row = next((row for row in run['evaluation']['tasks'] if row['task'] == task), None)
            value = row.get('score') if row else None
            values.append(-1 if value is None or row.get('error_type') else int(value))
        matrix.append(values)
    figure, axis = plt.subplots(figsize=(7, 4.0), layout='constrained')
    axis.imshow(matrix, cmap=ListedColormap(['#e5e0d8', '#e8edf5', TEAL]), vmin=-1, vmax=1, aspect='auto')
    labels = []
    for role, repetition, _ in columns:
        label = 'Base student' if role['role'] == 'base' else next(campaign['researcher'] for campaign in data['campaigns'] if campaign['name'] == role['role']) + '\nselection'
        labels.append(label + f'\nR{repetition}' + (' / shared' if role['shared_base'] else ''))
    axis.set_xticks(range(len(columns)), labels, fontsize=7)
    axis.set_yticks(range(len(tasks)), [task.removeprefix('model6-').removeprefix('final-') for task in tasks], fontsize=8)
    axis.tick_params(length=0)
    for index, values in enumerate(matrix):
        for column, value in enumerate(values):
            axis.text(column, index, 'Unscored' if value == -1 else ('Pass' if value == 1 else 'Fail'), ha='center', va='center', color='white' if value == 1 else '#384353', fontsize=7)
    offset = 0
    for role in roles[:-1]:
        offset += len(role['runs'])
        axis.axvline(offset - .5, color='white', lw=3)
    view = 'Operational recovery / same task repetitions' if recovered else 'Original final outcomes / within this cohort'
    axis.set_title(cohort['label'] + '\n' + view, fontsize=10, pad=14)
    if recovered and cohort['id'] == 'original':
        axis.set_xlabel('Astra: Mac originals. Base and Sol: Linux full-suite replays.\nController platforms differ; these are descriptive outcomes, not an isolated training-data effect.', fontsize=7, labelpad=12)
    suffix = 'final-recovered-matrix' if recovered else 'final-matrix'
    save(figure, directory, f'factory-{cohort["id"]}-{suffix}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-dir', type=Path, default=ROOT / 'outputs')
    parser.add_argument('--out-dir', type=Path, default=ROOT / 'outputs')
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    publication = load_publication(args.source_dir)
    if args.check_only:
        print('Both cohorts passed figure gates; no figures written.')
        return
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 9, 'font.family': 'DejaVu Sans', 'axes.spines.top': False,
                         'axes.spines.right': False, 'svg.fonttype': 'none', 'pdf.fonttype': 42})
    directory = args.out_dir / 'figures'
    directory.mkdir(parents=True, exist_ok=True)
    pipeline(directory)
    for cohort in publication['cohorts']:
        trajectories(cohort, directory)
        budget(cohort, directory)
        final_matrix(cohort, directory)
        if has_recovery(cohort['data']):
            final_matrix(cohort, directory, recovered=True)
    write_bundle(publication, args.out_dir)
    print('Exported shared pipeline and separate cohort figures from completed audit evidence.')


if __name__ == '__main__':
    main()
