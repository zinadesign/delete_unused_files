#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import MySQLdb
from _mysql_exceptions import ProgrammingError
import tarfile
import argparse
import re
import progressbar
import codecs
from progressbar.utils import get_terminal_size
from pytz import timezone
from datetime import datetime
import six
from six.moves import input, range
from binaryornot.check import is_binary


def get_answer(default='Y'):
    answer = (input('[y/n]> '.replace(default.lower(), default)) or default).lower()
    if answer not in ['y', 'n']:
        return get_answer(default)
    return True if answer == 'y' else False


def delete_unused_files(db_name, db_host, db_username,db_password, find_unused_at_directories=[],
                        find_usages_at_directories=[], verbose=False, exclude_tables=[]):
    for dir_path in find_usages_at_directories:
        assert (dir_path not in find_unused_at_directories), "Directories find_unused and find_usages is different"
        for dir_path2 in find_unused_at_directories:
            assert (dir_path not in dir_path2), "Directories find_usages is not subdirectory of find_unused"

    conn = MySQLdb.connect(host=db_host, user=db_username,
                           passwd=db_password, db=db_name, charset='utf8')
    cursor = conn.cursor()
    conn.cursor()
    cursor.execute('SHOW TABLES')
    table_info = {}
    for raw in cursor.fetchall():
        table_name = raw[0]
        if table_name in exclude_tables:
            continue
        table_info[table_name]  = []
        cursor.execute('SHOW COLUMNS FROM `{0}`'.format(table_name))
        for raw in cursor.fetchall():
            column_type_is_supported = False
            column_type = raw[1].upper()
            for t in ['CHAR', 'VARCHAR', 'BINARY', 'VARBINARY', 'BLOB', 'TEXT', 'ENUM', 'SET']:
                if t in column_type:
                    column_type_is_supported = True
                    break
            if column_type_is_supported:
                table_info[table_name].append(raw[0])
    pattern = re.compile('[^\w\-\.\(\)=\+\!\~\#\[\]\,\%\`\&\;\:]+', re.UNICODE)
    def get_unique_words():
        all_words = {}
        print('Making search index for files...')
        for dir_path in find_usages_at_directories:
            for root, subdirs, files in os.walk(dir_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    with open(file_path, 'rb') as f:
                        if is_binary(file_path):
                            continue
                        f.seek(0)
                        for line in f:
                            line = line.decode('utf-8')
                            line = line.rstrip("\n")
                            words = pattern.sub(' ', line).split()
                            for w in words:
                                all_words[w] = None
        print('Making search index for db...')
        for table_name, fields in table_info.items():
            if len(fields) == 0:
                continue
            print('Indexing table %s' % table_name)
            count_query = 'SELECT COUNT(*) FROM  `{0}`'.format(table_name)
            cursor.execute(count_query)
            total_records = int(cursor.fetchone()[0])
            if total_records == 0:
                continue
            bar = progressbar.ProgressBar(max_value=total_records)
            limit = 1000
            current_idx = -1
            for offset in range(0, total_records, limit):
                query = '''SELECT {0} FROM  `{1}` LIMIT {2},{3}'''.format(
                    ','.join(['`%s`' % field_name for field_name in fields]),
                    table_name,
                    offset,
                    limit
                )
                cursor.execute(query)
                while True:
                    row = cursor.fetchone()
                    if row is None:
                        break
                    current_idx += 1
                    bar.update(current_idx)
                    for content in row:
                        if content is None:
                            continue
                        words = pattern.sub(' ', content).split()
                        for w in words:
                            all_words[w] = None
            bar.finish()
        return all_words

    unique_words_in_project = get_unique_words()

    def is_file_used(f_name):
        return f_name.decode('utf-8') in unique_words_in_project

    files_to_delete = []

    for dir_path in find_unused_at_directories:
        for root, subdirs, files in os.walk(dir_path):
            for filename in files:
                if len(pattern.findall(filename.decode('utf-8'))) > 0:
                    print('Skip {0} due filename contains not allowed characters'.format(filename))
                    continue
                if filename in ['.htaccess', '.gitkeep', '.gitignore']:
                    print('Skip {0} due is special file used by external applications'.format(filename))
                    continue
                if is_file_used(filename) is False:
                    file_path = os.path.realpath(os.path.join(root, filename))
                    files_to_delete.append(file_path)
    files_to_delete_count = len(files_to_delete)
    current_time = datetime.now(tz=timezone('Europe/Kiev'))

    if files_to_delete_count > 0 and files_to_delete_count <= get_terminal_size()[1]:
        for file_path in files_to_delete:
            print('file: {0} marked for deletion'.format(file_path))

    elif files_to_delete_count > 0:
        logfile_path = os.path.realpath(os.path.join(os.path.dirname(__file__), 'deleted_unused_files_{0}.log'.format(current_time.strftime('%Y-%m-%dT%H:%M'))))
        with open(logfile_path, 'w') as f:
            for file_path in files_to_delete:
                f.write('file: {0} marked for deletion\n'.format(file_path))
        print('''We put list of files marked for deletion at \n
        log file {0} due it is too big to print.\n
         Please read it first and then confirm deletion'''.format(logfile_path))




    total_files_deleted = 0
    total_bytes_freed = 0
    archive_path = ''
    if len(files_to_delete) > 0:
        print('Delete this files?')
        if verbose is False or get_answer(default=''):
            archive_path = os.path.realpath(os.path.join(os.path.dirname(__file__), 'deleted_unused_files_{0}.tar'.format(current_time.strftime('%Y-%m-%dT%H:%M'))))
            bar = progressbar.ProgressBar(max_value=len(files_to_delete))
            print('Making backup')
            with tarfile.open(archive_path, mode='w:') as archive:
                for idx, file_path in enumerate(files_to_delete):
                    archive.add(file_path)
                    bar.update(idx + 1)
            bar.finish()
            print('Deleting files')
            bar = progressbar.ProgressBar(max_value=len(files_to_delete))
            for idx, file_path in enumerate(files_to_delete):
                total_bytes_freed += os.path.getsize(file_path)
                os.unlink(file_path)
                total_files_deleted += 1
                bar.update(idx + 1)
            bar.finish()
            restore_command = 'python {0} {1}'.format(
                os.path.realpath(os.path.join(os.path.dirname(__file__), 'restore_deleted_unused_files.py')),
                archive_path
            )
            print('We put all deleted files in archive {0}.\nYou can restore deleted files by command "{1}"'.format(archive_path, restore_command))
    return total_files_deleted, total_bytes_freed, archive_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='''Deletes unused files.\n
    Notification!!!\n\n
    Do not use it for files that are used by external applications for example php files\n
    (it used by apache and we can not determine it used or not)\n
    Use it only on files that reference can be found by file name in mysql database or project code.\n

    Usage example:
     ./delete_unused_files.py --db_name test --db_host localhost --db_username root --db_password ujnbrf --find_unused_at_directories /home/shmel/projects/hearts-in-love/assets/files --find_usages_at_directories /home/shmel/projects/hearts-in-love
    ''')
    parser.add_argument('--db_name', type=str, metavar='db_name', help='Database name', nargs=1, required=True)
    parser.add_argument('--db_host', type=str, metavar='db_host', help='Database host', nargs=1, required=True)
    parser.add_argument('--db_username', type=str, metavar='db_username', help='Database user', nargs=1, required=True)
    parser.add_argument('--db_password', type=str, metavar='db_password', help='Database user password', nargs=1, required=True)
    parser.add_argument('--find_unused_at_directories', type=str, metavar='find_unused_at_directories', nargs='+',
                        help='Find unused files at directories', required=True)
    parser.add_argument('--find_usages_at_directories', type=str, metavar='find_usages_at_directories', nargs='+',
                        help='Find file usages at directories', required=True)
    parser.add_argument('--exclude_tables', type=str, metavar='exclude_tables', nargs='+',
                        help='List of tables to skip search in', required=False, default=[])

    parser.print_help()
    params = parser.parse_args()
    print('Notification read carefully?')
    if get_answer(default='Y'):
        total_files_deleted, total_bytes_freed, archive_path = delete_unused_files(params.db_name[0], params.db_host[0], params.db_username[0],
                                                                     params.db_password[0], params.find_unused_at_directories,
                                                                     params.find_usages_at_directories, verbose=True, exclude_tables=params.exclude_tables)
        print('Total:\nmb freed {0}\nfiles deleted {1}\n'.format(total_bytes_freed / 1024 / 1024, total_files_deleted))
