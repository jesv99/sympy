#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
A tool to generate AUTHORS. We started tracking authors before moving to git,
so we have to do some manual rearrangement of the git history authors in order
to get the order in AUTHORS. bin/mailmap_check.py should be run before
committing the results.

See here for instructions on using this script:
https://github.com/sympy/sympy/wiki/Development-workflow#update-mailmap
"""

from __future__ import unicode_literals
from __future__ import print_function

import sys
import os
from pathlib import Path
from subprocess import run, PIPE
from collections import OrderedDict, defaultdict
from argparse import ArgumentParser

if sys.version_info < (3, 7):
    sys.exit("This script requires Python 3.7 or newer")

def sympy_dir():
    return Path(__file__).resolve().parent.parent

# put sympy on the path
sys.path.insert(0, str(sympy_dir()))
import sympy
from sympy.utilities.misc import filldedent
from sympy.external.importtools import version_tuple


def main(*args):

    parser = ArgumentParser(description='Update the .mailmap and/or AUTHORS files')
    parser.add_argument('--update-authors', action='store_true',
            help=filldedent("""
            Also update the AUTHORS file. Note that it
            should only necessary for the release manager to do this as part of
            the release process for SymPy."""))
    args = parser.parse_args(args)

    if not check_git_version():
        return 1

    # find who git knows ahout
    try:
        git_people = get_authors_from_git()
    except AssertionError as msg:
        print(red(msg))
        return 1

    lines_mailmap = read_lines(mailmap_path())

    def key(line):
        # return lower case first address on line or
        # raise an error if not an entry
        if '#' in line:
            line = line.split('#')[0]
        L, R = line.count("<"), line.count(">")
        assert L == R and L in (1, 2)
        return line.split(">", 1)[0].split("<")[1].lower()

    who = OrderedDict()
    for i, line in enumerate(lines_mailmap):
        try:
            who.setdefault(key(line), []).append(line)
        except AssertionError:
            who[i] = [line]

    problems = False
    missing = False
    ambiguous = False
    dups = defaultdict(list)

    for person in git_people:
        email = key(person)
        dups[email].append(person)
        if email not in who:
            print(red("This author is not included in the .mailmap file:"))
            print(person)
            missing = True
        elif not any(p.startswith(person) for p in who[email]):
            print(red("Ambiguous names in .mailmap"))
            print(red("This email address appears for multiple entries:"))
            print('Person:', person)
            print('Mailmap entries:')
            for line in who[email]:
                print(line)
            ambiguous = True

    if missing:
        print(red(filldedent("""
        The .mailmap file needs to be updated because there are commits with
        unrecognised author/email metadata.
        """)))
        problems = True

    if ambiguous:
        print(red(filldedent("""
        Lines should be added to .mailmap to indicate the correct name and
        email aliases for all commits.
        """)))
        problems = True

    for email, commitauthors in dups.items():
        if len(commitauthors) > 2:
            print(red(filldedent("""
            The following commits are recorded with different metadata but the
            same/ambiguous email address. The .mailmap file will need to be
            updated.""")))
            for author in commitauthors:
                print(author)
            problems = True

    lines_mailmap_sorted = sort_lines_mailmap(lines_mailmap)
    write_lines(mailmap_path(), lines_mailmap_sorted)

    if lines_mailmap_sorted != lines_mailmap:
        problems = True
        print(red("The mailmap file was reordered"))

    if problems:
        print(red(filldedent("""
        For instructions on updating the .mailmap file see:
        https://github.com/sympy/sympy/wiki/Development-workflow#update-mailmap""")))
    else:
        print(green("No changes needed in .mailmap"))

    # Check if changes to AUTHORS file are also needed
    lines_authors = make_authors_file_lines(git_people)
    old_lines_authors = read_lines(authors_path())
    update_authors_file(lines_authors, old_lines_authors, args.update_authors)

    return int(problems)


def update_authors_file(lines, old_lines, update_yesno):

    if old_lines == lines:
        print(green('No changes needed in AUTHORS.'))
        return 0

    # Actually write changes to the file?
    if update_yesno:
        write_lines(authors_path(), lines)
        print(red("Changes were made in the authors file"))

    # check for new additions
    new_authors = []
    for i in sorted(set(lines) - set(old_lines)):
        try:
            author_name(i)
            new_authors.append(i)
        except AssertionError:
            continue

    if new_authors:
        if update_yesno:
            print(yellow("The following authors were added to AUTHORS."))
        else:
            print(green(filldedent("""
                The following authors will be added to the AUTHORS file at the
                time of the next SymPy release.""")))
        print()
        for i in sorted(new_authors, key=lambda x: x.lower()):
            print('\t%s' % i)


def check_git_version():
    # check git version
    minimal = '1.8.4.2'
    git_ver = run(['git', '--version'], stdout=PIPE, encoding='utf-8').stdout[12:]
    if version_tuple(git_ver) < version_tuple(minimal):
        print(yellow("Please use a git version >= %s" % minimal))
        return False
    else:
        return True


def authors_path():
    return sympy_dir() / 'AUTHORS'


def mailmap_path():
    return sympy_dir() / '.mailmap'


def red(text):
    return "\033[31m%s\033[0m" % text


def yellow(text):
    return "\033[33m%s\033[0m" % text


def green(text):
    return "\033[32m%s\033[0m" % text


def author_name(line):
    assert line.count("<") == line.count(">") == 1
    assert line.endswith(">")
    return line.split("<", 1)[0].strip()


def get_authors_from_git():
    git_command = ["git", "log", "--topo-order", "--reverse", "--format=%aN <%aE>"]
    git_people = run(git_command, stdout=PIPE, encoding='utf-8').stdout.strip().split("\n")

    # remove duplicates, keeping the original order
    git_people = list(OrderedDict.fromkeys(git_people))

    # Do the few changes necessary in order to reproduce AUTHORS:
    def move(l, i1, i2, who):
        x = l.pop(i1)
        # this will fail if the .mailmap is not right
        assert who == author_name(x), \
            '%s was not found at line %i' % (who, i1)
        l.insert(i2, x)

    move(git_people, 2, 0, 'Ondřej Čertík')
    move(git_people, 42, 1, 'Fabian Pedregosa')
    move(git_people, 22, 2, 'Jurjen N.E. Bos')
    git_people.insert(4, "*Marc-Etienne M.Leveille <protonyc@gmail.com>")
    move(git_people, 10, 5, 'Brian Jorgensen')
    git_people.insert(11, "*Ulrich Hecht <ulrich.hecht@gmail.com>")
    # this will fail if the .mailmap is not right
    assert 'Kirill Smelkov' == author_name(git_people.pop(12)
        ), 'Kirill Smelkov was not found at line 12'
    move(git_people, 12, 32, 'Sebastian Krämer')
    move(git_people, 227, 35, 'Case Van Horsen')
    git_people.insert(43, "*Dan <coolg49964@gmail.com>")
    move(git_people, 57, 59, 'Aaron Meurer')
    move(git_people, 58, 57, 'Andrew Docherty')
    move(git_people, 67, 66, 'Chris Smith')
    move(git_people, 79, 76, 'Kevin Goodsell')
    git_people.insert(84, "*Chu-Ching Huang <cchuang@mail.cgu.edu.tw>")
    move(git_people, 93, 92, 'James Pearson')
    # this will fail if the .mailmap is not right
    assert 'Sergey B Kirpichev' == author_name(git_people.pop(226)
        ), 'Sergey B Kirpichev was not found at line 226.'

    index = git_people.index(
        "azure-pipelines[bot] " +
        "<azure-pipelines[bot]@users.noreply.github.com>")
    git_people.pop(index)
    index = git_people.index(
        "whitesource-bolt-for-github[bot] " +
        "<whitesource-bolt-for-github[bot]@users.noreply.github.com>")
    git_people.pop(index)

    return git_people


def make_authors_file_lines(git_people):
    # define new lines for the file
    header = filldedent("""
        All people who contributed to SymPy by sending at least a patch or
        more (in the order of the date of their first contribution), except
        those who explicitly didn't want to be mentioned. People with a * next
        to their names are not found in the metadata of the git history. This
        file is generated automatically by running `./bin/authors_update.py`.
        """).lstrip()
    header_extra = f"There are a total of {len(git_people)} authors."""
    lines = header.splitlines()
    lines.append('')
    lines.append(header_extra)
    lines.append('')
    lines.extend(git_people)
    return lines


def sort_lines_mailmap(lines):
    for n, line in enumerate(lines):
        if not line.startswith('#'):
            header_end = n
            break
    header = lines[:header_end]
    mailmap_lines = lines[header_end:]
    return header + sorted(mailmap_lines)


def read_lines(path):
    with open(path) as fin:
        return [line.strip() for line in fin.readlines()]


def write_lines(path, lines):
    with open(path, 'w') as fout:
        fout.write('\n'.join(lines))
        fout.write('\n')


if __name__ == "__main__":
    import sys
    sys.exit(main(*sys.argv[1:]))
