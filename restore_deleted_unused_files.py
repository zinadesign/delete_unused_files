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
        def is_within_directory(directory, target):
            
            abs_directory = os.path.abspath(directory)
            abs_target = os.path.abspath(target)
        
            prefix = os.path.commonprefix([abs_directory, abs_target])
            
            return prefix == abs_directory
        
        def safe_extract(tar, path=".", members=None, *, numeric_owner=False):
        
            for member in tar.getmembers():
                member_path = os.path.join(path, member.name)
                if not is_within_directory(path, member_path):
                    raise Exception("Attempted Path Traversal in Tar File")
        
            tar.extractall(path, members, numeric_owner=numeric_owner) 
            
        
        safe_extract(archive, "/")
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
