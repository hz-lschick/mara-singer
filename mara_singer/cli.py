"""Command line interface for running singer default pipelines"""

import sys
import click

from mara_app.monkey_patch import patch
from mara_pipelines import pipelines
import mara_pipelines.ui.cli

from .pipeline import _internal_root_pipeline


@click.command()
@click.option('--tap-name', required=True,
              help='The tap name, e.g. tap-exchangeratesapi')
@click.option('--disable-colors', default=False, is_flag=True,
              help='Output logs without coloring them.')
def discover(tap_name, disable_colors: bool = False):
    """Run discover for a singer tap"""

    patch(mara_pipelines.config.root_pipeline)(lambda: _internal_root_pipeline())

    # the pipeline to run
    pipeline, found = pipelines.find_node(['_singer',tap_name.replace('-','_')])
    if not found:
        print(f'Could not find pipeline. You have to add {tap_name} to config mara_singer.config.tap_names to be able to use this command', file=sys.stderr)
        sys.exit(-1)
    if not isinstance(pipeline, pipelines.Pipeline):
        print(f'Internal error: Note is not a pipeline, but a {pipeline.__class__.__name__}', file=sys.stderr)
        sys.exit(-1)

    # a list of nodes to run selectively in the pipeline
    nodes = set()
    nodes.add(pipeline.nodes.get('discover'))

    if not mara_pipelines.ui.cli.run_pipeline(pipeline, nodes, interactively_started=False, disable_colors=disable_colors):
        sys.exit(-1)
