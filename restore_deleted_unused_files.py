#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import tarfile
import argparse


def get_answer(default='Y'):
    answer = (input('[y/n]> '.replace(default.lower(), default)) or default).lower()
    if answer not in ['y', 'n']:
        return get_answer(default)
    return True if answer == 'y' else False


def restore_deleted_unused_files(restore_files_from_archive):
    with tarfile.open(restore_files_from_archive, mode='r:') as archive:
        print('Extracting files...')
        archive.extractall('/')
        print('All files extracted.')

if __name__ == '__main__':
    docroot = os.path.dirname(__file__)
    parser = argparse.ArgumentParser(
        description='''Restores unused files from archive created by delete_unused_files.py script'''
    )
    parser.add_argument('restore_files_from_archive', metavar='restore_files_from_archive', type=str, nargs=1,
                        help='Restores deleted files from archive created by this delete_unused_files.py script')
    params = parser.parse_args()
    restore_deleted_unused_files(params.restore_files_from_archive[0])
