import argparse

from foc import *

from lot.lot import *


class _help_formatter(argparse.HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=30)

    def _format_usage(self, *args):
        return "Usage: lot [options] FILE\n"


def main():
    __version__ = "0.1.0"

    parser = argparse.ArgumentParser(
        prog="lot",
        formatter_class=_help_formatter,
        add_help=False,
    )
    parser.add_argument("FILE", nargs="?", help="Input FILE to process")
    parser.add_argument(
        "-h",
        "--help",
        action="help",
        default=argparse.SUPPRESS,
        help="Help for lot",
    )
    parser.add_argument(
        "-c",
        "--cal",
        action="store_true",
        help="Print in calendar",
    )
    parser.add_argument(
        "-a",
        "--actor",
        action="store_true",
        help="Print with actors as key",
    )
    parser.add_argument(
        "-n",
        "--node",
        action="store_true",
        help="Print with nodes as key",
    )
    parser.add_argument(
        "-y",
        "--year",
        type=int,
        metavar="INT",
        help="Set the year",
    )
    parser.add_argument(
        "-m",
        "--month",
        type=int,
        metavar="INT",
        help="Set the month",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        metavar="FILE",
        help="Save to spreadsheet FILE",
    )
    parser.add_argument(
        "-u",
        "--ubound",
        type=int,
        metavar="INT",
        help="Set upper limit of acts",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Increase verbosity"
    )
    parser.add_argument(
        "-V",
        "--version",
        action="store_true",
        help="Show version information",
    )

    args = parser.parse_args()
    if args.version:
        error(f"lot version is {__version__}")
    if args.FILE is None:
        parser.print_help()
    else:
        solve(args)


if __name__ == "__main__":
    main()
