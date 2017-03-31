#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import MySQLdb
from _mysql_exceptions import ProgrammingError
import tarfile
import argparse
from pytz import timezone
from datetime import datetime
from six.moves import input
from uuid import uuid4


def get_answer(default='Y'):
    answer = (input('[y/n]> '.replace(default.lower(), default)) or default).lower()
    if answer not in ['y', 'n']:
        return get_answer(default)
    return True if answer == 'y' else False


def delete_unused_files(db_name, db_host, db_username,db_password, find_unused_at_directories=[],
                        find_usages_at_directories=[], verbose=False):
    for dir_path in find_usages_at_directories:
        assert (dir_path not in find_unused_at_directories), "Directories find_unused and find_usages is different"
        for dir_path2 in find_unused_at_directories:
            assert (dir_path not in dir_path2), "Directories find_usages is not subdirectory of find_unused"

    conn = MySQLdb.connect(host=db_host, user=db_username,
                           passwd=db_password, db=db_name)
    cursor = conn.cursor()
    conn.cursor()
    cursor.execute('SHOW TABLES')
    table_info = {}
    index_table_name = 'delete_unsed_files_script_index_{0}'.format(uuid4().hex)
    for raw in cursor.fetchall():
        table_name = raw[0]
        table_info[table_name]  = []
        cursor.execute('SHOW COLUMNS FROM {0}'.format(table_name))
        for raw in cursor.fetchall():
            column_type_is_supported = False
            column_type = raw[1].upper()
            for t in ['CHAR', 'VARCHAR', 'BINARY', 'VARBINARY', 'BLOB', 'TEXT', 'ENUM', 'SET']:
                if t in column_type:
                    column_type_is_supported = True
                    break
            if column_type_is_supported is False:
                continue
            table_info[table_name].append(raw[0])
    index_is_build = False

    def build_index():
        index_is_build = True
        textchars = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)) - {0x7f})
        is_binary_string = lambda bytes: bool(bytes.translate(None, textchars))
        cursor.execute('''
                CREATE TABLE `{0}` (
                  `{1}` varchar(1024) NOT NULL
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
                '''.format(index_table_name, 'word'))
        conn.commit()
        cursor.execute('''
          ALTER TABLE `{0}` ADD UNIQUE KEY `word` (`word`(150))
        '''.format(table_name))

        for dir_path in find_usages_at_directories:
            for root, subdirs, files in os.walk(dir_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    with open(file_path, 'rb') as f:
                        if is_binary_string(f.read(1024)) is False:
                            continue
                        f.seek(0)
                        for line in f:
                            for word in line.split():
                                pass


    def is_file_used(f_name):
        if index_is_build is False:
            build_index()
        return True

    def is_file_used_at_directories(f_name):
        for dir_path in find_usages_at_directories:
            for root, subdirs, files in os.walk(dir_path):
                for filename in files:
                    file_path = os.path.join(root, filename)
                    with open(file_path, 'rb') as f:
                        for line in f:
                            if f_name in line:
                                return True
        return False

    def is_file_used_at_db(f_name):
        for table_name, fields in table_info.items():
            query = 'SELECT "none" as none FROM {0} WHERE {1}'.format(table_name, ' OR '.join(['`{0}` LIKE "%{1}%"'.format(field_name, f_name) for field_name in fields]))
            try:
                cursor.execute(query)
            except ProgrammingError as e:
                print(query)
                raise
            if cursor.fetchone() is not None:
                return True
        return False

    files_to_delete = []

    for dir_path in find_unused_at_directories:
        for root, subdirs, files in os.walk(dir_path):
            for filename in files:
                if is_file_used_at_directories(filename) is False and is_file_used_at_db(filename) is False:
                    file_path = os.path.realpath(os.path.join(root, filename))
                    print('file: {0} marked for deletion'.format(file_path))
                    files_to_delete.append(file_path)
    total_files_deleted = 0
    total_bytes_freed = 0
    archive_path = ''
    if len(files_to_delete) > 0:
        print('Delete this files?')
        if verbose is False or get_answer(default=''):
            archive_path = os.path.join(os.path.dirname(__file__), 'deleted_unused_files_{0}.tar'.format(datetime.now(tz=timezone('Europe/Kiev')).strftime('%Y-%m-%dT%H:%M')))
            with tarfile.open(archive_path, mode='w:') as archive:
                for file_path in files_to_delete:
                    total_bytes_freed += os.path.getsize(file_path)
                    archive.add(file_path)
                    os.unlink(file_path)
                    total_files_deleted += 1
            print('We put all deleted files in archive {0}. You can restore deleted files by command {1}'.format(archive_path, ''))
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
    parser.print_help()
    params = parser.parse_args()
    print('Notification read carefully?')
    if get_answer(default='Y'):
        total_files_deleted, total_bytes_freed, archive_path = delete_unused_files(params.db_name[0], params.db_host[0], params.db_username[0],
                                                                     params.db_password[0], params.find_unused_at_directories,
                                                                     params.find_usages_at_directories, verbose=True)
        print('Total:\nmb freed {0}\nfiles deleted {1}\n'.format(total_bytes_freed / 1024 / 1024, total_files_deleted))
