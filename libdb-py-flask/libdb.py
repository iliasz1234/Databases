from flask import Flask, render_template, request
from flask_mysqldb import MySQL

if __name__ == '__main__':
	app = Flask(__name__)

app.config['MYSQL_HOST'] = '127.0.0.1'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'libdb'
 
mysql = MySQL(app)

def get_request_values(request):
	f1 = request.args.get('filter1', '')
	if f1:
		if f1 != 'all':
			fltr1 = f1
			fltr1_key = request.args.get('filter1_key', '')
			selected1 = fltr1
			selected1_key = fltr1_key
		else:
			fltr1 = '0'
			fltr1_key = 0;
			selected1 = 'all'
			selected1_key = ''	
	else:			
		fltr1 = '0'
		fltr1_key = 0;
		selected1 = 'all'
		selected1_key = ''				

	f2 = request.args.get('filter2', '')
	if f2:	
		if request.args.get('filter2', '') != 'all':
			fltr2 = f2
			fltr2_key = request.args.get('filter2_key', '')
			selected2 = fltr2
			selected2_key= fltr2_key
		else:
			fltr2 = '1'
			fltr2_key = 1
			selected2 = 'all'
			selected2_key = ''
	else:
		fltr2 = '1'
		fltr2_key = 1
		selected2 = 'all'
		selected2_key = ''

	d = {}
	if fltr1:
		d = {'fltr1':fltr1,'fltr1_key':fltr1_key,'selected1':selected1,'selected1_key':selected1_key}
	if fltr2:
		d2 = {'fltr2':fltr2,'fltr2_key':fltr2_key,'selected2':selected2,'selected2_key':selected2_key}
		for x in d:
			d2[x] = d[x]
		d = d2
	return d

@app.route("/", methods=['GET'])
def welcome():

	return render_template("layout.html", page_title = "Welcome!")


@app.route("/queries", methods=['GET'])
def queries():
	r = request.args.get('role', '')
	if r == 'admin':
		queries = ['q1','q2a','q2b','q3','q4','q5','q6','q7']
	elif r == 'operator':
		queries = ['q8','q9','q10a','q10b']
	elif r == 'user':
		queries = ['q11','q12']

	return render_template("query-list.html",queries = queries, page_title = r.capitalize())


@app.route("/reservation", methods=['GET','POST'])
def reservation():

	if request.method == "GET":

		title = request.args.get('title', '')

		cursor = mysql.connection.cursor()

		cursor.execute("SELECT b.book_id as book_id,title,GROUP_CONCAT(DISTINCT a.author SEPARATOR ', ') as authors,publisher,GROUP_CONCAT(DISTINCT c.category SEPARATOR ', ') as categories, GROUP_CONCAT(DISTINCT k.keyword SEPARATOR ', ') as keywords,pages,summary,language,GROUP_CONCAT(DISTINCT text SEPARATOR '|') as texts,AVG(likert) as avg_likert FROM books b JOIN book_authors ba ON b.book_id = ba.book_id JOIN authors a ON ba.author_id = a.author_id JOIN book_categories bc ON b.book_id = bc.book_id JOIN categories c ON bc.category_id = c.category_id JOIN book_keywords bk ON b.book_id = bk.book_id JOIN keywords k ON bk.keyword_id = k.keyword_id JOIN school_books sb ON b.book_id = sb.book_id JOIN reviews r ON b.book_id = r.book_id WHERE title = '{}';".format(title))

		columns = [i[0] for i in cursor.description]
		
		# rows is tuple of tuples -> rows[0]: tuple
		rows = cursor.fetchall()
		
		cursor.close()

		reviews = dict(zip(columns[-2:], rows[0][-2:]))
		columns = columns[:-2]		
		row = dict(zip(columns, rows[0][:-2]))	

		print(reviews)
		print(reviews['texts'])

		if reviews['texts']:
			reviews['texts'] = reviews['texts'] .split('|')
		else:
			reviews = []

		return render_template("reservation.html", columns = columns, row = row, reviews=reviews, page_title = "Reservation")

	if request.method == "POST":

		book_id = request.form['book_id']
		title = request.form['title']
		username = request.form['username']

		print(title)

		cursor = mysql.connection.cursor()

		# find user_id and user_school from username
		# also check for current loans/reservations because of the limit
		cursor.execute("SELECT u.user_id, school_id, current FROM users u JOIN school_users su ON u.user_id = su.user_id JOIN (SELECT sum(c) as current FROM ( SELECT 100 as c FROM loans l JOIN users u ON l.user_id = u.user_id WHERE u.username = '{}' AND DATEDIFF(CURRENT_DATE(),loan_date) > 7 AND NOT returned UNION SELECT count(*) as c FROM users u JOIN loans l ON u.user_id = l.user_id WHERE u.username = '{}' AND NOT returned UNION ALL SELECT count(*) as c FROM users u JOIN reservations r ON u.user_id = r.user_id WHERE u.username = '{}' AND DATEDIFF(CURRENT_DATE(),reservation_date) <= 7) as temp1) as temp2 WHERE username = '{}';".format(username,username,username,username))

		columns = [i[0] for i in cursor.description]

		rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]
		
		
		if rows:
			user_id = rows[0][columns[0]]
			school_id = rows[0][columns[1]]
			current = rows[0][columns[2]]

			if current < 2:
				cursor.execute("SELECT 100+val1-val2-val3 as available FROM (SELECT copies as val1 FROM school_books WHERE school_id = '{}' AND book_id = '{}') as tmp1 JOIN (SELECT count(*) as val2 FROM loans WHERE book_id = '{}' AND returned = 0) as tmp2 JOIN (SELECT count(*) as val3 FROM reservations WHERE book_id = '{}' AND DATEDIFF(CURRENT_DATE(),reservation_date) <= 7) as tmp3;".format(school_id,book_id,book_id,book_id))

				columns = [i[0] for i in cursor.description]

				rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

				cursor.close()

				if rows:
					# +100 for UNSIGNED int problem (when by mistake in data negative value)				
					available = rows[0][columns[0]] - 100
					
					if available > 0:
			
						cursor = mysql.connection.cursor()
	
						# insert new reservation
						cursor.execute("INSERT INTO reservations (user_id,book_id,school_id) VALUES(%s, %s, %s)", (str(user_id), str(book_id), str(school_id)))

						# commit
						mysql.connection.commit()

						cursor.close()

						text = "You have reserved book: {} for 1 week.".format(title)
						return render_template("action-result.html", text = text, page_title = "Success")
					else:
						text = "Book currently not available at school: {}.".format(school_id)
						return render_template("action-result.html", text = text, page_title = "Error")
				else:
					text = "No copy of this book at school: {}.".format(school_id)
					return render_template("action-result.html", text = text, page_title = "Error")
			else:
				text = "You are limited to 2 loans/reservations per week."
				return render_template("action-result.html", text = text, page_title = "Error")
		else:
			text = "Wrong Username: {}.".format(username)
			return render_template("action-result.html", text = text, page_title = "Error")
			

@app.route("/q1", methods=['GET'])
def q1():
	cursor = mysql.connection.cursor()

	req = get_request_values(request)
	if req['fltr1'] != '0':
		req['fltr1'] += "(loan_date)"	

	cursor.execute("SELECT school_id,count(*) FROM loans WHERE {}='{}' GROUP BY school_id;".format(req['fltr1'],req['fltr1_key']))

	action = 'q1'

	filters1 = ['all', 'year', 'month']
	
	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q1")


@app.route("/q2a", methods=['GET'])
def q2a():

	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT DISTINCT author FROM authors a JOIN book_authors ba ON a.author_id = ba.author_id JOIN book_categories bc ON ba.book_id = bc.book_id JOIN categories c ON bc.category_id = c.category_id WHERE {}='{}';".format(req['fltr1'],req['fltr1_key']))		

	action = 'q2a'

	filters1 = ['all', 'category']
	
	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q2A")


@app.route("/q2b", methods=['GET'])
def q2b():

	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT first_name, last_name FROM users u JOIN roles r ON u.role_id = r.role_id JOIN loans l ON u.user_id = l.user_id JOIN book_categories bc ON l.book_id = bc.book_id JOIN categories c ON bc.category_id = c.category_id WHERE role = 'teacher' AND {}='{}' AND YEAR(loan_date)=2023 GROUP BY u.user_id;".format(req['fltr1'],req['fltr1_key']))

	action = 'q2b'

	filters1 = ['all', 'category']
	
	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q2B")	


@app.route("/q3", methods=['GET'])
def q3():
	cursor = mysql.connection.cursor()

	cursor.execute("SELECT first_name, last_name, count(book_id) FROM users u JOIN roles r ON u.role_id = r.role_id JOIN loans l ON u.user_id = l.user_id WHERE role = 'teacher' AND DATEDIFF(CURRENT_DATE(),date_of_birth)/365 < 40 GROUP BY u.user_id ORDER BY count(book_id) DESC LIMIT 3;")

	action = 'q3'

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, columns = columns, rows = rows, page_title = "Q3")


@app.route("/q4", methods=['GET'])
def q4():
	cursor = mysql.connection.cursor()

	cursor.execute("SELECT author FROM authors a EXCEPT SELECT author FROM authors a JOIN book_authors ba ON a.author_id = ba.author_id JOIN loans l ON ba.book_id = l.book_id;")

	action = 'q4'

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, columns = columns, rows = rows, page_title = "Q4")


@app.route("/q5", methods=['GET'])
def q5():

	cursor = mysql.connection.cursor()

	req = get_request_values(request)
	if req['fltr1'] != '0':
		req['fltr1'] = "t1.cnt" 

	cursor.execute("SELECT concat(t1.first_name,' ',t1.last_name) as n1,t1.year as y1,concat(t2.first_name,' ',t2.last_name) as n2,t2.year as y2,t1.cnt as count FROM (SELECT first_name,last_name,YEAR(loan_date) as year,count(*) as cnt,u.user_id as u1 FROM users u JOIN schools s ON u.user_id = s.operator_id JOIN loans l ON s.school_id = l.school_id GROUP BY l.school_id, YEAR(loan_date))t1 JOIN ( SELECT first_name,last_name,YEAR(loan_date) as year,count(*) as cnt,u.user_id as u2 FROM users u JOIN schools s ON u.user_id = s.operator_id JOIN loans l ON s.school_id = l.school_id GROUP BY l.school_id, YEAR(loan_date))t2 ON t1.cnt= t2.cnt WHERE u1 < u2 AND {}>='{}';".format(req['fltr1'],req['fltr1_key']))		

	action = 'q5'

	filters1 = ['all', 'count']
	
	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q5")


@app.route("/q6", methods=['GET'])
def q6():
	cursor = mysql.connection.cursor()

	cursor.execute("SELECT c1.category as cat1,c2.category as cat2,count(*) FROM categories c1 JOIN categories c2 JOIN book_categories bc1 ON c1.category_id = bc1.category_id JOIN book_categories bc2 ON c2.category_id = bc2.category_id JOIN loans l ON bc1.book_id = l.book_id WHERE c1.category < c2.category AND bc1.book_id = bc2.book_id GROUP BY c1.category,c2.category ORDER BY count(*) DESC LIMIT 3;")

	action = 'q6'

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, columns = columns, rows = rows, page_title = "Q6")


@app.route("/q7", methods=['GET'])
def q7():

	cursor = mysql.connection.cursor()

	cursor.execute("SELECT author, count(*) FROM authors a JOIN book_authors ba ON a.author_id = ba.author_id GROUP BY a.author_id HAVING count(*) >= (SELECT count(*) FROM authors a JOIN book_authors ba ON a.author_id = ba.author_id GROUP BY a.author_id ORDER BY count(*) DESC LIMIT 1)-5;")

	action = 'q7'

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, columns = columns, rows = rows, page_title = "Q7")


@app.route("/q8", methods=['GET'])
def q8():
	cursor = mysql.connection.cursor()

	req = get_request_values(request)
	
	if req['selected1'] == 'all' and req['selected2'] == 'copies':
		req['fltr2'] = 'total_copies'		


	cursor.execute("SELECT b.title, GROUP_CONCAT(DISTINCT a.author SEPARATOR ', ') as authors, GROUP_CONCAT(DISTINCT c.category SEPARATOR ', ') as categories, sb.copies, b.total_copies FROM books b JOIN school_books sb ON b.book_id = sb.book_id JOIN book_authors ba ON b.book_id = ba.book_id JOIN authors a ON ba.author_id = a.author_id JOIN book_categories bc ON b.book_id = bc.book_id  JOIN categories c ON bc.category_id = c.category_id WHERE {}='{}' AND {}='{}' GROUP BY b.book_id ORDER BY title;".format(req['fltr1'],req['fltr1_key'],req['fltr2'],req['fltr2_key']))

	action = 'q8'

	filters1 = ['all', 'school_id']
	filters2 = ['all','title', 'author', 'category', 'copies']

	filter_selection = "{}: {}, {}: {}".format(req['selected1'], req['selected1_key'], req['selected2'], req['selected2_key'])

	columns = [i[0] for i in cursor.description]

	if req['selected1'] == 'all':
		columns = columns[:-2]+columns[-1:]
		rows = [dict(zip(columns, entry[:-2]+entry[-1:])) for entry in cursor.fetchall()]
	else:
		columns = columns[:-1]
		rows = [dict(zip(columns, entry[:-1])) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filters2 = filters2, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q8")


@app.route("/q9", methods=['GET'])
def q9():
	cursor = mysql.connection.cursor()

	req = get_request_values(request)
	if req['fltr2'] == 'days':
		req['fltr2'] = "DATEDIFF(CURRENT_DATE(),loan_date)>"

	cursor.execute("SELECT first_name, last_name, DATEDIFF(CURRENT_DATE(),loan_date) as delay FROM loans l JOIN users u ON l.user_id = u.user_id WHERE {} = '{}' AND {}='{}' AND NOT returned AND DATEDIFF(CURRENT_DATE(),loan_date) > 7;".format(req['fltr1'],req['fltr1_key'],req['fltr2'],req['fltr2_key']))

	
	action = 'q9'

	filters1 = ['all', 'school_id']
	filters2 = ['all','first_name','last_name','days']

	filter_selection = "{}: {}, {}: {}".format(req['selected1'], req['selected1_key'], req['selected2'], req['selected2_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filters2 = filters2, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q9")


@app.route("/q10a", methods=['GET'])
def q10a():
	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT AVG(likert) FROM reviews r JOIN users u ON r.user_id = u.user_id JOIN school_users su ON u.user_id = su.user_id WHERE {}='{}';".format(req['fltr1'],req['fltr1_key']))

	action = 'q10a'

	filters1 = ['all','username']

	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q10A")


@app.route("/q10b", methods=['GET'])
def q10b():
	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT AVG(likert) FROM reviews r JOIN book_categories bc ON r.book_id = bc.book_id JOIN categories c ON bc.category_id = c.category_id WHERE {}='{}';".format(req['fltr1'],req['fltr1_key']))

	action = 'q10b'

	filters1 = ['all','category']

	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q10B")

@app.route("/q11", methods=['GET'])
def q11():

	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT title, GROUP_CONCAT(DISTINCT a.author SEPARATOR ', ') as authors, GROUP_CONCAT(DISTINCT c.category SEPARATOR ', ') as categories FROM books b JOIN book_authors ba ON b.book_id = ba.book_id JOIN authors a ON ba.author_id = a.author_id JOIN book_categories bc ON b.book_id = bc.book_id JOIN categories c ON bc.category_id = c.category_id JOIN school_books sb ON b.book_id = sb.book_id WHERE {}='{}' AND {}='{}' GROUP BY b.book_id ORDER BY title;".format(req['fltr1'],req['fltr1_key'],req['fltr2'],req['fltr2_key']))

	action = 'q11'

	filters1 = ['all', 'school_id']
	filters2 = ['all', 'title', 'category', 'author']

	filter_selection = "{}: {}, {}: {}".format(req['selected1'], req['selected1_key'], req['selected2'], req['selected2_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("books.html",action = action, filters1 = filters1, filters2 = filters2, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q11")


@app.route("/q12", methods=['GET'])
def q12():

	cursor = mysql.connection.cursor()

	req = get_request_values(request)

	cursor.execute("SELECT title, loan_date FROM books b JOIN loans l ON b.book_id = l.book_id JOIN users u ON l.user_id = u.user_id WHERE {}='{}';".format(req['fltr1'],req['fltr1_key']))

	action = 'q12'
	
	filters1 = ['all', 'username']

	filter_selection = "{}: {}".format(req['selected1'], req['selected1_key'])

	columns = [i[0] for i in cursor.description]

	rows = [dict(zip(columns, entry)) for entry in cursor.fetchall()]

	cursor.close()

	return render_template("table-filters.html",action = action, filters1 = filters1, filter_selection = filter_selection, columns = columns, rows = rows, page_title = "Q12")


if __name__ == '__main__':
        app.run(debug="True", host='127.0.0.1', port=5000)

	
