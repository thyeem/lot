import argparse

from foc import *

from lot.lot import *

__version__ = "0.1.0"


class _help_formatter(argparse.HelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, max_help_position=30)

    def _format_usage(self, *args):
        return "Usage: lot [options] FILE\n"


def main():

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
        help="Print sorted by actor",
    )
    parser.add_argument(
        "-n",
        "--node",
        action="store_true",
        help="Print sorted by node",
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
        help="Save as spreadsheet FILE",
    )
    parser.add_argument(
        "-A",
        "--max-it",
        type=int,
        metavar="INT",
        help="Set maximum number of iteration",
    )
    parser.add_argument(
        "-R",
        "--min-rest",
        type=int,
        metavar="INT",
        help="Set minimum number of rest",
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
        try:
            solve(args)
        except ParseError as e:
            print(e)
        except Exception as e:
            print(e)


if __name__ == "__main__":
    main()
