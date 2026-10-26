#!/usr/bin/env python3
"""Plot distinct template keys per function from Fossil's analyzed outputs."""
import csv
import json
from pathlib import Path
import sys

from emit_recurrence import plotting


def main():
    plt = plotting()
    from matplotlib.ticker import PercentFormatter

    analyzed = json.load(sys.stdin)
    if not analyzed:
        sys.exit('No analyzed workloads to plot')
    variants = sorted(analyzed, key=lambda v:
                      analyzed[v]['template_recurrence_count']['mean'], reverse=True)
    bins = ('1', '2', '3', '4', '5-8', '9-16', '17+')
    colors = ('#e1edf3', '#b7d5df', '#80b5c5', '#4a93a9',
              '#27738d', '#18516f', '#102f4c')
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    fig, ax = plt.subplots(figsize=(9, 2.4 + 0.48 * len(variants)))
    data = {v: {key: analyzed[v][key] for key in
                ('template_multiplicity', 'templates_per_function')} for v in variants}
    for y, variant in enumerate(variants):
        metrics = data[variant]['template_multiplicity']
        left = 0
        for i, (bucket, color) in enumerate(zip(bins, colors)):
            width = 100 * metrics['shares'][bucket]['mean']
            ax.barh(y, width, left=left, height=0.6, color=color,
                    label=bucket.replace('-', '–') if y == 0 else None)
            if width >= 5:
                ax.text(left + width / 2, y, f'{width:.1f}%', ha='center',
                        va='center', fontsize=8, color='#20333e' if i < 3 else 'white')
            left += width
        ax.text(102, y, f"{metrics['functions']['mean']:,.0f} functions; "
                f"max {metrics['max']['mean']:g}", va='center', fontsize=8)
    ax.set(yticks=range(len(variants)),
           yticklabels=[v + (' (recorded)' if v == 'navbench' else '') for v in variants],
           xlim=(0, 132), xticks=range(0, 101, 20), xlabel='Share of distinct guest functions',
           title='Distinct Ion template keys per function')
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.spines['bottom'].set_bounds(0, 100)
    ax.legend(title='Distinct template keys', loc='upper center',
              bbox_to_anchor=(0.4, -0.17), ncol=len(bins), frameon=False,
              fontsize=9, handlelength=1.2, columnspacing=1)
    fig.text(0.02, 0.025,
             'One vote per function fingerprint; template keys are deduplicated across all guest compilations in each session.\n'
             'When multiple observations are selected, shares, function totals, and per-session maxima are averaged.',
             fontsize=8, color='#4f5b60')
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    for extension in ('pdf', 'png'):
        fig.savefig(output / f'template-distribution.{extension}', dpi=160, facecolor='white')
    plt.close(fig)
    (output / 'template-distribution.json').write_text(json.dumps(data, indent=2) + '\n')
    with (output / 'templates-per-function.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['variant', 'function_hash', 'distinct_templates_mean',
                         'distinct_templates_stddev'])
        for variant in variants:
            for function, count in data[variant]['templates_per_function'].items():
                writer.writerow([variant, function, count['mean'], count['stddev']])


if __name__ == '__main__':
    main()
