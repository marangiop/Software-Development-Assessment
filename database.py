from pymongo import MongoClient, TEXT
import pandas as pd
import csv, math, pprint
client = MongoClient()
db = client.rankit


class Database(object):
	"""docstring for Database"""
	db = MongoClient().rankit
	institutions = db.institutions
	courses = db.courses
	subjects = db.subjects

	def DropDB(self):
		confirm = input("Are you sure you want to delete the database? (y/n)")
		if confirm == "y":
			client.drop_database('rankit')
			print("DB Dropped")
		else:
			print("Abort")
	def Bootstrap(self):
		self.ImportInstitutions()
		self.ImportCourses()
		self.ImportLocations()
		self.ImportNSS()
		self.ImportSalary()
		self.ImportGraduationRates()
		self.ImportEmploymentRates()
		self.ComputeInstitutionAverages()
		self.AssignSubjects()
		
	def ImportInstitutions(self):
		print('Importing Institutions...')
		self.institutions.create_index([('$**', 'text')])
		df = pd.read_csv('./data/learning-providers.csv')
		for index,row in df.iterrows():
			entry = row.to_dict()
			entry['courses_ids'] = []
			entry['locations'] = []
			self.institutions.update({'UKPRN':entry['UKPRN']}, entry, upsert=True)
	def ImportCourses(self):
		print('Importing Courses...')
		df = pd.read_csv('./data/KISCOURSE.csv', low_memory=False)
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' courses')
			entry = row.to_dict()
			ukprn = entry['UKPRN']
			kiscourseid = entry['KISCOURSEID']
			self.courses.update({'KISCOURSEID':kiscourseid}, entry, upsert=True)
			self.institutions.update( {'UKPRN':ukprn}, { '$push': { 'courses_ids': kiscourseid } }, upsert=True )
		self.courses.create_index([('$**', 'text')])

	def ImportLocations(self):
		df = pd.read_csv('./data/LOCATION.csv')
		print('Importing Locations')
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' locations')
			entry = row.to_dict()
			ukprn = entry['UKPRN']
			entry.pop('UKPRN')
			self.institutions.update( {'UKPRN':ukprn}, { '$push': { 'locations': entry } }, upsert=True )
		self.institutions.create_index([('$**', 'text')])

	def ImportNSS(self):
		df = pd.read_csv('./data/NSS.csv')
		print('Importing NSS')
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' NSS entries')
			entry = row.to_dict()
			if math.isnan(entry['Q27']) or entry['Q27'] == 0.0:
				continue
			kiscourseid = entry["KISCOURSEID"]
			entry.pop('PUBUKPRN')
			entry.pop('UKPRN')
			entry.pop('KISCOURSEID')
			entry.pop('KISMODE')
			self.courses.update({'KISCOURSEID':kiscourseid}, { '$push': { 'nss': entry} }, upsert=True )
			self.courses.update({'KISCOURSEID':kiscourseid}, { '$set': {'studentsatisfaction_rate_percent': entry['Q27']}}, upsert=True )
		self.courses.create_index([('$**', 'text')])
		'''
		df = pd.read_csv('./data/NHSNSS.csv')
		print('Importing NHSNSS')
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' NHS NSS entries')
			entry = row.to_dict()
			kiscourseid = entry["KISCOURSEID"]
			entry.pop('PUBUKPRN')
			entry.pop('UKPRN')
			entry.pop('KISCOURSEID')
			entry.pop('KISMODE')
			self.courses.update({'KISCOURSEID':kiscourseid}, { '$push': { 'nss': entry} }, upsert=True )
		self.courses.create_index([('$**', 'text')])
		'''

	def ImportSalary(self):
		df = pd.read_csv('./data/SALARY.csv')
		print('Importing Salary')
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' salaries')
			entry = row.to_dict()
			if math.isnan(entry['INSTMED']) or entry['INSTMED'] == 0.0:
				continue
			kiscourseid = entry["KISCOURSEID"]
			entry.pop('PUBUKPRN')
			entry.pop('UKPRN')
			entry.pop('KISCOURSEID')
			entry.pop('KISMODE')
			self.courses.update({'KISCOURSEID':kiscourseid}, { '$push': { 'salary': entry} }, upsert=True )
			self.courses.update({'KISCOURSEID':kiscourseid},{ '$set': { 'median_salary': entry['INSTMED']}}, upsert=True )
		self.courses.create_index([('$**', 'text')])

	def ImportGraduationRates(self):
		df = pd.read_csv('./data/DEGREECLASS.csv')
		print("Adding Graduation Rate")
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' graduation rates')
			entry = row.to_dict()
			if math.isnan(entry['UPASS']):
				continue
			kiscourseid = entry["KISCOURSEID"]
			self.courses.update({'KISCOURSEID':kiscourseid},{ '$set':  { 'graduation_rate_percent': entry["UPASS"]} }, upsert=True )


	def ImportEmploymentRates(self):
		df = pd.read_csv('./data/EMPLOYMENT.csv')
		print("Adding Employment Rates 6M post-graduation")
		for index,row in df.iterrows():
			if index%1000 == 0:
					print(str(index)+' out of '+str(df.size) + ' employment rates')
			entry = row.to_dict()
			if math.isnan(entry['WORKSTUDY']) or entry['WORKSTUDY'] == 0.0:
				continue
			kiscourseid = entry["KISCOURSEID"]
			self.courses.update({'KISCOURSEID':kiscourseid},{ '$set':  { 'employment_rate_percent': entry["WORKSTUDY"]}}, upsert=True )

	def ComputeInstitutionAverages(self):
		institutions = self.institutions.find()
		values_employment = []
		values_graduation = []
		values_salary = []
		values_studentsatisfaction = []
		print("computing graduation rates")
		for idx,institution in enumerate(institutions):
			if idx%1000 == 0:
					print(str(idx)+' out of '+str(institutions.count()) + 'institution rates computed')
			prn = institution["UKPRN"]
			for course in self.courses.find({'UKPRN':prn}):
				if ('median_salary' not in course) or ('graduation_rate_percent' not in course) or ('employment_rate_percent' not in course) or ('studentsatisfaction_rate_percent' not in course):
					continue
				values_employment.append(course['employment_rate_percent'])
				values_graduation.append(course['graduation_rate_percent'])
				values_salary.append(course['median_salary'])
				values_studentsatisfaction.append(course['studentsatisfaction_rate_percent'])

			
			if len(values_graduation) > 0:
				institution_gradrate = (sum(values_graduation)/len(values_graduation))
			else:
				institution_gradrate = None

			if len(values_employment) > 0:
				institution_emprate = (sum(values_employment)/len(values_employment))
			else:
				institution_emprate = None

			if len(values_salary) > 0:
				institution_salary = (sum(values_salary)/len(values_salary))
			else:
				institution_salary = None

			if len(values_employment) > 0:
				institution_studentsat = (sum(values_studentsatisfaction)/len(values_studentsatisfaction))
			else:
				institution_studentsat = None
			self.institutions.update({'UKPRN':prn},{ '$set':  { 'employment_rate_percent': institution_emprate}}, upsert=True  )
			self.institutions.update({'UKPRN':prn},{ '$set':  { 'graduation_rate_percent': institution_gradrate}}, upsert=True  )
			self.institutions.update({'UKPRN':prn},{ '$set':  { 'median_salary': institution_salary}}, upsert=True  )
			self.institutions.update({'UKPRN':prn},{ '$set':  { 'studentsatisfaction_rate_percent': institution_studentsat}}, upsert=True  )
			values_employment.clear()
			values_graduation.clear()
			values_salary.clear()
			values_studentsatisfaction.clear()


	def AssignSubjects(self):
		print("Assigning subjects to courses")
		reader = csv.reader(open('./data/CAH.csv', 'r'))
		lookup = {}
		for row in reader:
			k, v = row
			lookup[k] = v
		print("dddd")
		reader = csv.reader(open('./data/SBJ.csv', 'r'))
		cah_courses = {}
		for row in reader:
			k, v = row
			cah_courses[k] = v

		courses = []

		for doc in db.courses.find():
			courses.append(doc)

		for x in courses:

			if 'KISCOURSEID' not in x:
				db.courses.delete_one({'_id':x['_id']})
				courses.remove(x)
				continue
			kiscourseid = x['KISCOURSEID']
			subject_cah = cah_courses[kiscourseid]
			subject_description = lookup[subject_cah]
			self.courses.update({'KISCOURSEID': kiscourseid},{ '$set':  {'subject_cah' : subject_cah} }, upsert=True)
			self.courses.update({'KISCOURSEID': kiscourseid},{ '$set':  {'subject_description' : subject_description} }, upsert=True)



if __name__ == '__main__':
    d = Database()
    d.DropDB()
    d.Bootstrap()
