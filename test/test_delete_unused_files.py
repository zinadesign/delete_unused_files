# -*- coding: utf-8 -*-
import os
import unittest
from uuid import uuid4
import subprocess
import MySQLdb
from delete_unused_files import delete_unused_files
from restore_deleted_unused_files import restore_deleted_unused_files


class Test(unittest.TestCase):
    DOCROOT = os.path.join(os.path.dirname(__file__))
    db_name = 'unittest_{0}'.format(uuid4().hex)
    db_host = os.environ.get('DB_HOST', 'localhost')
    db_username = os.environ.get('DB_USERNAME', 'root')
    db_password = os.environ.get('DB_PASSWORD', 'ujnbrf')
    data_dir = os.path.join(DOCROOT, 'data/files')
    code_dir = os.path.join(DOCROOT, 'data/code_dir')
    cursor = None
    db_connection = None
    table_name = uuid4().hex

    @classmethod
    def setUpClass(cls):
        cls.db_connection = MySQLdb.connect(host=cls.db_host, user=cls.db_username,
                     passwd=cls.db_password)
        cls.cursor = cls.db_connection.cursor(MySQLdb.cursors.DictCursor)
        cls.cursor.execute('CREATE DATABASE {0} DEFAULT CHARACTER SET utf8 DEFAULT COLLATE utf8_general_ci'.format(cls.db_name))
        cls.db_connection.commit()
        cls.cursor.execute('USE {0}'.format(cls.db_name))
        cls.cursor.execute('''
        CREATE TABLE `{0}` (
          `{1}` varchar(255) NOT NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
        '''.format(cls.table_name, uuid4().hex))
        cls.db_connection.commit()
        subprocess.call(['mkdir', '-p', cls.data_dir])
        subprocess.call(['mkdir', '-p', cls.code_dir])

    def test_unused_file_is_deleted(self):
        dir_path = os.path.join(self.data_dir, '{0}/{1}/{2}/{3}'.format(uuid4().hex, uuid4().hex, uuid4().hex, uuid4().hex))
        subprocess.call(['mkdir', '-p', dir_path])
        unused_file = os.path.join(dir_path, 'unused_file_{0}'.format(uuid4().hex))
        with open(unused_file, 'w') as f:
            f.write('some data')
            f.close()
        used_file = os.path.join(dir_path, 'used_file_{0}'.format(uuid4().hex))
        with open(used_file, 'w') as f:
            f.write('some data')
            f.close()
        used_file_in_db = os.path.join(dir_path, 'used_file_in_db_{0}'.format(uuid4().hex))
        with open(used_file_in_db, 'w') as f:
            f.write('some data')
            f.close()
        self.cursor.execute('INSERT INTO `'+ self.table_name +'` VALUES (%s)',
                            ['test<img src="{0}" />test'.format(os.path.basename(used_file_in_db))]
        )
        self.db_connection.commit()
        used_in_file = os.path.join(self.code_dir, '{0}/{1}/used_in_file_{2}'.format(uuid4().hex, uuid4().hex, uuid4().hex))
        subprocess.call(['mkdir', '-p', os.path.dirname(used_in_file)])
        with open(used_in_file, 'w') as f:
            f.write('''
            sdkfksdkf\n
            sdkfksdkf\n
            dskkd<img src="{0}" />fksdkf\n
            sdiofiosdiof\n
            '''.format(os.path.basename(used_file)))
            f.close()
        file_count = int(subprocess.Popen('find {0} -type f | wc -l'.format(self.data_dir), stdout=subprocess.PIPE, shell=True).stdout.read())
        self.assertRaises(AssertionError, delete_unused_files, db_name=self.db_name, db_host=self.db_host, db_username=self.db_username,
                            db_password=self.db_password,
                            find_unused_at_directories=[self.data_dir], find_usages_at_directories=[self.data_dir])

        self.assertRaises(AssertionError, delete_unused_files, db_name=self.db_name, db_host=self.db_host,
                          db_username=self.db_username,
                          db_password=self.db_password,
                          find_unused_at_directories=[self.data_dir, 'subdir'], find_usages_at_directories=[self.data_dir])

        delete_unused_files(db_name=self.db_name, db_host=self.db_host, db_username=self.db_username,
                            db_password=self.db_password,
                            find_unused_at_directories=[self.data_dir], find_usages_at_directories=[self.code_dir])
        file_count_after_deletion = int(subprocess.Popen('find {0} -type f | wc -l'.format(self.data_dir), stdout=subprocess.PIPE, shell=True).stdout.read())
        self.assertFalse(os.path.exists(unused_file), 'Check unused file is deleted')
        print(file_count, file_count_after_deletion)
        self.assertEqual(file_count - 1, file_count_after_deletion, 'Check that only unused file is deleted')

    def test_restore_deleted_unused_files(self):
        unused_file = os.path.join(self.data_dir, 'unused_file_{0}'.format(uuid4().hex))
        with open(unused_file, 'w') as f:
            f.write('some data')
            f.close()
        file_count = int(subprocess.Popen('find {0} -type f | wc -l'.format(self.data_dir), stdout=subprocess.PIPE,
                                          shell=True).stdout.read())
        total_files_deleted, total_bytes_freed, archive_path = delete_unused_files(
            db_name=self.db_name, db_host=self.db_host, db_username=self.db_username,
            db_password=self.db_password,
            find_unused_at_directories=[self.data_dir], find_usages_at_directories=[self.code_dir])
        restore_deleted_unused_files(archive_path)
        file_count_after_restore = int(subprocess.Popen('find {0} -type f | wc -l'.format(self.data_dir),
                                                        stdout=subprocess.PIPE, shell=True).stdout.read())
        self.assertEqual(file_count, file_count_after_restore, 'Check that file count before deletion equals file count after deletion')
        self.assertTrue(os.path.isfile(unused_file), 'Check that previously deleted file exists')
        delete_unused_files(
            db_name=self.db_name, db_host=self.db_host, db_username=self.db_username,
            db_password=self.db_password,
            find_unused_at_directories=[self.data_dir], find_usages_at_directories=[self.code_dir])



    @classmethod
    def tearDownClass(cls):
        cls.cursor.execute(
            'DROP DATABASE {0}'.format(cls.db_name))
        cls.db_connection.commit()
        subprocess.call('rm -rf {0}'.format(os.path.join(cls.data_dir, '*')), shell=True)
        subprocess.call('rm -rf {0}'.format(os.path.join(cls.code_dir, '*')), shell=True)



if __name__ == '__main__':
    unittest.main()