#!/usr/bin/python

import os
import sys
import time
import getopt
import sqlite3

start = -1
end = -1

optlist,args = getopt.getopt(sys.argv[1:], 'f', ['start=','end='])
options = dict(optlist)
force = '-f' in options

if '--start' in options:
	start = int(options['--start'])
if '--end' in options:
	end = int(options['--end'])

if len(args) < 1:
	sys.stderr.write('%s --start=timestamp --end=timestamp <HappyFace Database file>\n' % sys.argv[0])
	sys.exit(-1)

dirname = os.path.dirname(args[0])
dbname = os.path.basename(args[0])
if not dirname:
    dirname = '.'

conn = sqlite3.connect(dirname + '/' + dbname)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Get list of tables in database
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
rows = cursor.fetchall()
#n_rows = cursor.rowcount
n_rows = len(rows)
row_index = 0

for row in rows:
	table_name = row['name']

	# Construct WHERE clause to query the data in the specified range
	start_cond = ''
	end_cond = ''
	if start >= 0:
		start_cond = 'timestamp>=%d' % start
	if end >= 0:
		end_cond = 'timestamp<=%d' % end

	where_clause = ''
	if start_cond and end_cond:
		where_clause = 'WHERE %s AND %s' % (start_cond, end_cond)
	elif start_cond:
		where_clause = 'WHERE %s' % start_cond
	elif end_cond:
		where_clause = 'WHERE %s' % end_cond

	sub_cursor = conn.cursor()
	sub_cursor.execute('SELECT * FROM "%s" %s' % (table_name, where_clause))

	# Get list of columns
	columns = map(lambda x: x[0], sub_cursor.description)
	# Filter non-filename columns
	columns = filter(lambda x: x.startswith('filename') or x == 'eff_plot' or x == 'rel_eff_plot', columns)

	row_index += 1
	sys.stdout.write('%d/%d: %s... ' % (row_index, n_rows, table_name))
	sys.stdout.flush()

	try:
		if not columns:
			sys.stdout.write('contains no filename entries\n')
			continue

		n_entries = 0
		n_converted_entries = 0
		for sub_row in sub_cursor:
			n_entries += len(columns)

			timestamp = sub_row['timestamp']
			tm = time.localtime(timestamp)

			year = str(tm.tm_year)
			month = '%02d' % tm.tm_mon
			day = '%02d' % tm.tm_mday

			for column in columns:
				# Only process files which contain "archive". If they
				# do not then most likely they are already stored
				# in new format.
				content = sub_row[column]
				if not content or not 'archive' in content:
					continue

				# Move file on disk
				old_file = dirname + '/' + content
				new_file = dirname + '/archive/' + year + '/' + month + '/' + day + '/' + str(timestamp) + '/' + os.path.basename(content)

				try:
					# If the script was interrupted then
					# the file may be moved but the database
					# entry not yet be updated. Just update the
					# entry in that case.
					if not os.path.exists(new_file):
						os.renames(old_file, new_file)
				except Exception as ex:
					sys.stderr.write('Failed to move "%s" to "%s": %s\n' % (old_file,new_file,str(ex)))
					if not force:
						sys.stderr.write('Exiting. You can run the migration script again after fixing\n')
						sys.stderr.write('the error. Already migrated entries will be left untouched.\n')
						sys.exit(-1)
					else:
						sys.stderr.write('Clearing entry in database\n')
						new_file = ''

				res = conn.execute('UPDATE "%s" SET "%s"=? WHERE id=?' % (table_name, column), (os.path.basename(content), sub_row['id']))
				n_converted_entries += 1
	finally:
		conn.commit()

	sys.stdout.write('converted %d/%d entries\n' % (n_converted_entries, n_entries))

list = filter(lambda x: len(x) > 5, os.listdir(dirname + '/archive'))

if list:
	sys.stderr.write('There are still timestamp directories in %s/archive remaining\n' % dirname)
	sys.stderr.write('These files have not been migrated since they\n')
	sys.stderr.write('are not referenced in the database.\n')
