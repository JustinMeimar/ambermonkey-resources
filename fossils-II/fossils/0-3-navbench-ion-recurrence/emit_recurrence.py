#!/usr/bin/env python3
"""Plot count recurrence from Fossil's analyzed JSON on stdin."""
import json
import os
from pathlib import Path
import sys
import tempfile
import textwrap


SITES = {
    'navbench': 'Google, Facebook, Yahoo, Amazon, BBC News, DuckDuckGo, Google Docs, Wikipedia.',
    'workspace-shuffle': 'Google Docs, Sheets, and Slides.',
    'media-pinball': 'Bluesky and Substack.',
    'wiki-rabbit-hole': 'Wikipedia articles on fractals and complex dynamics.',
    'cake-quest': "Sally’s Baking Addiction, Preppy Kitchen, and King Arthur Baking recipes.",
    'compiler-coffee': 'V8 blog and Dan Luu articles.',
    'debugging-detour': 'MDN JavaScript documentation and MDN content issues on GitHub.',
    'headline-hop': 'BBC News, The Guardian, and NASA.',
    'comparison-cart': 'Amazon Canada, RTINGS, and Best Buy Canada headphone searches/reviews.',
    'weekend-wayfinder': 'Google Maps, Wikipedia, Fairmont, and Banff & Lake Louise Tourism.',
    'paper-trail': 'arXiv abstracts and ar5iv full texts for the Attention and BERT papers.',
}


def plotting():
    project = Path(__file__).resolve().parents[2]
    python = project / '.venv/bin/python'
    if Path(sys.prefix).resolve() != python.parent.parent.resolve():
        if not python.is_file():
            sys.exit(f'Install figure dependencies: uv sync --project {project}')
        os.execv(python, [str(python), *sys.argv])
    os.environ.setdefault('MPLCONFIGDIR', str(
        Path(tempfile.gettempdir()) / 'ambermonkey-oopsla-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    return plt


def main():
    plt = plotting()
    from matplotlib.ticker import PercentFormatter

    metrics = ('function_recurrence_count', 'template_recurrence_count')
    analyzed = json.load(sys.stdin)
    data = {variant: {key: values[key] for key in metrics}
            for variant, values in analyzed.items()}
    if not data:
        sys.exit('No analyzed workloads to plot')
    variants = sorted(data, key=lambda v: data[v][metrics[1]]['mean'], reverse=True)
    plt.rcParams.update({'font.size': 10, 'pdf.fonttype': 42,
                         'axes.spines.top': False, 'axes.spines.right': False})
    caption = '\n'.join(textwrap.fill(f'{v}: {SITES[v]}', width=108,
                                      subsequent_indent='    ') for v in variants)
    caption_height = 0.18 * len(caption.splitlines()) + 0.25
    figure_height = 1.3 + 0.65 * len(variants) + caption_height
    fig, ax = plt.subplots(figsize=(8, figure_height))
    for metric, label, color, offset in zip(
            metrics, ('Function', 'Template'), ('#4675a5', '#087f75'), (-0.18, 0.18)):
        means = [100 * data[v][metric]['mean'] for v in variants]
        deviations = [100 * data[v][metric]['stddev'] for v in variants]
        bars = ax.barh([i + offset for i in range(len(variants))], means,
                       height=0.32, color=color, label=label,
                       xerr=deviations if any(deviations) else None,
                       error_kw={'elinewidth': 1, 'capsize': 2})
        ax.bar_label(bars, labels=[f'{value:.1f}%' for value in means],
                     padding=4, fontsize=9)
    ax.set(yticks=range(len(variants)),
           yticklabels=[v + (' (recorded)' if v == 'navbench' else '') for v in variants],
           xlim=(0, 100), xlabel='Share of guest Ion compilations',
           title='Ion compilation recurrence')
    ax.invert_yaxis()
    ax.xaxis.set_major_formatter(PercentFormatter())
    ax.set_axisbelow(True)
    ax.grid(axis='x', alpha=0.18)
    ax.legend(loc='lower right', frameon=False)
    fig.text(0.02, 0.02, caption, fontsize=8, color='#4f5b60',
             va='bottom', linespacing=1.5)
    fig.tight_layout(rect=(0, caption_height / figure_height, 1, 1))
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    for extension in ('pdf', 'png'):
        fig.savefig(output / f'recurrence.{extension}', dpi=160, facecolor='white')
    plt.close(fig)
    (output / 'recurrence.json').write_text(json.dumps(data, indent=2) + '\n')


if __name__ == '__main__':
    main()
