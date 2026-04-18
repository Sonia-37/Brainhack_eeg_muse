#!/usr/bin/env python
# from the tip: https://stackoverflow.com/questions/18734739/using-ipython-jupyter-notebooks-under-version-control
# from: https://github.com/ivanov/nbutils/blob/master/nbstrip.py
# usage: nbstrip.py FILE.ipynb  # will strip the outputs *in place*

"""
Clear outputs of IPython notebooks.

By default, it prints the notebooks without outputs into stdout.
When the --in-place option is given, all files will be overwritten.

"""

import sys

#from IPython.nbformat import current as nbformat
import nbformat




def clear_outputs(nb):
    """Clear output of notebook `nb` INPLACE."""
    for ws in nb.worksheets:
        for cell in ws.cells:
            cell.outputs = []


def stripoutput(inputs, inplace=False):
    """
    Strip output of notebooks.

    Parameters
    ----------
    inputs : list of string
        Path to the notebooks to be processed.
    inplace : bool
        If this is `True`, outputs in the input files will be deleted.
        Default is `False`.

    """
    for inpath in inputs:
        with open(inpath) as fp:
            nb = nbformat.read(fp, 'ipynb')
        clear_outputs(nb)
        if inplace:
            with open(inpath, 'w') as fp:
                nbformat.write(nb, fp, 'ipynb')
        else:
            nbformat.write(nb, sys.stdout, 'ipynb')


def main():
    from argparse import ArgumentParser
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('inputs', nargs='+', metavar='input',
                        help='Paths to notebook files.')
    #XXX: TODO: handle alternative outputs here, such as to stdout or to file
    parser.add_argument('-i', '--inplace', '--in-place', default=True,
            action='store_true', 
            help='Overwrite existing notebook when given.')

    args = parser.parse_args()
    stripoutput(**vars(args))


if __name__ == '__main__':
    main()
