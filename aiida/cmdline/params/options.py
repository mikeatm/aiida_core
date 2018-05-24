# -*- coding: utf-8 -*-
import click

from . import types


class OverridableOption(object):
    """
    Wrapper around click option that increases reusability

    Click options are reusable already but sometimes it can improve the user interface to for example customize a
    help message for an option on a per-command basis. Sometimes the option should be prompted for if it is not given
    On some commands an option might take any folder path, while on another the path only has to exist.

    Overridable options store the arguments to click.option and only instanciate the click.Option on call,
    kwargs given to ``__call__`` override the stored ones.

    Example::

        FOLDER = OverridableOption('--folder', type=click.Path(file_okay=False), help='A folder')

        @click.command()
        @FOLDER(help='A folder, will be created if it does not exist')
        def ls_or_create(folder):
            click.echo(os.listdir(folder))

        @click.command()
        @FOLDER(help='An existing folder', type=click.Path(exists=True, file_okay=False, readable=True)
        def ls(folder)
            click.echo(os.listdir(folder))
    """

    def __init__(self, *args, **kwargs):
        """
        Store the default args and kwargs
        """
        self.args = args
        self.kwargs = kwargs

    def __call__(self, **kwargs):
        """
        Override the stored kwargs, (ignoring args as we do not allow option name changes) and return the option
        """
        kw_copy = self.kwargs.copy()
        kw_copy.update(kwargs)
        return click.option(*self.args, **kw_copy)


class MultipleValueOption(click.Option):
    """
    An option that can handle multiple values with a single flag. For example::

        @click.option('-n', '--nodes', cls=MultipleValueOption)

    Will be able to parse the following::

        --nodes 10 15 12

    This is better than the builtin ``multiple=True`` keyword for click's option which forces the user to specify
    the option flag for each value, which gets impractical for long lists of values
    """

    def __init__(self, *args, **kwargs):
        param_type = kwargs.pop('type', None)

        if param_type is not None:
            kwargs['type'] = types.MultipleValueParamType(param_type)

        super(MultipleValueOption, self).__init__(*args, **kwargs)
        self._previous_parser_process = None
        self._eat_all_parser = None

    def add_to_parser(self, parser, ctx):
        result = super(MultipleValueOption, self).add_to_parser(parser, ctx)

        def parser_process(value, state):
            ENDOPTS = '--'
            done = False
            value = [value]

            # Grab everything up to the next option or endopts symbol
            while state.rargs and not done:
                for prefix in self._eat_all_parser.prefixes:
                    if state.rargs[0].startswith(prefix) or state.rargs[0] == ENDOPTS:
                        done = True
                if not done:
                    value.append(state.rargs.pop(0))

            value = tuple(value)

            self._previous_parser_process(value, state)

        for name in self.opts:
            our_parser = parser._long_opt.get(name) or parser._short_opt.get(name)
            if our_parser:
                self._eat_all_parser = our_parser
                self._previous_parser_process = our_parser.process
                our_parser.process = parser_process
                break

        return result


CODE = OverridableOption('-X', '--code', 'code', type=types.CodeParam(),
    help='A single code identified by its ID, UUID or label')


CODES = OverridableOption('-X', '--codes', 'codes', cls=MultipleValueOption, type=types.CodeParam(),
    help='One or multiple codes identified by their ID, UUID or label')


COMPUTER = OverridableOption('-C', '--computer', 'computer', type=types.ComputerParam(),
    help='A single computer identified by its ID, UUID or label')


COMPUTERS = OverridableOption('-C', '--computers', 'computers', cls=MultipleValueOption, type=types.ComputerParam(),
    help='One or multiple computers identified by their ID, UUID or label')


GROUPS = OverridableOption('-G', '--group', 'group', type=types.GroupParam(),
    help='A single group identified by its ID, UUID or name')


GROUPS = OverridableOption('-G', '--groups', 'groups', cls=MultipleValueOption, type=types.GroupParam(),
    help='One or multiple groups identified by their ID, UUID or name')


NODES = OverridableOption('-N', '--node', 'node', type=types.NodeParam(),
    help='A single node identified by its ID or UUID')


NODES = OverridableOption('-N', '--nodes', 'nodes', cls=MultipleValueOption, type=types.NodeParam(),
    help='One or multiple nodes identified by their ID or UUID')